"""
Feature Engineering HTTP service.
Serves indicator calculations for the Interface (on-the-fly) and Scheduler (persist to Secondary).
The Strategy Runner does NOT use this — it imports the library directly.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, List

import numpy as np
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Query
from pydantic import BaseModel

from plugin_registry import registry
from lib.compute_engine import ComputeEngine

DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "trading")
DB_USER = os.getenv("DB_USER", "trading")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("indicators.service")

app = FastAPI(title="Feature Engineering Service", version="2.0.0")
engine = ComputeEngine()  # No cache for service mode (each request is independent)


def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
    )


def load_ohlcv(symbol: str, timeframe: str, start: str = None, end: str = None):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = "SELECT time, open, high, low, close, volume FROM ohlcv WHERE symbol=%s AND timeframe=%s"
    params = [symbol, timeframe]
    if start:
        query += " AND time >= %s"
        params.append(start)
    if end:
        query += " AND time <= %s"
        params.append(end)
    query += " ORDER BY time ASC"
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


class ComputeRequest(BaseModel):
    symbol: str
    timeframe: str
    indicators: List[dict]  # [{"name": "ema", "params": {"period": 9}}, ...]
    start: Optional[str] = None
    end: Optional[str] = None
    persist: bool = False  # If True, write results to Storage Secondary


@app.get("/health")
def health():
    return {"status": "ok", "plugins": registry.list_names()}


@app.get("/plugins")
def list_plugins():
    return {"plugins": registry.list_all()}


@app.post("/compute")
def compute_indicators(req: ComputeRequest):
    rows = load_ohlcv(req.symbol, req.timeframe, req.start, req.end)
    if not rows:
        return {"error": "No data", "results": {}}

    closes = np.array([float(r["close"]) for r in rows])
    highs = np.array([float(r["high"]) for r in rows])
    lows = np.array([float(r["low"]) for r in rows])
    volumes = np.array([float(r["volume"]) for r in rows])
    times = [r["time"] for r in rows]

    results = engine.compute_batch(
        req.indicators, closes, highs, lows, volumes,
        req.symbol, req.timeframe,
    )

    # Convert numpy arrays to lists for JSON response
    output = {}
    for key, arr in results.items():
        output[key] = [
            {"time": times[i].isoformat(), "value": None if np.isnan(arr[i]) else round(float(arr[i]), 6)}
            for i in range(len(arr))
        ]

    # Optionally persist to Storage Secondary
    if req.persist:
        persist_to_secondary(req.symbol, req.timeframe, req.indicators, results, times)

    return {
        "symbol": req.symbol,
        "timeframe": req.timeframe,
        "candles": len(rows),
        "indicators": output,
    }


def persist_to_secondary(symbol, timeframe, indicator_requests, results, times):
    """Write computed indicators to secondary schema."""
    conn = get_db()
    cur = conn.cursor()

    for req_item in indicator_requests:
        name = req_item["name"]
        params = req_item.get("params", {})
        plugin = registry.get(name)
        if not plugin:
            continue

        p_hash = plugin.params_hash(params)
        key = f"{name}_{engine._params_label(params)}"
        values = results.get(key)
        if values is None:
            continue

        # Upsert metadata
        cur.execute("""
            INSERT INTO secondary.indicator_metadata
                (indicator_name, version, params, params_hash, calculated_at,
                 source_range_start, source_range_end, row_count)
            VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s)
            ON CONFLICT (indicator_name, version, params_hash) DO UPDATE SET
                calculated_at = NOW(), row_count = EXCLUDED.row_count
        """, (name, plugin.version, psycopg2.extras.Json(params), p_hash,
              times[0], times[-1], len(times)))

        # Upsert values
        for i, t in enumerate(times):
            v = values[i]
            if np.isnan(v):
                continue
            cur.execute("""
                INSERT INTO secondary.indicator_values
                    (time, symbol, timeframe, indicator_name, indicator_version, params_hash, value)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (time, symbol, timeframe, indicator_name, params_hash) DO UPDATE SET
                    value = EXCLUDED.value, indicator_version = EXCLUDED.indicator_version
            """, (t, symbol, timeframe, name, plugin.version, p_hash, float(v)))

    conn.commit()
    cur.close()
    conn.close()
    log.info(f"Persisted {len(indicator_requests)} indicators for {symbol} {timeframe}")
