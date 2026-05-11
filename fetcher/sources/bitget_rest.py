"""
Bitget REST source: funding rate + open interest.
Polls periodically via public REST API (no auth needed).
"""

import asyncio
import logging
from datetime import datetime, timezone

import aiohttp
from db_helper import get_db, get_active_symbols

FUNDING_URL = "https://api.bitget.com/api/v2/mix/market/current-fund-rate"
OI_URL = "https://api.bitget.com/api/v2/mix/market/open-interest"

FUNDING_INTERVAL = 8 * 3600  # 8 hours
OI_INTERVAL = 3600           # 1 hour

log = logging.getLogger("fetcher.bitget_rest")


async def fetch_funding_rate(session, symbol):
    try:
        params = {"symbol": symbol, "productType": "USDT-FUTURES"}
        async with session.get(FUNDING_URL, params=params) as resp:
            data = await resp.json()
            if data.get("code") == "00000" and data.get("data"):
                item = data["data"][0] if isinstance(data["data"], list) else data["data"]
                rate = float(item.get("fundingRate", 0))
                now = datetime.now(timezone.utc)

                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO funding_rate (time, symbol, rate)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (time, symbol) DO UPDATE SET rate=EXCLUDED.rate
                """, (now.replace(minute=0, second=0, microsecond=0), symbol, rate))
                conn.commit()
                cur.close()
                conn.close()
                log.info(f"Funding rate {symbol}: {rate}")
    except Exception as e:
        log.error(f"Funding rate error {symbol}: {e}")


async def fetch_open_interest(session, symbol):
    try:
        params = {"symbol": symbol, "productType": "USDT-FUTURES"}
        async with session.get(OI_URL, params=params) as resp:
            data = await resp.json()
            if data.get("code") == "00000" and data.get("data"):
                item = data["data"][0] if isinstance(data["data"], list) else data["data"]
                oi = float(item.get("amount", 0))
                now = datetime.now(timezone.utc)

                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO open_interest (time, symbol, value)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (time, symbol) DO UPDATE SET value=EXCLUDED.value
                """, (now.replace(minute=0, second=0, microsecond=0), symbol, oi))
                conn.commit()
                cur.close()
                conn.close()
                log.info(f"Open interest {symbol}: {oi}")
    except Exception as e:
        log.error(f"Open interest error {symbol}: {e}")


async def run():
    """Poll funding rate every 8h, open interest every 1h."""
    oi_counter = 0

    async with aiohttp.ClientSession() as session:
        while True:
            symbols_config = get_active_symbols()
            symbols = [s["symbol"] for s in symbols_config]

            # Open interest every hour
            for symbol in symbols:
                await fetch_open_interest(session, symbol)

            # Funding rate every 8 hours (every 8th iteration)
            if oi_counter % 8 == 0:
                for symbol in symbols:
                    await fetch_funding_rate(session, symbol)

            oi_counter += 1
            await asyncio.sleep(OI_INTERVAL)
