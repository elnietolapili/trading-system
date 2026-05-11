"""
Backtest engine v1 — evaluates entry/exit rules against OHLCV data.
This will be rewritten in Phase 4 with long/short/hedge, walk-forward, etc.
"""

import os
import psycopg2
import psycopg2.extras

DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "trading")
DB_USER = os.getenv("DB_USER", "trading")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")


def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
    )


def run_backtest(symbol, timeframe, entry_rules, exit_rules,
                 stop_loss_pct=None, take_profit_pct=None, position_size=100):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM ohlcv WHERE symbol = %s AND timeframe = %s ORDER BY time ASC",
        (symbol, timeframe),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        return {"error": "No data", "trades": [], "metrics": {}, "equity_curve": []}

    candles = [dict(r) for r in rows]
    trades = []
    equity_curve = []
    equity = position_size
    in_position = False
    entry_price = 0
    entry_time = None

    for i in range(1, len(candles)):
        prev = candles[i - 1]
        curr = candles[i]

        if not in_position:
            if evaluate_rules(entry_rules, prev, curr):
                in_position = True
                entry_price = curr["close"]
                entry_time = curr["time"]
        else:
            close = curr["close"]
            pnl_pct = (close - entry_price) / entry_price * 100

            exit_signal = evaluate_rules(exit_rules, prev, curr)
            hit_sl = stop_loss_pct and pnl_pct <= -stop_loss_pct
            hit_tp = take_profit_pct and pnl_pct >= take_profit_pct

            if exit_signal or hit_sl or hit_tp:
                pnl = position_size * pnl_pct / 100
                equity += pnl

                reason = "signal"
                if hit_sl:
                    reason = "stop_loss"
                elif hit_tp:
                    reason = "take_profit"

                trades.append({
                    "entry_time": str(entry_time),
                    "exit_time": str(curr["time"]),
                    "entry_price": float(entry_price),
                    "exit_price": float(close),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "exit_reason": reason,
                })
                in_position = False

        equity_curve.append({
            "time": str(curr["time"]),
            "equity": round(equity, 2),
        })

    winning = [t for t in trades if t["pnl"] > 0]
    losing = [t for t in trades if t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in trades)
    gross_profit = sum(t["pnl"] for t in winning)
    gross_loss = abs(sum(t["pnl"] for t in losing))

    metrics = {
        "total_trades": len(trades),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": round(len(winning) / len(trades) * 100, 1) if trades else 0,
        "total_pnl": round(total_pnl, 2),
        "avg_pnl": round(total_pnl / len(trades), 2) if trades else 0,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else 999,
        "max_drawdown": round(calculate_max_drawdown(equity_curve), 2),
        "final_equity": round(equity, 2),
        "candles_analyzed": len(candles),
    }

    return {"trades": trades, "metrics": metrics, "equity_curve": equity_curve}


def evaluate_rules(rules, prev, curr):
    if not rules:
        return False
    for rule in rules:
        indicator = rule["indicator"]
        operator = rule["operator"]
        value = rule["value"]

        curr_val = get_indicator_value(curr, indicator)
        prev_val = get_indicator_value(prev, indicator)
        compare_val = get_indicator_value(curr, value) if isinstance(value, str) else float(value)
        prev_compare = get_indicator_value(prev, value) if isinstance(value, str) else float(value)

        if curr_val is None or compare_val is None:
            return False

        if operator == "crosses_above":
            if not (prev_val is not None and prev_val <= prev_compare and curr_val > compare_val):
                return False
        elif operator == "crosses_below":
            if not (prev_val is not None and prev_val >= prev_compare and curr_val < compare_val):
                return False
        elif operator == "greater_than":
            if not (curr_val > compare_val):
                return False
        elif operator == "less_than":
            if not (curr_val < compare_val):
                return False
        elif operator == "sar_below_price":
            sar_val = get_indicator_value(curr, indicator)
            if not (sar_val is not None and ssar_val < curr["close"]):
                return False
        elif operator == "sar_above_price":
            sar_val = get_indicator_value(curr, indicator)
            if not (sar_val is not None and sar_val > curr["close"]):
                return False
        else:
            return False
    return True


def get_indicator_value(candle, key):
    if key in candle and candle[key] is not None:
        return float(candle[key])
    return None


def calculate_max_drawdown(equity_curve):
    if not equity_curve:
        return 0
    peak = equity_curve[0]["equity"]
    max_dd = 0
    for point in equity_curve:
        eq = point["equity"]
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd
    return max_dd
