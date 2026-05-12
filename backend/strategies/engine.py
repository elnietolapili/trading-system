"""
Strategy Runner v2 — core backtesting engine.
Long/Short/Hedge, walk-forward, performance metrics.
Uses Feature Engineering as library (in-memory, no HTTP).
"""

import os, sys, time, json, logging
import tracemalloc
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import psycopg2
import psycopg2.extras

# Import indicators library directly
INDICATORS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "indicators")
if INDICATORS_PATH not in sys.path:
    sys.path.insert(0, INDICATORS_PATH)

from lib.compute_engine import ComputeEngine
from lib.session_cache import SessionCache
from plugin_registry import registry

DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "trading")
DB_USER = os.getenv("DB_USER", "trading")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")

log = logging.getLogger("strategy.engine")


def get_db():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                            user=DB_USER, password=DB_PASSWORD)


# ── Data Loading ───────────────────────────────────────────────

def load_candles(symbol, timeframe, start=None, end=None):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    q = "SELECT time,open,high,low,close,volume FROM ohlcv WHERE symbol=%s AND timeframe=%s"
    p = [symbol, timeframe]
    if start: q += " AND time >= %s"; p.append(start)
    if end: q += " AND time <= %s"; p.append(end)
    q += " ORDER BY time ASC"
    cur.execute(q, p)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def candles_to_arrays(candles):
    c = np.array([float(x["close"]) for x in candles])
    h = np.array([float(x["high"]) for x in candles])
    l = np.array([float(x["low"]) for x in candles])
    v = np.array([float(x["volume"]) for x in candles])
    o = np.array([float(x["open"]) for x in candles])
    return o, h, l, c, v


# ── Indicator Resolution ───────────────────────────────────────

INDICATOR_MAP = {
    "ema_9": {"name": "ema", "params": {"period": 9}},
    "ema_20": {"name": "ema", "params": {"period": 20}},
    "ema_50": {"name": "ema", "params": {"period": 50}},
    "ema_100": {"name": "ema", "params": {"period": 100}},
    "ema_200": {"name": "ema", "params": {"period": 200}},
    "rsi_14": {"name": "rsi", "params": {"period": 14}},
    "rsi_7": {"name": "rsi", "params": {"period": 7}},
    "rsi_ma_14": {"name": "rsi_ma", "params": {"rsi_period": 14, "ma_period": 14}},
    "sar_015": {"name": "sar", "params": {"af_start": 0.015, "af_step": 0.015, "af_max": 0.12}},
    "sar_020": {"name": "sar", "params": {"af_start": 0.02, "af_step": 0.02, "af_max": 0.2}},
}

LEGACY_TO_COMPUTED = {
    "ema_9": "ema_9", "ema_20": "ema_20", "ema_50": "ema_50",
    "ema_100": "ema_100", "ema_200": "ema_200",
    "rsi_14": "rsi_14", "rsi_7": "rsi_7",
    "rsi_ma_14": "rsi_ma_14_14",
    "sar_015": "sar_0.015_0.015_0.12",
    "sar_020": "sar_0.02_0.02_0.2",
}


def resolve_indicators(rules):
    needed, seen = [], set()
    for rule in (rules or []):
        for field in ["indicator", "value"]:
            key = rule.get(field, "")
            if isinstance(key, str) and key in INDICATOR_MAP and key not in seen:
                needed.append(INDICATOR_MAP[key]); seen.add(key)
    return needed


def compute_all(candles, entry_rules, exit_rules, engine, symbol, timeframe):
    opens, highs, lows, closes, volumes = candles_to_arrays(candles)
    requests = resolve_indicators((entry_rules or []) + (exit_rules or []))
    computed = engine.compute_batch(requests, closes, highs, lows, volumes, symbol, timeframe)
    computed.update({"close": closes, "open": opens, "high": highs, "low": lows, "volume": volumes})
    for legacy, comp_key in LEGACY_TO_COMPUTED.items():
        if comp_key in computed and legacy not in computed:
            computed[legacy] = computed[comp_key]
    return computed


