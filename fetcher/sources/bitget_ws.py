"""
Bitget WebSocket source: subscribes to OHLCV candle channels.
Reads active symbols from DB. Builds 2h/8h aggregated candles.
"""

import json
import asyncio
import logging
from datetime import datetime, timezone

import websockets
from db_helper import get_db, get_active_symbols

WS_URL = "wss://ws.bitget.com/v2/ws/public"

# Bitget channel suffixes for each timeframe
TF_MAP = {
    "30m": "30min",
    "1h": "1H",
    "4h": "4H",
    "12h": "12H",
    "1D": "1Dutc",
    "1W": "1Wutc",
}

log = logging.getLogger("fetcher.ws")


def insert_candle(conn, symbol, timeframe, candle):
    ts = datetime.fromtimestamp(int(candle[0]) / 1000, tz=timezone.utc)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ohlcv (time, symbol, timeframe, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
            open=EXCLUDED.open, high=EXCLUDED.high,
            low=EXCLUDED.low, close=EXCLUDED.close,
            volume=EXCLUDED.volume
    """, (ts, symbol, timeframe, float(candle[1]), float(candle[2]),
          float(candle[3]), float(candle[4]), float(candle[5])))
    conn.commit()
    cur.close()
    return ts


def build_aggregated_candle(conn, symbol, source_tf, target_tf, count, current_ts):
    cur = conn.cursor()
    cur.execute("""
        SELECT open, high, low, close, volume, time
        FROM ohlcv WHERE symbol=%s AND timeframe=%s AND time<=%s
        ORDER BY time DESC LIMIT %s
    """, (symbol, source_tf, current_ts, count))
    rows = cur.fetchall()

    if len(rows) == count:
        rows.reverse()
        o, h, l, c = rows[0][0], max(r[1] for r in rows), min(r[2] for r in rows), rows[-1][3]
        v, t = sum(r[4] for r in rows), rows[0][5]

        cur.execute("""
            INSERT INTO ohlcv (time, symbol, timeframe, open, high, low, close, volume)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
                open=EXCLUDED.open, high=EXCLUDED.high,
                low=EXCLUDED.low, close=EXCLUDED.close,
                volume=EXCLUDED.volume
        """, (t, symbol, target_tf, o, h, l, c, v))
        conn.commit()
        log.info(f"  Built {symbol} {target_tf} @ {t}")
    cur.close()


async def run(reload_interval=300):
    """
    Main WebSocket loop. Reloads symbol config from DB every reload_interval seconds.
    """
    conn = get_db()

    while True:
        symbols_config = get_active_symbols()
        symbols = [s["symbol"] for s in symbols_config]

        if not symbols:
            log.warning("No active symbols in fetcher_config. Sleeping 60s...")
            await asyncio.sleep(60)
            continue

        # Only subscribe to native WS timeframes (not aggregated 2h/8h)
        native_tfs = [tf for tf in TF_MAP.keys()]

        try:
            async with websockets.connect(WS_URL, ping_interval=25) as ws:
                subs = []
                for symbol in symbols:
                    for tf in native_tfs:
                        if tf in TF_MAP:
                            subs.append({
                                "instType": "USDT-FUTURES",
                                "channel": "candle" + TF_MAP[tf],
                                "instId": symbol,
                            })

                await ws.send(json.dumps({"op": "subscribe", "args": subs}))
                log.info(f"Subscribed: {len(subs)} channels for {symbols}")

                tf_reverse = {v: k for k, v in TF_MAP.items()}

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

                    timeframe = None
                    for suffix, orig_tf in tf_reverse.items():
                        if channel == "candle" + suffix:
                            timeframe = orig_tf
                            break

                    if not timeframe:
                        continue

                    for candle in data["data"]:
                        ts = insert_candle(conn, symbol, timeframe, candle)
                        log.debug(f"Candle {symbol} {timeframe} @ {ts}")

                        # Build aggregated timeframes
                        if timeframe == "1h" and ts.hour % 2 == 1:
                            build_aggregated_candle(conn, symbol, "1h", "2h", 2, ts)
                        elif timeframe == "4h" and ts.hour % 8 == 4:
                            build_aggregated_candle(conn, symbol, "4h", "8h", 2, ts)

        except (websockets.ConnectionClosed, ConnectionError, OSError) as e:
            log.warning(f"WS connection lost: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            log.error(f"WS unexpected error: {e}. Reconnecting in 10s...")
            await asyncio.sleep(10)
