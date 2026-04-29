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

    query += " ORDER BY time ASC LIMIT %s"
    params.append(limit)

    cur.execute(query, params)
    rows = cur.fetchall()

    # Convertir timestamps a string ISO
    candles = []
    for row in rows:
        candle = dict(row)
        candle["time"] = candle["time"].isoformat()
        candles.append(candle)

    cur.close()
    conn.close()

    return {"symbol": symbol, "timeframe": timeframe, "count": len(candles), "candles": candles}
