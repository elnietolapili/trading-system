"""
CoinGecko source: BTC Dominance.
Free API, no auth needed. Rate limited to ~10 calls/min.
"""

import asyncio
import logging
from datetime import datetime, timezone

import aiohttp
from db_helper import get_db

API_URL = "https://api.coingecko.com/api/v3/global"
INTERVAL = 3600  # 1 hour

log = logging.getLogger("fetcher.btc_dominance")


async def fetch_btc_dominance(session):
    try:
        async with session.get(API_URL) as resp:
            data = await resp.json(content_type=None)
            if data.get("data") and "market_cap_percentage" in data["data"]:
                dominance = data["data"]["market_cap_percentage"].get("btc", 0)
                now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO btc_dominance (time, value)
                    VALUES (%s, %s)
                    ON CONFLICT (time) DO UPDATE SET value=EXCLUDED.value
                """, (now, dominance))
                conn.commit()
                cur.close()
                conn.close()
                log.info(f"BTC Dominance: {dominance:.2f}%")
    except Exception as e:
        log.error(f"BTC Dominance error: {e}")


async def run():
    """Poll BTC dominance every 1h."""
    async with aiohttp.ClientSession() as session:
        while True:
            await fetch_btc_dominance(session)
            await asyncio.sleep(INTERVAL)
