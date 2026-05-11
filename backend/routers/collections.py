from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from database import get_cursor

router = APIRouter()


class CollectionCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None


@router.get("/collections")
def list_collections():
    with get_cursor() as (conn, cur):
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
            if s.get("backtest_at"):
                s["backtest_at"] = s["backtest_at"].isoformat()
    return {"collections": collections, "strategies": strategies}


@router.post("/collections")
def create_collection(c: CollectionCreate):
    with get_cursor(dict_cursor=False) as (conn, cur):
        cur.execute(
            "INSERT INTO collections (name, parent_id) VALUES (%s,%s) RETURNING id",
            (c.name, c.parent_id),
        )
        cid = cur.fetchone()[0]
    return {"id": cid, "name": c.name, "status": "created"}


@router.put("/collections/{collection_id}")
def update_collection(collection_id: int, c: CollectionUpdate):
    updates, params = [], []
    if c.name is not None:
        updates.append("name = %s"); params.append(c.name)
    if c.parent_id is not None:
        updates.append("parent_id = %s"); params.append(c.parent_id)
    if c.sort_order is not None:
        updates.append("sort_order = %s"); params.append(c.sort_order)
    if updates:
        params.append(collection_id)
        with get_cursor(dict_cursor=False) as (conn, cur):
            cur.execute(f"UPDATE collections SET {', '.join(updates)} WHERE id = %s", params)
    return {"id": collection_id, "status": "updated"}


@router.delete("/collections/{collection_id}")
def delete_collection(collection_id: int):
    with get_cursor(dict_cursor=False) as (conn, cur):
        cur.execute("DELETE FROM collections WHERE id = %s", (collection_id,))
    return {"id": collection_id, "status": "deleted"}