# ── Rule Evaluation ────────────────────────────────────────────

def get_val(data, key, idx):
    if key in data:
        v = data[key][idx]
        if isinstance(v, (int, float, np.floating)) and not np.isnan(v):
            return float(v)
    try: return float(key)
    except: return None


def eval_rules(rules, data, i, prev):
    if not rules: return False
    for r in rules:
        ind, op, val = r["indicator"], r["operator"], r["value"]
        cv = get_val(data, ind, i)
        pv = get_val(data, ind, prev)
        cc = get_val(data, val, i) if isinstance(val, str) else float(val)
        pc = get_val(data, val, prev) if isinstance(val, str) else float(val)
        if cv is None or cc is None: return False
        if op == "crosses_above":
            if pv is None or pc is None or not (pv <= pc and cv > cc): return False
        elif op == "crosses_below":
            if pv is None or pc is None or not (pv >= pc and cv < cc): return False
        elif op == "greater_than":
            if not (cv > cc): return False
        elif op == "less_than":
            if not (cv < cc): return False
        elif op == "sar_below_price":
            if not (cv < data["close"][i]): return False
        elif op == "sar_above_price":
            if not (cv > data["close"][i]): return False
        else: return False
    return True


# ── Core Backtest ──────────────────────────────────────────────

def backtest_single(candles, data, entry_rules, exit_rules, direction="long",
                    sl=None, tp=None, size=100):
    n = len(candles)
    trades, eq_curve = [], []
    equity, in_pos, entry_price, entry_idx = size, False, 0.0, 0

    for i in range(1, n):
        if not in_pos:
            if eval_rules(entry_rules, data, i, i-1):
                in_pos, entry_price, entry_idx = True, float(candles[i]["close"]), i
        else:
            close = float(candles[i]["close"])
            pnl_pct = ((close - entry_price) / entry_price * 100) if direction == "long" \
                      else ((entry_price - close) / entry_price * 100)

            exit_sig = eval_rules(exit_rules, data, i, i-1)
            hit_sl = sl and pnl_pct <= -sl
            hit_tp = tp and pnl_pct >= tp

            if exit_sig or hit_sl or hit_tp or i == n-1:
                pnl = size * pnl_pct / 100
                equity += pnl
                reason = "stop_loss" if hit_sl else ("take_profit" if hit_tp else
                         ("end_of_data" if i == n-1 else "signal"))
                trades.append({
                    "entry_time": candles[entry_idx]["time"],
                    "exit_time": candles[i]["time"],
                    "entry_price": entry_price, "exit_price": close,
                    "direction": direction,
                    "pnl": round(pnl, 4), "pnl_pct": round(pnl_pct, 4),
                    "exit_reason": reason,
                })
                in_pos = False
        eq_curve.append({"time": candles[i]["time"], "equity": round(equity, 4)})

    return {"trades": trades, "equity_curve": eq_curve, "final_equity": equity}


def calc_metrics(trades, eq_curve, size, n_candles, duration, mem_mb):
    if not trades:
        return {"total_trades": 0, "winning_trades": 0, "losing_trades": 0,
                "win_rate": 0, "total_pnl": 0, "pnl_pct": 0, "avg_pnl": 0,
                "profit_factor": 0, "max_drawdown": 0, "sharpe_ratio": 0,
                "final_equity": size, "candles_processed": n_candles,
                "duration_seconds": duration, "memory_peak_mb": mem_mb,
                "candles_per_second": n_candles / max(0.001, duration)}

    win = [t for t in trades if t["pnl"] > 0]
    lose = [t for t in trades if t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in trades)
    gp = sum(t["pnl"] for t in win)
    gl = abs(sum(t["pnl"] for t in lose))

    peak, max_dd = size, 0
    for pt in eq_curve:
        eq = pt["equity"]
        if eq > peak: peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd: max_dd = dd

    rets = [t["pnl_pct"] for t in trades]
    sharpe = (np.mean(rets) / np.std(rets) * np.sqrt(252)) if len(rets) > 1 and np.std(rets) > 0 else 0

    return {
        "total_trades": len(trades), "winning_trades": len(win), "losing_trades": len(lose),
        "win_rate": round(len(win)/len(trades)*100, 2),
        "total_pnl": round(total_pnl, 4), "pnl_pct": round(total_pnl/size*100, 2),
        "avg_pnl": round(total_pnl/len(trades), 4),
        "profit_factor": round(gp/gl, 4) if gl > 0 else 999,
        "max_drawdown": round(max_dd, 4), "sharpe_ratio": round(sharpe, 4),
        "final_equity": round(size + total_pnl, 4),
        "candles_processed": n_candles,
        "duration_seconds": round(duration, 4), "memory_peak_mb": round(mem_mb, 2),
        "candles_per_second": round(n_candles / max(0.001, duration), 0),
    }


