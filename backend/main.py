"""
Backend básico: lee datos OHLCV de la DB y los expone via API REST.

Endpoints:
    GET /symbols           → lista de símbolos disponibles
    GET /timeframes        → lista de timeframes disponibles
    GET /candles           → velas OHLCV con filtros
    GET /health            → estado del servicio
"""

import os
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

# ── Configuración ──────────────────────────────────────────────

DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "trading")
DB_USER = os.getenv("DB_USER", "trading")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")

app = FastAPI(title="Trading System API")

# Permitir peticiones desde cualquier origen (para el frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Base de datos ──────────────────────────────────────────────

def get_db():
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
    )
    return conn


# ── Endpoints ──────────────────────────────────────────────────

@app.get("/health")
def health():
    """Comprueba que el backend y la DB funcionan."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM ohlcv")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return {"status": "ok", "total_candles": count}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/symbols")
def get_symbols():
    """Lista de símbolos disponibles en la DB."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT symbol FROM ohlcv ORDER BY symbol")
    symbols = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return {"symbols": symbols}


@app.get("/timeframes")
def get_timeframes():
    """Lista de timeframes disponibles en la DB."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT timeframe FROM ohlcv ORDER BY timeframe")
    timeframes = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return {"timeframes": timeframes}


@app.get("/candles")
def get_candles(
    symbol: str = Query(..., description="Ej: ETHUSDT"),
    timeframe: str = Query(..., description="Ej: 1h, 4h, 1D"),
    start: Optional[str] = Query(None, description="Fecha inicio ISO, ej: 2025-01-01"),
    end: Optional[str] = Query(None, description="Fecha fin ISO, ej: 2025-12-31"),
    limit: int = Query(1000000, description="Máximo de filas", ge=1, le=1000000),
):
    """Devuelve velas OHLCV con filtros opcionales de fecha."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    query = "SELECT * FROM ohlcv WHERE symbol = %s AND timeframe = %s"
    params = [symbol, timeframe]

    if start:
        query += " AND time >= %s"
        params.append(start)

    if end:
        query += " AND time <= %s"
        params.append(end)

    query += " ORDER BY time DESC LIMIT %s"
    params.append(limit)

    cur.execute(query, params)
    rows = cur.fetchall()
    rows.reverse()  # Volver a orden cronológico

    # Convertir timestamps a string ISO
    candles = []
    for row in rows:
        candle = dict(row)
        candle["time"] = candle["time"].isoformat()
        candles.append(candle)

    cur.close()
    conn.close()

    return {"symbol": symbol, "timeframe": timeframe, "count": len(candles), "candles": candles}


# ── Endpoints de bots ──────────────────────────────────────────

@app.get("/bots")
def get_bots():
    """Lista de bots con su info básica."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM bots ORDER BY started_at DESC")
    bots = cur.fetchall()

    result = []
    for bot in bots:
        b = dict(bot)
        b["started_at"] = b["started_at"].isoformat()
        result.append(b)

    cur.close()
    conn.close()
    return {"bots": result}


@app.get("/bots/{bot_name}/orders")
def get_bot_orders(
    bot_name: str,
    limit: int = Query(100, ge=1, le=1000),
):
    """Órdenes de un bot, las más recientes primero."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM bot_orders
        WHERE bot_name = %s
        ORDER BY created_at DESC
        LIMIT %s
    """, (bot_name, limit))
    orders = cur.fetchall()

    result = []
    for order in orders:
        o = dict(order)
        o["created_at"] = o["created_at"].isoformat()
        result.append(o)

    cur.close()
    conn.close()
    return {"bot_name": bot_name, "count": len(result), "orders": result}


@app.get("/bots/{bot_name}/stats")
def get_bot_stats(bot_name: str):
    """Estadísticas de un bot: PnL, trades, win rate, etc."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Info del bot
    cur.execute("SELECT * FROM bots WHERE name = %s", (bot_name,))
    bot = cur.fetchone()
    if not bot:
        cur.close()
        conn.close()
        return {"error": "Bot no encontrado"}

    # Estadísticas de órdenes
    cur.execute("""
        SELECT
            count(*) FILTER (WHERE side = 'buy') as total_buys,
            count(*) FILTER (WHERE side = 'sell') as total_sells,
            coalesce(sum(pnl) FILTER (WHERE side = 'sell'), 0) as total_pnl,
            count(*) FILTER (WHERE side = 'sell' AND pnl > 0) as winning_trades,
            count(*) FILTER (WHERE side = 'sell' AND pnl <= 0) as losing_trades,
            coalesce(avg(pnl) FILTER (WHERE side = 'sell'), 0) as avg_pnl,
            coalesce(max(pnl) FILTER (WHERE side = 'sell'), 0) as best_trade,
            coalesce(min(pnl) FILTER (WHERE side = 'sell'), 0) as worst_trade
        FROM bot_orders
        WHERE bot_name = %s
    """, (bot_name,))
    stats = dict(cur.fetchone())

    # Win rate
    total_closed = stats["winning_trades"] + stats["losing_trades"]
    stats["win_rate"] = (stats["winning_trades"] / total_closed * 100) if total_closed > 0 else 0

    # Rentabilidad sobre cartera
    wallet = float(bot["wallet"]) if bot["wallet"] else 0
    stats["wallet"] = wallet
    stats["return_pct"] = (float(stats["total_pnl"]) / wallet * 100) if wallet > 0 else 0
    stats["started_at"] = bot["started_at"].isoformat()
    stats["strategy"] = bot["strategy"]
    stats["params"] = bot["params"]
    stats["symbol"] = bot["symbol"]
    stats["active"] = bot["active"]

    cur.close()
    conn.close()
    return {"bot_name": bot_name, "stats": stats}


