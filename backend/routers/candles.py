from fastapi import APIRouter, Query
from typing import Optional
from database import get_cursor

router = APIRouter()


@router.get("/symbols")
def list_symbols():
    with get_cursor() as (conn, cur):
        cur.execute("SELECT DISTINCT symbol FROM ohlcv ORDER BY symbol")
        symbols = [r["symbol"] for r in cur.fetchall()]
    return {"symbols": symbols}


@router.get("/timeframes")
def list_timeframes():
    with get_cursor() as (conn, cur):
        cur.execute("SELECT DISTINCT timeframe FROM ohlcv ORDER BY timeframe")
        timeframes = [r["timeframe"] for r in cur.fetchall()]
    return {"timeframes": timeframes}


@router.get("/candles")
def get_candles(
    symbol: str = Query(...),
    timeframe: str = Query(...),
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = Query(default=1000, le=1000000),
):
    with get_cursor() as (conn, cur):
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

    candles = []
    for row in rows:
        candle = dict(row)
        candle["time"] = candle["time"].isoformat()
        candles.append(candle)
    return {"symbol": symbol, "timeframe": timeframe, "count": len(candles), "candles": candles}