# ── Walk-Forward ───────────────────────────────────────────────

def walk_forward_split(candles, train_pct=0.75, window_pct=0.25, step_pct=0.125):
    n = len(candles)
    train_sz = int(n * train_pct)
    win_sz = int(n * window_pct)
    step_sz = max(1, int(n * step_pct))
    splits, start = [], 0
    while start + train_sz + win_sz <= n:
        splits.append((candles[start:start+train_sz], candles[start+train_sz:start+train_sz+win_sz]))
        start += step_sz
    if not splits:
        mid = n // 2
        splits.append((candles[:mid], candles[mid:]))
    return splits


# ── Main Entry Point ──────────────────────────────────────────

def run_backtest(symbol, timeframe, entry_rules, exit_rules,
                 direction="long", stop_loss_pct=None, take_profit_pct=None,
                 position_size=100, start=None, end=None,
                 backtest_type="simple", strategy_id=None, cache=None):
    tracemalloc.start()
    t0 = time.time()

    candles = load_candles(symbol, timeframe, start, end)
    if not candles:
        tracemalloc.stop()
        return {"error": "No data", "trades": [], "metrics": {}, "equity_curve": []}

    engine = ComputeEngine(cache=cache or SessionCache())
    data = compute_all(candles, entry_rules, exit_rules, engine, symbol, timeframe)

    # Collect indicator versions
    reqs = resolve_indicators((entry_rules or []) + (exit_rules or []))
    ind_versions = {}
    for rq in reqs:
        meta = engine.get_indicator_metadata(rq["name"], rq.get("params", {}))
        if meta: ind_versions[f"{meta['name']}_{meta['params_hash']}"] = meta["version"]

    # Execute
    if backtest_type == "walk_forward":
        result = _walk_forward(candles, data, entry_rules, exit_rules,
                               direction, stop_loss_pct, take_profit_pct, position_size)
    elif direction == "hedge":
        long_r = backtest_single(candles, data, entry_rules, exit_rules, "long",
                                 stop_loss_pct, take_profit_pct, position_size/2)
        short_r = backtest_single(candles, data, exit_rules, entry_rules, "short",
                                  stop_loss_pct, take_profit_pct, position_size/2)
        trades = sorted(long_r["trades"] + short_r["trades"], key=lambda t: str(t["entry_time"]))
        eq = _merge_eq(long_r["equity_curve"], short_r["equity_curve"])
        result = {"trades": trades, "equity_curve": eq}
    else:
        result = backtest_single(candles, data, entry_rules, exit_rules,
                                 direction, stop_loss_pct, take_profit_pct, position_size)

    duration = time.time() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    metrics = calc_metrics(result["trades"], result["equity_curve"],
                           position_size, len(candles), duration, peak/1024/1024)

    output = {
        "trades": result["trades"], "equity_curve": result["equity_curve"],
        "metrics": metrics, "indicator_versions": ind_versions,
        "backtest_type": backtest_type,
        "cache_stats": engine.cache.stats if engine.cache else {},
    }

    if strategy_id:
        _save_results(strategy_id, symbol, timeframe, metrics, result["trades"],
                      result["equity_curve"], ind_versions, entry_rules, exit_rules,
                      stop_loss_pct, take_profit_pct, position_size, direction,
                      backtest_type, candles)

    return output


