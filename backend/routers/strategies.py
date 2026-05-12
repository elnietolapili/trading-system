from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
import json
from database import get_cursor
from strategies.engine import run_backtest

router = APIRouter()


class RuleModel(BaseModel):
    indicator: str
    operator: str
    value: str | float | int


class StrategyCreate(BaseModel):
    name: str
    symbol: str
    timeframe: str
    entry_rules: List[RuleModel]
    exit_rules: List[RuleModel]
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    position_size: float = 100
    collection_id: Optional[int] = None


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    entry_rules: Optional[List[RuleModel]] = None
    exit_rules: Optional[List[RuleModel]] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    position_size: Optional[float] = None
    collection_id: Optional[int] = None


@router.get("/strategies")
def list_strategies():
    with get_cursor() as (conn, cur):
        cur.execute("""
            SELECT id, name, symbol, timeframe, entry_rules, exit_rules,
                   stop_loss_pct, take_profit_pct, position_size,
                   collection_id, last_backtest, backtest_at,
                   active, created_at, updated_at
            FROM strategies ORDER BY updated_at DESC
        """)
        rows = cur.fetchall()
    result = []
    for r in rows:
        s = dict(r)
        s["created_at"] = s["created_at"].isoformat()
        s["updated_at"] = s["updated_at"].isoformat()
        if s.get("backtest_at"):
            s["backtest_at"] = s["backtest_at"].isoformat()
        result.append(s)
    return {"strategies": result}


