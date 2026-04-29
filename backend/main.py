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
    limit: int = Query(500, description="Máximo de filas", ge=1, le=10000),
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
