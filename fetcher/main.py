"""
Fetcher: conecta a Bitget WebSocket (futuros) y guarda velas OHLCV en la DB.

- Escucha canales de velas para los timeframes disponibles en WS
- Construye velas de 2h y 8h a partir de 1h y 4h
- Auto-reconnect si se cae la conexión
- Ping cada 30s para mantener la conexión viva
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone

import psycopg2
import websockets

# ── Configuración ──────────────────────────────────────────────

DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "trading")
DB_USER = os.getenv("DB_USER", "trading")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")

SYMBOLS = os.getenv("SYMBOLS", "ETHUSDT").split(",")

WS_URL = "wss://ws.bitget.com/v2/ws/public"

# Timeframes disponibles en WebSocket de Bitget
# No incluye 2h ni 8h — los construimos nosotros
WS_TIMEFRAMES = ["1h", "4h", "12h", "1D", "1W"]

# Mapeo de nombre de canal de Bitget a nuestro nombre de timeframe
CHANNEL_MAP = {
    "candle1H": "1h",
    "candle4H": "4h",
    "candle12H": "12h",
    "candle1D": "1D",
    "candle1W": "1W",
}

# Mapeo inverso: nuestro timeframe al nombre de canal de Bitget
TF_TO_CHANNEL = {v: k for k, v in CHANNEL_MAP.items()}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("fetcher")

# ── Base de datos ──────────────────────────────────────────────

def get_db_connection():
    """Crea conexión a PostgreSQL con reintentos."""
    for attempt in range(10):
        try:
            conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT,
                dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
            )
            conn.autocommit = True
            return conn
        except psycopg2.OperationalError:
            log.warning(f"DB no disponible, reintento {attempt+1}/10...")
            time.sleep(3)
    raise Exception("No se pudo conectar a la DB tras 10 intentos")


def insert_candle(conn, symbol, timeframe, candle):
    """Inserta una vela en la DB. Si ya existe, la ignora."""
    sql = """
        INSERT INTO ohlcv (time, symbol, timeframe, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume
    """
    ts = datetime.fromtimestamp(int(candle[0]) / 1000, tz=timezone.utc)
    cur = conn.cursor()
    cur.execute(sql, (
        ts, symbol, timeframe,
        float(candle[1]),  # open
        float(candle[2]),  # high
        float(candle[3]),  # low
        float(candle[4]),  # close
        float(candle[5]),  # volume
    ))
    cur.close()
    return ts


def build_aggregated_candle(conn, symbol, base_tf, agg_tf, n_candles, ts):
    """
    Construye una vela agregada a partir de N velas del timeframe base.
    Ejemplo: 2h = 2 velas de 1h, 8h = 2 velas de 4h.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT open, high, low, close, volume, time
        FROM ohlcv
        WHERE symbol = %s AND timeframe = %s AND time <= %s
        ORDER BY time DESC
        LIMIT %s
    """, (symbol, base_tf, ts, n_candles))
    rows = cur.fetchall()
    cur.close()

    if len(rows) < n_candles:
        return  # No hay suficientes velas base todavía

    # rows están en orden DESC, invertir para cronológico
    rows = rows[::-1]

    agg_open = rows[0][0]
    agg_high = max(r[1] for r in rows)
    agg_low = min(r[2] for r in rows)
    agg_close = rows[-1][3]
    agg_volume = sum(r[4] for r in rows)
    agg_time = rows[0][5]  # timestamp de la primera vela

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ohlcv (time, symbol, timeframe, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume
    """, (agg_time, symbol, agg_tf, agg_open, agg_high, agg_low, agg_close, agg_volume))
    cur.close()
    log.info(f"  → Vela agregada {agg_tf} construida para {symbol} @ {agg_time}")


# ── WebSocket ──────────────────────────────────────────────────

def build_subscribe_message(symbols):
    """Construye el mensaje de suscripción para todos los símbolos y timeframes."""
    args = []
    for symbol in symbols:
        for tf in WS_TIMEFRAMES:
            channel = TF_TO_CHANNEL[tf]
            args.append({
                "instType": "USDT-FUTURES",
                "channel": channel,
                "instId": symbol,
            })
    return json.dumps({"op": "subscribe", "args": args})


async def run_websocket():
    """Bucle principal del WebSocket con auto-reconnect."""
    conn = get_db_connection()
    log.info(f"Conectado a DB. Symbols: {SYMBOLS}")

    while True:
        try:
            async with websockets.connect(WS_URL) as ws:
                log.info("WebSocket conectado a Bitget")

                # Suscribirse a canales
                sub_msg = build_subscribe_message(SYMBOLS)
                await ws.send(sub_msg)
                log.info(f"Suscrito a {len(SYMBOLS)} symbols × {len(WS_TIMEFRAMES)} timeframes")

                # Bucle de ping en paralelo
                async def ping_loop():
                    while True:
                        await asyncio.sleep(25)
                        try:
                            await ws.send("ping")
                        except Exception:
                            break

                ping_task = asyncio.create_task(ping_loop())

                try:
                    async for raw_msg in ws:
                        # Bitget responde "pong" a nuestro "ping"
                        if raw_msg == "pong":
                            continue

                        try:
                            msg = json.loads(raw_msg)
                        except json.JSONDecodeError:
                            continue

                        # Ignorar mensajes de confirmación de suscripción
                        if "event" in msg:
                            if msg["event"] == "subscribe":
                                log.info(f"Suscripción confirmada: {msg.get('arg', {}).get('channel')}")
                            elif msg["event"] == "error":
                                log.error(f"Error de suscripción: {msg}")
                            continue

                        # Procesar datos de velas
                        if "data" in msg and "arg" in msg:
                            arg = msg["arg"]
                            channel = arg.get("channel", "")
                            symbol = arg.get("instId", "")

                            if channel not in CHANNEL_MAP:
                                continue

                            timeframe = CHANNEL_MAP[channel]

                            for candle in msg["data"]:
                                ts = insert_candle(conn, symbol, timeframe, candle)
                                log.info(f"Vela {symbol} {timeframe} @ {ts}")

                                # Construir velas agregadas
                                if timeframe == "1h":
                                    # Cada 2 horas construir vela 2h
                                    if ts.hour % 2 == 1:  # hora impar = cierre de vela 2h
                                        build_aggregated_candle(conn, symbol, "1h", "2h", 2, ts)

                                elif timeframe == "4h":
                                    # Cada 8 horas construir vela 8h
                                    if ts.hour % 8 == 4:  # hora 4, 12, 20 = cierre de vela 8h
                                        build_aggregated_candle(conn, symbol, "4h", "8h", 2, ts)

                finally:
                    ping_task.cancel()

        except (websockets.ConnectionClosed, ConnectionError, OSError) as e:
            log.warning(f"Conexión perdida: {e}. Reconectando en 5s...")
            await asyncio.sleep(5)

        except Exception as e:
            log.error(f"Error inesperado: {e}. Reconectando en 10s...")
            await asyncio.sleep(10)


# ── Main ───────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Iniciando fetcher de Bitget...")
    asyncio.run(run_websocket())