@router.post("/strategies")
def create_strategy(s: StrategyCreate):
    entry = [r.model_dump() for r in s.entry_rules]
    exit_ = [r.model_dump() for r in s.exit_rules]
    with get_cursor(dict_cursor=False) as (conn, cur):
        cur.execute(
            """INSERT INTO strategies
               (name, symbol, timeframe, entry_rules, exit_rules,
                stop_loss_pct, take_profit_pct, position_size, collection_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (s.name, s.symbol, s.timeframe,
             json.dumps(entry), json.dumps(exit_),
             s.stop_loss_pct, s.take_profit_pct, s.position_size, s.collection_id),
        )
        sid = cur.fetchone()[0]
    return {"id": sid, "name": s.name, "status": "created"}


@router.put("/strategies/{strategy_id}")
def update_strategy(strategy_id: int, s: StrategyUpdate):
    updates, params = [], []
    if s.name is not None:
        updates.append("name = %s"); params.append(s.name)
    if s.entry_rules is not None:
        updates.append("entry_rules = %s")
        params.append(json.dumps([r.model_dump() for r in s.entry_rules]))
    if s.exit_rules is not None:
        updates.append("exit_rules = %s")
        params.append(json.dumps([r.model_dump() for r in s.exit_rules]))
    if s.stop_loss_pct is not None:
        updates.append("stop_loss_pct = %s"); params.append(s.stop_loss_pct)
    if s.take_profit_pct is not None:
        updates.append("take_profit_pct = %s"); params.append(s.take_profit_pct)
    if s.position_size is not None:
        updates.append("position_size = %s"); params.append(s.position_size)
    if s.collection_id is not None:
        updates.append("collection_id = %s"); params.append(s.collection_id)
    if updates:
        updates.append("updated_at = NOW()")
        params.append(strategy_id)
        with get_cursor(dict_cursor=False) as (conn, cur):
            cur.execute(f"UPDATE strategies SET {', '.join(updates)} WHERE id = %s", params)
    return {"id": strategy_id, "status": "updated"}


@router.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: int):
    with get_cursor(dict_cursor=False) as (conn, cur):
        cur.execute("DELETE FROM strategies WHERE id = %s", (strategy_id,))
    return {"id": strategy_id, "status": "deleted"}


class BacktestRequest(BaseModel):
    direction: str = "long"  # long, short, hedge
    backtest_type: str = "simple"  # simple, walk_forward
    start: Optional[str] = None
    end: Optional[str] = None


class OptimizeRequest(BaseModel):
    param_ranges: dict  # {"stop_loss_pct": [2,3,5], "take_profit_pct": [3,5,10]}
    direction: str = "long"
    start: Optional[str] = None
    end: Optional[str] = None
    max_workers: int = 2
    early_stop_drawdown: float = 50.0


@router.post("/strategies/{strategy_id}/backtest")
def backtest_strategy(strategy_id: int, req: BacktestRequest = None):
    if req is None:
        req = BacktestRequest()

    with get_cursor() as (conn, cur):
        cur.execute("SELECT * FROM strategies WHERE id = %s", (strategy_id,))
        row = cur.fetchone()
        if not row:
            return {"error": "Strategy not found"}
        strategy = dict(row)

    entry_rules = strategy["entry_rules"]
    exit_rules = strategy["exit_rules"]
    if isinstance(entry_rules, str):
        entry_rules = json.loads(entry_rules)
    if isinstance(exit_rules, str):
        exit_rules = json.loads(exit_rules)

    result = run_backtest(
        symbol=strategy["symbol"],
        timeframe=strategy["timeframe"],
        entry_rules=entry_rules,
        exit_rules=exit_rules,
        direction=req.direction,
        stop_loss_pct=strategy.get("stop_loss_pct"),
        take_profit_pct=strategy.get("take_profit_pct"),
        position_size=strategy.get("position_size", 100),
        start=req.start,
        end=req.end,
        backtest_type=req.backtest_type,
        strategy_id=strategy_id,
    )

    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy["name"],
        "symbol": strategy["symbol"],
        "timeframe": strategy["timeframe"],
        "result": result,
    }


@router.post("/strategies/{strategy_id}/optimize")
def optimize_strategy(strategy_id: int, req: OptimizeRequest):
    from strategies.optimizer import run_optimization

    with get_cursor() as (conn, cur):
        cur.execute("SELECT * FROM strategies WHERE id = %s", (strategy_id,))
        row = cur.fetchone()
        if not row:
            return {"error": "Strategy not found"}
        strategy = dict(row)

    entry_rules = strategy["entry_rules"]
    exit_rules = strategy["exit_rules"]
    if isinstance(entry_rules, str):
        entry_rules = json.loads(entry_rules)
    if isinstance(exit_rules, str):
        exit_rules = json.loads(exit_rules)

    result = run_optimization(
        strategy_id=strategy_id,
        symbol=strategy["symbol"],
        timeframe=strategy["timeframe"],
        entry_rules=entry_rules,
        exit_rules=exit_rules,
        param_ranges=req.param_ranges,
        direction=req.direction,
        position_size=strategy.get("position_size", 100),
        start=req.start,
        end=req.end,
        max_workers=req.max_workers,
        early_stop_drawdown=req.early_stop_drawdown,
    )

    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy["name"],
        "result": result,
    }


@router.get("/strategies/{strategy_id}/results")
def get_backtest_results(strategy_id: int):
    with get_cursor() as (conn, cur):
        cur.execute("""
            SELECT id, pnl_total, pnl_pct, win_rate, max_drawdown, profit_factor,
                   sharpe_ratio, num_trades, timeframe, date_from, date_to,
                   backtest_type, duration_seconds, candles_processed,
                   is_favorite, created_at
            FROM backtest_results WHERE strategy_id = %s
            ORDER BY created_at DESC
        """, (strategy_id,))
        rows = cur.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["created_at"] = d["created_at"].isoformat()
        if d.get("date_from"): d["date_from"] = d["date_from"].isoformat()
        if d.get("date_to"): d["date_to"] = d["date_to"].isoformat()
        results.append(d)
    return {"strategy_id": strategy_id, "results": results}


@router.get("/backtest/{backtest_id}/trades")
def get_backtest_trades(backtest_id: int):
    with get_cursor() as (conn, cur):
        cur.execute("""
            SELECT entry_time, exit_time, entry_price, exit_price,
                   direction, pnl, pnl_pct, exit_reason
            FROM backtest_trades WHERE backtest_id = %s
            ORDER BY entry_time ASC
        """, (backtest_id,))
        rows = cur.fetchall()
    trades = []
    for r in rows:
        t = dict(r)
        t["entry_time"] = t["entry_time"].isoformat()
        if t.get("exit_time"): t["exit_time"] = t["exit_time"].isoformat()
        trades.append(t)
    return {"backtest_id": backtest_id, "trades": trades}


@router.get("/strategies/operators")
def get_operators():
    return {
        "operators": [
            {"id": "crosses_above", "label": "Cruza por encima de"},
            {"id": "crosses_below", "label": "Cruza por debajo de"},
            {"id": "greater_than", "label": "Mayor que"},
            {"id": "less_than", "label": "Menor que"},
            {"id": "sar_below_price", "label": "SAR debajo del precio"},
            {"id": "sar_above_price", "label": "SAR encima del precio"},
        ],
        "indicators": [
            {"id": "close", "label": "Precio cierre"},
            {"id": "open", "label": "Precio apertura"},
            {"id": "high", "label": "Precio máximo"},
            {"id": "low", "label": "Precio mínimo"},
            {"id": "ema_9", "label": "EMA 9"},
            {"id": "ema_20", "label": "EMA 20"},
            {"id": "ema_50", "label": "EMA 50"},
            {"id": "ema_100", "label": "EMA 100"},
            {"id": "ema_200", "label": "EMA 200"},
            {"id": "sar_015", "label": "SAR 0.015"},
            {"id": "sar_020", "label": "SAR 0.020"},
            {"id": "rsi_14", "label": "RSI 14"},
            {"id": "rsi_7", "label": "RSI 7"},
            {"id": "rsi_ma_14", "label": "RSI MA 14"},
        ],
    }
