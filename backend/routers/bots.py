from fastapi import APIRouter
from database import get_cursor

router = APIRouter()


@router.get("/bots")
def list_bots():
    with get_cursor() as (conn, cur):
        cur.execute("SELECT * FROM bots ORDER BY name")
        bots = []
        for r in cur.fetchall():
            b = dict(r)
            if b.get("started_at"):
                b["started_at"] = b["started_at"].isoformat()
            bots.append(b)
    return {"bots": bots}


@router.get("/bots/{bot_name}/orders")
def bot_orders(bot_name: str):
    with get_cursor() as (conn, cur):
        cur.execute(
            "SELECT * FROM bot_orders WHERE bot_name = %s ORDER BY created_at DESC LIMIT 100",
            (bot_name,),
        )
        orders = []
        for r in cur.fetchall():
            o = dict(r)
            o["created_at"] = o["created_at"].isoformat()
            orders.append(o)
    return {"bot_name": bot_name, "orders": orders}


@router.get("/bots/{bot_name}/stats")
def bot_stats(bot_name: str):
    with get_cursor() as (conn, cur):
        cur.execute(
            """SELECT COUNT(*) as total_orders,
                 SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning,
                 SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losing,
                 SUM(pnl) as total_pnl, AVG(pnl) as avg_pnl
               FROM bot_orders WHERE bot_name = %s""",
            (bot_name,),
        )
        row = cur.fetchone()
        stats = dict(row) if row else {}
    return {"bot_name": bot_name, "stats": stats}
