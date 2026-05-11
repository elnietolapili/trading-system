"""
Alternative.me source: Crypto Fear & Greed Index.
Free API, daily data, no auth needed.
"""

import asyncio
import logging
from datetime import datetime, timezone

import aiohttp
from db_helper import get_db

API_URL = "https://api.alternative.me/fng/?limit=1"
INTERVAL = 24 * 3600  # 24 hours

log = logging.getLogger("fetcher.fear_greed")


async def fetch_fear_greed(session):
    try:
        async with session.get(API_URL) as resp:
            data = await resp.json(content_type=None)
            if data.get("data"):
                item = data["data"][0]
                value = int(item["value"])
                ts = datetime.fromtimestamp(int(item["timestamp"]), tz=timezone.utc)

                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO fear_greed (time, value)
                    VALUES (%s, %s)
                    ON CONFLICT (time) DO UPDATE SET value=EXCLUDED.value
                """, (ts, value))
                conn.commit()
                cur.close()
                conn.close()
                log.info(f"Fear & Greed: {value} ({item.get('value_classification', '')})")
    except Exception as e:
        log.error(f"Fear & Greed error: {e}")


async def run():
    """Poll Fear & Greed Index every 24h."""
    async with aiohttp.ClientSession() as session:
        while True:
            await fetch_fear_greed(session)
            await asyncio.sleep(INTERVAL)
