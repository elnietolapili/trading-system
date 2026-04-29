"""
Calculador de indicadores: recalcula EMAs, SAR, RSI para todas las velas.

Corre en bucle cada 60 segundos. Detecta filas con indicadores vacíos
y los calcula. Solo recalcula lo necesario, no toda la tabla.

Indicadores:
    - EMA 9, 20, 50, 100, 200
    - Parabolic SAR 0.015/0.015/0.12
    - Parabolic SAR 0.02/0.02/0.2
    - RSI 14
    - RSI 7
    - RSI MA 14 (media móvil del RSI 14)
"""

import os
import time
import logging

import numpy as np
import psycopg2
import psycopg2.extras

DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "trading")
DB_USER = os.getenv("DB_USER", "trading")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")

INTERVAL = int(os.getenv("CALC_INTERVAL", "60"))  # segundos entre ejecuciones

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("indicators")


# ── Funciones de cálculo ───────────────────────────────────────

def calc_ema(closes, period):
    """Calcula EMA. Devuelve array del mismo tamaño, con NaN al inicio."""
    ema = np.full(len(closes), np.nan)
    if len(closes) < period:
        return ema
    # Primer valor: SMA
    ema[period - 1] = np.mean(closes[:period])
    multiplier = 2 / (period + 1)
    for i in range(period, len(closes)):
        ema[i] = closes[i] * multiplier + ema[i - 1] * (1 - multiplier)
    return ema


def calc_rsi(closes, period):
    """Calcula RSI. Devuelve array del mismo tamaño, con NaN al inicio."""
    rsi = np.full(len(closes), np.nan)
    if len(closes) < period + 1:
        return rsi
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100 - (100 / (1 + rs))

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100 - (100 / (1 + rs))
    return rsi


def calc_sma(values, period):
    """Media móvil simple sobre un array (puede contener NaN)."""
    result = np.full(len(values), np.nan)
    for i in range(period - 1, len(values)):
        window = values[i - period + 1:i + 1]
        if np.any(np.isnan(window)):
            continue
        result[i] = np.mean(window)
    return result


def calc_parabolic_sar(highs, lows, closes, af_start, af_increment, af_max):
    """Calcula Parabolic SAR. Devuelve array del mismo tamaño."""
    n = len(closes)
    sar = np.full(n, np.nan)
    if n < 2:
        return sar

    # Inicializar
    is_long = closes[1] > closes[0]
    af = af_start
    if is_long:
        sar[0] = lows[0]
        ep = highs[0]
    else:
        sar[0] = highs[0]
        ep = lows[0]

    for i in range(1, n):
        prev_sar = sar[i - 1]

        if is_long:
            sar[i] = prev_sar + af * (ep - prev_sar)
            # SAR no puede estar por encima de los dos mínimos anteriores
            sar[i] = min(sar[i], lows[i - 1])
            if i >= 2:
                sar[i] = min(sar[i], lows[i - 2])

            if lows[i] < sar[i]:
                # Cambio a short
                is_long = False
                sar[i] = ep
                ep = lows[i]
                af = af_start
            else:
                if highs[i] > ep:
                    ep = highs[i]
                    af = min(af + af_increment, af_max)
        else:
            sar[i] = prev_sar + af * (ep - prev_sar)
            # SAR no puede estar por debajo de los dos máximos anteriores
            sar[i] = max(sar[i], highs[i - 1])
            if i >= 2:
                sar[i] = max(sar[i], highs[i - 2])

            if highs[i] > sar[i]:
                # Cambio a long
                is_long = True
                sar[i] = ep
                ep = highs[i]
                af = af_start
            else:
                if lows[i] < ep:
                    ep = lows[i]
                    af = min(af + af_increment, af_max)

    return sar


# ── Lógica principal ───────────────────────────────────────────

def get_db():
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
    )
    conn.autocommit = True
    return conn


def get_symbol_timeframe_pairs(conn):
    """Obtiene todas las combinaciones symbol/timeframe en la DB."""
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT symbol, timeframe FROM ohlcv ORDER BY symbol, timeframe")
    pairs = cur.fetchall()
    cur.close()
    return pairs


def calculate_and_update(conn, symbol, timeframe):
    """Calcula todos los indicadores para un symbol/timeframe y actualiza la DB."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT time, open, high, low, close, volume,
               ema_9, rsi_14
        FROM ohlcv
        WHERE symbol = %s AND timeframe = %s
        ORDER BY time ASC
    """, (symbol, timeframe))
    rows = cur.fetchall()
    cur.close()

    if len(rows) < 2:
        return 0

    # Comprobar si hay indicadores vacíos
    has_nulls = any(r["ema_9"] is None or r["rsi_14"] is None for r in rows)
    if not has_nulls:
        return 0  # Todo ya calculado

    # Extraer arrays
    closes = np.array([float(r["close"]) for r in rows])
    highs = np.array([float(r["high"]) for r in rows])
    lows = np.array([float(r["low"]) for r in rows])

    # Calcular indicadores
    ema_9 = calc_ema(closes, 9)
    ema_20 = calc_ema(closes, 20)
    ema_50 = calc_ema(closes, 50)
    ema_100 = calc_ema(closes, 100)
    ema_200 = calc_ema(closes, 200)
    sar_015 = calc_parabolic_sar(highs, lows, closes, 0.015, 0.015, 0.12)
    sar_020 = calc_parabolic_sar(highs, lows, closes, 0.02, 0.02, 0.2)
    rsi_14 = calc_rsi(closes, 14)
    rsi_7 = calc_rsi(closes, 7)
    rsi_ma_14 = calc_sma(rsi_14, 14)

    # Actualizar en lotes
    cur = conn.cursor()
    updated = 0
    for i, row in enumerate(rows):
        def val(arr, idx):
            v = arr[idx]
            return None if np.isnan(v) else float(v)

        cur.execute("""
            UPDATE ohlcv SET
                ema_9 = %s, ema_20 = %s, ema_50 = %s, ema_100 = %s, ema_200 = %s,
                sar_015 = %s, sar_020 = %s,
                rsi_14 = %s, rsi_7 = %s, rsi_ma_14 = %s
            WHERE time = %s AND symbol = %s AND timeframe = %s
        """, (
            val(ema_9, i), val(ema_20, i), val(ema_50, i),
            val(ema_100, i), val(ema_200, i),
            val(sar_015, i), val(sar_020, i),
            val(rsi_14, i), val(rsi_7, i), val(rsi_ma_14, i),
            row["time"], symbol, timeframe,
        ))
        updated += 1

    cur.close()
    return updated


def run_cycle():
    """Ejecuta un ciclo de cálculo para todos los pares."""
    conn = get_db()
    pairs = get_symbol_timeframe_pairs(conn)
    total = 0

    for symbol, timeframe in pairs:
        count = calculate_and_update(conn, symbol, timeframe)
        if count > 0:
            log.info(f"  {symbol} {timeframe}: {count} filas actualizadas")
            total += count

    conn.close()
    return total


# ── Main ───────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Iniciando calculador de indicadores...")

    while True:
        try:
            total = run_cycle()
            if total > 0:
                log.info(f"Ciclo completado: {total} filas actualizadas")
        except Exception as e:
            log.error(f"Error en ciclo: {e}")

        time.sleep(INTERVAL)