# ── Endpoints de estrategias ───────────────────────────────────

from pydantic import BaseModel
from typing import List
import json
from strategies.engine import run_backtest


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
    entry_rules: Optional[List[RuleModel]] = None
    exit_rules: Optional[List[RuleModel]] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    position_size: Optional[float] = None
    collection_id: Optional[int] = None


@app.get("/strategies")
def list_strategies():
    """Lista todas las estrategias guardadas."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, name, symbol, timeframe, entry_rules, exit_rules, stop_loss_pct, take_profit_pct, position_size, active, created_at, updated_at FROM strategies ORDER BY updated_at DESC")
    rows = cur.fetchall()
    result = []
    for r in rows:
        s = dict(r)
        s["created_at"] = s["created_at"].isoformat()
        s["updated_at"] = s["updated_at"].isoformat()
        result.append(s)
    cur.close()
    conn.close()
    return {"strategies": result}


@app.post("/strategies")
def create_strategy(s: StrategyCreate):
    """Crea una nueva estrategia."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO strategies (name, symbol, timeframe, entry_rules, exit_rules,
                                    stop_loss_pct, take_profit_pct, position_size, collection_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            s.name, s.symbol, s.timeframe,
            json.dumps([r.dict() for r in s.entry_rules]),
            json.dumps([r.dict() for r in s.exit_rules]),
            s.stop_loss_pct, s.take_profit_pct, s.position_size, s.collection_id,
        ))
        conn.commit()
        strategy_id = cur.fetchone()[0]
        cur.close()
        conn.close()
        return {"id": strategy_id, "name": s.name, "status": "created"}
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        cur.close()
        conn.close()
        return {"error": "Ya existe una estrategia con ese nombre"}


