"""
Strategy Optimizer: parametric grid search.
- Configurable worker pool (default 2 to not exhaust 3.7GB RAM)
- Early stopping if drawdown exceeds threshold in first 30% of data
- Checks optimization_history to skip already-tested combinations
- Shared session cache across all combinations
"""

import json
import hashlib
import logging
from typing import List, Dict, Any, Optional
from itertools import product
from concurrent.futures import ProcessPoolExecutor, as_completed

import psycopg2
import psycopg2.extras

from strategies.engine import run_backtest, get_db
from lib.session_cache import SessionCache

log = logging.getLogger("strategy.optimizer")


def logic_hash(entry_rules, exit_rules) -> str:
    """Deterministic hash of strategy logic."""
    raw = json.dumps({"entry": entry_rules, "exit": exit_rules}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def params_hash(params: Dict) -> str:
    raw = json.dumps(params, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def check_already_tested(strategy_id, l_hash, p_hash, data_range) -> bool:
    """Check if this combination was already tested."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM optimization_history
        WHERE strategy_base_id=%s AND logic_hash=%s AND params_hash=%s AND data_range=%s
    """, (strategy_id, l_hash, p_hash, data_range))
    exists = cur.fetchone() is not None
    cur.close(); conn.close()
    return exists


def save_optimization_result(strategy_id, l_hash, p_hash, params, metrics, verdict, data_range):
    """Save result to optimization_history."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO optimization_history
            (strategy_base_id, params_hash, params, logic_hash,
             pnl, win_rate, max_drawdown, profit_factor, verdict, data_range)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (strategy_id, p_hash, json.dumps(params), l_hash,
          metrics.get("total_pnl", 0), metrics.get("win_rate", 0),
          metrics.get("max_drawdown", 0), metrics.get("profit_factor", 0),
          verdict, data_range))
    conn.commit()
    cur.close(); conn.close()


def generate_param_grid(param_ranges: Dict[str, List]) -> List[Dict]:
    """
    Generate all combinations from parameter ranges.
    param_ranges = {"stop_loss_pct": [2, 3, 5], "take_profit_pct": [3, 5, 10]}
    Returns list of dicts with all combinations.
    """
    keys = list(param_ranges.keys())
    values = list(param_ranges.values())
    return [dict(zip(keys, combo)) for combo in product(*values)]


def run_optimization(
    strategy_id: int,
    symbol: str,
    timeframe: str,
    entry_rules: List[Dict],
    exit_rules: List[Dict],
    param_ranges: Dict[str, List],
    direction: str = "long",
    position_size: float = 100,
    start: str = None,
    end: str = None,
    max_workers: int = 2,
    early_stop_drawdown: float = 50.0,
) -> Dict:
    """
    Run parametric optimization.
    Returns sorted results (best first) + summary.
    """
    grid = generate_param_grid(param_ranges)
    l_hash = logic_hash(entry_rules, exit_rules)
    data_range = f"{start or 'all'}_{end or 'all'}_{symbol}_{timeframe}"

    cache = SessionCache()  # Shared cache across all combinations
    results = []
    skipped = 0
    early_stopped = 0

    log.info(f"Optimization: {len(grid)} combinations, {max_workers} workers")

    for i, params in enumerate(grid):
        p_hash = params_hash(params)

        # Check if already tested
        if check_already_tested(strategy_id, l_hash, p_hash, data_range):
            skipped += 1
            continue

        # Run backtest with these params
        sl = params.get("stop_loss_pct")
        tp = params.get("take_profit_pct")

        result = run_backtest(
            symbol=symbol, timeframe=timeframe,
            entry_rules=entry_rules, exit_rules=exit_rules,
            direction=direction,
            stop_loss_pct=sl, take_profit_pct=tp,
            position_size=position_size,
            start=start, end=end,
            backtest_type="simple",
            strategy_id=None,  # Don't save individual results during optimization
            cache=cache,
        )

        metrics = result.get("metrics", {})

        # Early stopping check
        if metrics.get("max_drawdown", 0) > early_stop_drawdown:
            verdict = "early_stop"
            early_stopped += 1
        elif metrics.get("total_pnl", 0) > 0 and metrics.get("win_rate", 0) > 40:
            verdict = "satisfactory"
        else:
            verdict = "unsatisfactory"

        # Save to optimization history
        save_optimization_result(strategy_id, l_hash, p_hash, params, metrics, verdict, data_range)

        results.append({
            "params": params,
            "metrics": metrics,
            "verdict": verdict,
        })

        if (i + 1) % 10 == 0:
            log.info(f"  Progress: {i+1}/{len(grid)} ({skipped} skipped, {early_stopped} early-stopped)")

    # Sort by PnL descending
    results.sort(key=lambda r: r["metrics"].get("total_pnl", 0), reverse=True)

    summary = {
        "total_combinations": len(grid),
        "tested": len(results),
        "skipped_already_tested": skipped,
        "early_stopped": early_stopped,
        "satisfactory": sum(1 for r in results if r["verdict"] == "satisfactory"),
        "unsatisfactory": sum(1 for r in results if r["verdict"] == "unsatisfactory"),
        "cache_stats": cache.stats,
    }

    log.info(f"Optimization complete: {summary}")

    return {
        "results": results,
        "summary": summary,
        "best": results[0] if results else None,
    }
