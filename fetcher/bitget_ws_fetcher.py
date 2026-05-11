"""
Fetcher: Bitget WebSocket (futures) → OHLCV candles → PostgreSQL.
Auto-reconnect, builds 2h/8h from 1h/4h.
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timezone

import websockets
import psycopg2

DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "trading")
DB_USER = os.getenv("DB_USER", "trading")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")
SYMBOLS = os.getenv("SYMBOLS", "ETHUSDT").split(",")

WS_URL = "wss://ws.bitget.com/v2/ws/public"
TIMEFRAMES = ["1h", "4h", "12h", "1D", "1W"]
TF_MAP = {"1h": "1H", "4h": "4H", "12h": "12H", "1D": "1Dutc", "1W": "1Wutc"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fetcher")


def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
    )


def insert_candle(conn, symbol, timeframe, candle):
    ts = datetime.fromtimestamp(int(candle[0]) / 1000, tz=timezone.utc)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ohlcv (time, symbol, timeframe, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
            open = EXCLUDED.open, high = EXCLUDED.high,
            low = EXCLUDED.low, close = EXCLUDED.close,
            volume = EXCLUDED.volume
    """, (ts, symbol, timeframe, float(candle[1]), float(candle[2]),
          float(candle[3]), float(candle[4]), float(candle[5])))
    conn.commit()
    cur.close()
    return ts


def build_aggregated_candle(conn, symbol, source_tf, target_tf, count, current_ts):
    cur = conn.cursor()
    cur.execute("""
        SELECT open, high, low, close, volume, time
        FROM ohlcv
        WHERE symbol = %s AND timeframe = %s AND time <= %s
        ORDER BY time DESC LIMIT %s
    """, (symbol, source_tf, current_ts, count))
    rows = cur.fetchall()

    if len(rows) == count:
        rows.reverse()
        o = rows[0][0]
        h = max(r[1] for r in rows)
        l = min(r[2] for r in rows)
        c = rows[-1][3]
        v = sum(r[4] for r in rows)
        t = rows[0][5]

        cur.execute("""
            INSERT INTO ohlcv (time, symbol, timeframe, open, high, low, close, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
                open = EXCLUDED.open, high = EXCLUDED.high,
                low = EXCLUDED.low, close = EXCLUDED.close,
                volume = EXCLUDED.volume
        """, (t, symbol, target_tf, o, h, l, c, v))
        conn.commit()
        log.info(f"  Built {symbol} {target_tf} @ {t}")

    cur.close()


async def run_websocket():
    conn = get_db()

    while True:
        try:
            async with websockets.connect(WS_URL, ping_interval=25) as ws:
                subs = []
                for symbol in SYMBOLS:
                    for tf in TIMEFRAMES:
                        subs.append({
                            "instType": "USDT-FUTURES",
                            "channel": "candle" + TF_MAP[tf],
                            "instId": symbol,
                        })

                await ws.send(json.dumps({"op": "subscribe", "args": subs}))
                log.info(f"Subscribed: {len(subs)} channels")

                async for msg in ws:
                    try:
                        data = json.loads(msg)
                    except json.JSONDecodeError:
                        continue

                    if "data" not in data or "arg" not in data:
                        continue

                    arg = data["arg"]
                    symbol = arg.get("instId", "")
                    channel = arg.get("channel", "")

                    tf_reverse = {v: k for k, v in TF_MAP.items()}
                    timeframe = None
                    for suffix, orig_tf in tf_reverse.items():
                        if channel == "candle" + suffix:
                            timeframe = orig_tf
                            break

                    if not timeframe:
                        continue

                    for candle in data["data"]:
                        ts = insert_candle(conn, symbol, timeframe, candle)
                        log.info(f"Candle {symbol} {timeframe} @ {ts}")

                        if timeframe == "1h" and ts.hour % 2 == 1:
                            build_aggregated_candle(conn, symbol, "1h", "2h", 2, ts)
                        elif timeframe == "4h" and ts.hour % 8 == 4:
                            build_aggregated_candle(conn, symbol, "4h", "8h", 2, ts)

        except (websockets.ConnectionClosed, ConnectionError, OSError) as e:
            log.warning(f"Connection lost: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            log.error(f"Unexpected error: {e}. Reconnecting in 10s...")
            await asyncio.sleep(10)


if __name__ == "__main__":
    log.info("Starting Bitget fetcher...")
    asyncio.run(run_websocket())