@app.put("/strategies/{strategy_id}")
def update_strategy(strategy_id: int, s: StrategyUpdate):
    """Actualiza una estrategia existente."""
    conn = get_db()
    cur = conn.cursor()

    updates = []
    params = []

    if s.entry_rules is not None:
        updates.append("entry_rules = %s")
        params.append(json.dumps([r.dict() for r in s.entry_rules]))
    if s.exit_rules is not None:
        updates.append("exit_rules = %s")
        params.append(json.dumps([r.dict() for r in s.exit_rules]))
    if s.stop_loss_pct is not None:
        updates.append("stop_loss_pct = %s")
        params.append(s.stop_loss_pct)
    if s.take_profit_pct is not None:
        updates.append("take_profit_pct = %s")
        params.append(s.take_profit_pct)
    if s.position_size is not None:
        updates.append("position_size = %s")
        params.append(s.position_size)
    if s.collection_id is not None:
        updates.append("collection_id = %s")
        params.append(s.collection_id)

    updates.append("updated_at = NOW()")
    params.append(strategy_id)

    if len(updates) > 1:
        cur.execute(f"UPDATE strategies SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()
    cur.close()
    conn.close()
    return {"id": strategy_id, "status": "updated"}


@app.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: int):
    """Elimina una estrategia."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM strategies WHERE id = %s", (strategy_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"id": strategy_id, "status": "deleted"}


@app.post("/strategies/{strategy_id}/backtest")
def run_strategy_backtest(
    strategy_id: int,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    """Ejecuta backtest de una estrategia y guarda resultados."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Obtener estrategia
    cur.execute("SELECT * FROM strategies WHERE id = %s", (strategy_id,))
    strategy = cur.fetchone()
    if not strategy:
        cur.close()
        conn.close()
        return {"error": "Estrategia no encontrada"}

    # Obtener velas
    query = "SELECT * FROM ohlcv WHERE symbol = %s AND timeframe = %s"
    params = [strategy["symbol"], strategy["timeframe"]]

    if start:
        query += " AND time >= %s"
        params.append(start)
    if end:
        query += " AND time <= %s"
        params.append(end)

    query += " ORDER BY time ASC"
    cur.execute(query, params)
    candles = [dict(r) for r in cur.fetchall()]

    # Convertir timestamps a string para el motor
    for c in candles:
        c["time"] = c["time"].isoformat()

    if len(candles) < 10:
        cur.close()
        conn.close()
        return {"error": "Datos insuficientes para backtest"}

    # Ejecutar backtest
    result = run_backtest(
        candles=candles,
        entry_rules=strategy["entry_rules"],
        exit_rules=strategy["exit_rules"],
        stop_loss_pct=strategy["stop_loss_pct"],
        take_profit_pct=strategy["take_profit_pct"],
        position_size=strategy["position_size"],
    )

    # Guardar resultados en la DB
    cur2 = conn.cursor()
    cur2.execute("""
        UPDATE strategies SET last_backtest = %s, backtest_at = NOW(), updated_at = NOW()
        WHERE id = %s
    """, (json.dumps(result), strategy_id))
    conn.commit()
    cur2.close()

    cur.close()
    conn.close()

    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy["name"],
        "symbol": strategy["symbol"],
        "timeframe": strategy["timeframe"],
        "candles_used": len(candles),
        "result": result,
    }


@app.get("/strategies/operators")
def get_operators():
    """Devuelve los operadores y indicadores disponibles para construir reglas."""
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


# ── Endpoints de colecciones ───────────────────────────────────

class CollectionCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None


@app.get("/collections")
def list_collections():
    """Lista todas las colecciones con sus estrategias."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM collections ORDER BY sort_order, name")
    collections = [dict(r) for r in cur.fetchall()]
    for c in collections:
        c["created_at"] = c["created_at"].isoformat()

    cur.execute("""
        SELECT id, name, symbol, timeframe, entry_rules, exit_rules,
               stop_loss_pct, take_profit_pct, position_size, collection_id,
               active, created_at, updated_at, backtest_at
        FROM strategies ORDER BY name
    """)
    strategies = [dict(r) for r in cur.fetchall()]
    for s in strategies:
        s["created_at"] = s["created_at"].isoformat()
        s["updated_at"] = s["updated_at"].isoformat()
        if s["backtest_at"]:
            s["backtest_at"] = s["backtest_at"].isoformat()

    cur.close()
    conn.close()
    return {"collections": collections, "strategies": strategies}


@app.post("/collections")
def create_collection(c: CollectionCreate):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO collections (name, parent_id) VALUES (%s, %s) RETURNING id",
        (c.name, c.parent_id),
    )
    conn.commit()
    cid = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {"id": cid, "name": c.name, "status": "created"}


@app.put("/collections/{collection_id}")
def update_collection(collection_id: int, c: CollectionUpdate):
    conn = get_db()
    cur = conn.cursor()
    updates, params = [], []
    if c.name is not None:
        updates.append("name = %s"); params.append(c.name)
    if c.parent_id is not None:
        updates.append("parent_id = %s"); params.append(c.parent_id)
    if c.sort_order is not None:
        updates.append("sort_order = %s"); params.append(c.sort_order)
    if updates:
        params.append(collection_id)
        cur.execute(f"UPDATE collections SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()
    cur.close()
    conn.close()
    return {"id": collection_id, "status": "updated"}


@app.delete("/collections/{collection_id}")
def delete_collection(collection_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM collections WHERE id = %s", (collection_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"id": collection_id, "status": "deleted"}
