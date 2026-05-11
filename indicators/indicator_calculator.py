"""
Indicator calculator v1: EMAs, SAR, RSI every 60s.
Will be rewritten in Phase 3 as Feature Engineering dual system.
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
INTERVAL = int(os.getenv("CALC_INTERVAL", "60"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("indicators")


def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
    )


def calc_ema(closes, period):
    ema = np.full(len(closes), np.nan)
    if len(closes) < period:
        return ema
    ema[period - 1] = np.mean(closes[:period])
    m = 2 / (period + 1)
    for i in range(period, len(closes)):
        ema[i] = closes[i] * m + ema[i - 1] * (1 - m)
    return ema


def calc_rsi(closes, period):
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
        rsi[period] = 100 - (100 / (1 + avg_gain / avg_loss))
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi[i + 1] = 100.0
        else:
            rsi[i + 1] = 100 - (100 / (1 + avg_gain / avg_loss))
    return rsi


def calc_sma(values, period):
    result = np.full(len(values), np.nan)
    valid = ~np.isnan(values)
    count = 0
    running_sum = 0.0
    for i in range(len(values)):
        if valid[i]:
            running_sum += values[i]
            count += 1
            if count > period:
                j = i - period
                while j >= 0 and not valid[j]:
                    j -= 1
                if j >= 0:
                    running_sum -= values[j]
                    count -= 1
            if count >= period:
                result[i] = running_sum / period
    return result


def calc_sar(highs, lows, af_start, af_step, af_max):
    n = len(highs)
    sar = np.full(n, np.nan)
    if n < 2:
        return sar
    bull = True
    af = af_start
    ep = highs[0]
    sar[0] = lows[0]
    for i in range(1, n):
        prev_sar = sar[i - 1] if not np.isnan(sar[i - 1]) else lows[i - 1]
        sar_val = prev_sar + af * (ep - prev_sar)
        if bull:
            sar_val = min(sar_val, lows[i - 1])
            if i >= 2 and not np.isnan(sar[i - 2]):
                sar_val = min(sar_val, lows[i - 2])
            if sar_val > lows[i]:
                bull = False
                sar_val = ep
                ep = lows[i]
                af = af_start
            else:
                if highs[i] > ep:
                    ep = highs[i]
                    af = min(af + af_step, af_max)
        else:
            sar_val = max(sar_val, highs[i - 1])
            if i >= 2 and not np.isnan(sar[i - 2]):
                sar_val = max(sar_val, highs[i - 2])
            if sar_val < highs[i]:
                bull = True
                sar_val = ep
                ep = highs[i]
                af = af_start
            else:
                if lows[i] < ep:
                    ep = lows[i]
                    af = min(af + af_step, af_max)
        sar[i] = sar_val
    return sar


def get_symbol_timeframe_pairs(conn):
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT symbol, timeframe FROM ohlcv ORDER BY symbol, timeframe")
    pairs = cur.fetchall()
    cur.close()
    return pairs


def calculate_and_update(conn, symbol, timeframe):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT time, open, high, low, close, volume FROM ohlcv "
        "WHERE symbol = %s AND timeframe = %s ORDER BY time ASC",
        (symbol, timeframe),
    )
    rows = cur.fetchall()
    if not rows:
        cur.close()
        return 0

    closes = np.array([float(r["close"]) for r in rows])
    highs = np.array([float(r["high"]) for r in rows])
    lows = np.array([float(r["low"]) for r in rows])

    ema9 = calc_ema(closes, 9)
    ema20 = calc_ema(closes, 20)
    ema50 = calc_ema(closes, 50)
    ema100 = calc_ema(closes, 100)
    ema200 = calc_ema(closes, 200)
    sar015 = calc_sar(highs, lows, 0.015, 0.015, 0.12)
    sar020 = calc_sar(highs, lows, 0.02, 0.02, 0.2)
    rsi14 = calc_rsi(closes, 14)
    rsi7 = calc_rsi(closes, 7)
    rsi_ma14 = calc_sma(rsi14, 14)

    update_cur = conn.cursor()
    count = 0
    for i, row in enumerate(rows):
        vals = {
            "ema_9": None if np.isnan(ema9[i]) else round(float(ema9[i]), 6),
            "ema_20": None if np.isnan(ema20[i]) else round(float(ema20[i]), 6),
            "ema_50": None if np.isnan(ema50[i]) else round(float(ema50[i]), 6),
            "ema_100": None if np.isnan(ema100[i]) else round(float(ema100[i]), 6),
            "ema_200": None if np.isnan(ema200[i]) else round(float(ema200[i]), 6),
            "sar_015": None if np.isnan(sar015[i]) else round(float(sar015[i]), 6),
            "sar_020": None if np.isnan(sar020[i]) else round(float(sar020[i]), 6),
            "rsi_14": None if np.isnan(rsi14[i]) else round(float(rsi14[i]), 4),
            "rsi_7": None if np.isnan(rsi7[i]) else round(float(rsi7[i]), 4),
            "rsi_ma_14": None if np.isnan(rsi_ma14[i]) else round(float(rsi_ma14[i]), 4),
        }
        update_cur.execute("""
            UPDATE ohlcv SET
                ema_9=%s, ema_20=%s, ema_50=%s, ema_100=%s, ema_200=%s,
                sar_015=%s, sar_020=%s, rsi_14=%s, rsi_7=%s, rsi_ma_14=%s
            WHERE time=%s AND symbol=%s AND timeframe=%s
        """, (vals["ema_9"], vals["ema_20"], vals["ema_50"], vals["ema_100"],
              vals["ema_200"], vals["sar_015"], vals["sar_020"],
              vals["rsi_14"], vals["rsi_7"], vals["rsi_ma_14"],
              row["time"], symbol, timeframe))
        count += 1

    conn.commit()
    update_cur.close()
    cur.close()
    return count


def run_cycle():
    conn = get_db()
    pairs = get_symbol_timeframe_pairs(conn)
    total = 0
    for symbol, timeframe in pairs:
        count = calculate_and_update(conn, symbol, timeframe)
        if count > 0:
            log.info(f"  {symbol} {timeframe}: {count} rows updated")
            total += count
    conn.close()
    return total


if __name__ == "__main__":
    log.info("Starting indicator calculator...")
    while True:
        try:
            total = run_cycle()
            if total > 0:
                log.info(f"Cycle done: {total} rows updated")
        except Exception as e:
            log.error(f"Cycle error: {e}")
        time.sleep(INTERVAL)
