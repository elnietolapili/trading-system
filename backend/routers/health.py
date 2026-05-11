from fastapi import APIRouter
from database import get_cursor

router = APIRouter()


@router.get("/health")
def health_check():
    try:
        with get_cursor() as (conn, cur):
            cur.execute("SELECT COUNT(*) as total FROM ohlcv")
            row = cur.fetchone()
            total = row["total"] if row else 0
        return {"status": "ok", "total_candles": total}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