def _walk_forward(candles, data, entry_rules, exit_rules, direction, sl, tp, size):
    splits = walk_forward_split(candles)
    all_trades, all_eq = [], []
    for train, test in splits:
        # Find test start index in full data
        test_start = next((j for j, c in enumerate(candles) if c["time"] == test[0]["time"]), 0)
        test_n = len(test)
        test_data = {k: arr[test_start:test_start+test_n] for k, arr in data.items()}

        if direction == "hedge":
            lr = backtest_single(test, test_data, entry_rules, exit_rules, "long", sl, tp, size/2)
            sr = backtest_single(test, test_data, exit_rules, entry_rules, "short", sl, tp, size/2)
            all_trades.extend(lr["trades"] + sr["trades"])
            all_eq.extend(_merge_eq(lr["equity_curve"], sr["equity_curve"]))
        else:
            r = backtest_single(test, test_data, entry_rules, exit_rules, direction, sl, tp, size)
            all_trades.extend(r["trades"])
            all_eq.extend(r["equity_curve"])
    return {"trades": all_trades, "equity_curve": all_eq}


def _merge_eq(a, b):
    if not a or not b: return a or b
    return [{"time": a[i]["time"], "equity": round(a[i]["equity"]+b[i]["equity"], 4)}
            for i in range(min(len(a), len(b)))]


# ── DB Persistence ─────────────────────────────────────────────

def _save_results(strategy_id, symbol, timeframe, metrics, trades, eq_curve,
                  ind_versions, entry_rules, exit_rules, sl, tp, size,
                  direction, bt_type, candles):
    conn = get_db()
    cur = conn.cursor()

    params_used = {"entry_rules": entry_rules, "exit_rules": exit_rules,
                   "stop_loss_pct": sl, "take_profit_pct": tp,
                   "position_size": size, "direction": direction}

    cur.execute("""
        INSERT INTO backtest_results
            (strategy_id, pnl_total, pnl_pct, win_rate, max_drawdown,
             profit_factor, sharpe_ratio, num_trades, symbol, timeframe,
             date_from, date_to, indicator_versions, params_used,
             backtest_type, duration_seconds, memory_peak_mb,
             candles_processed, candles_per_second)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (strategy_id, metrics["total_pnl"], metrics["pnl_pct"],
          metrics["win_rate"], metrics["max_drawdown"],
          metrics["profit_factor"], metrics["sharpe_ratio"],
          metrics["total_trades"], symbol, timeframe,
          candles[0]["time"], candles[-1]["time"],
          json.dumps(ind_versions), json.dumps(params_used),
          bt_type, metrics["duration_seconds"], metrics["memory_peak_mb"],
          metrics["candles_processed"], metrics["candles_per_second"]))
    bt_id = cur.fetchone()[0]

    for t in trades:
        cur.execute("""
            INSERT INTO backtest_trades
                (backtest_id, entry_time, exit_time, entry_price, exit_price,
                 direction, pnl, pnl_pct, exit_reason)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (bt_id, t["entry_time"], t["exit_time"], t["entry_price"],
              t["exit_price"], t["direction"], t["pnl"], t["pnl_pct"], t["exit_reason"]))

    if eq_curve:
        step = max(1, len(eq_curve) // 500)
        for i in range(0, len(eq_curve), step):
            cur.execute("INSERT INTO backtest_equity (backtest_id,time,equity_value) VALUES (%s,%s,%s)",
                        (bt_id, eq_curve[i]["time"], eq_curve[i]["equity"]))

    conn.commit()
    # Cleanup: keep last 20 non-favorites per strategy
    cur.execute("""DELETE FROM backtest_results WHERE id IN (
        SELECT id FROM backtest_results WHERE strategy_id=%s AND is_favorite=FALSE
        ORDER BY created_at DESC OFFSET 20)""", (strategy_id,))
    conn.commit()
    cur.close(); conn.close()
    log.info(f"Saved backtest {bt_id}: {metrics['total_trades']} trades")
    return bt_id
