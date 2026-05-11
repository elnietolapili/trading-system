"""
Fetcher orchestrator: launches all data sources as concurrent async tasks.
- Bitget WebSocket (OHLCV candles)
- Bitget REST (funding rate, open interest)
- Alternative.me (Fear & Greed Index)
- CoinGecko (BTC Dominance)
"""

import asyncio
import logging

from sources import bitget_ws, bitget_rest, alternative_me, coingecko

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
log = logging.getLogger("fetcher")


async def main():
    log.info("Starting fetcher orchestrator...")
    log.info("Sources: Bitget WS, Bitget REST, Alternative.me, CoinGecko")

    tasks = [
        asyncio.create_task(bitget_ws.run(), name="bitget_ws"),
        asyncio.create_task(bitget_rest.run(), name="bitget_rest"),
        asyncio.create_task(alternative_me.run(), name="fear_greed"),
        asyncio.create_task(coingecko.run(), name="btc_dominance"),
    ]

    # If any task crashes, log it and restart
    while True:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for task in done:
            name = task.get_name()
            if task.exception():
                log.error(f"Source '{name}' crashed: {task.exception()}. Restarting in 10s...")
                await asyncio.sleep(10)
                # Restart the crashed source
                if name == "bitget_ws":
                    new_task = asyncio.create_task(bitget_ws.run(), name="bitget_ws")
                elif name == "bitget_rest":
                    new_task = asyncio.create_task(bitget_rest.run(), name="bitget_rest")
                elif name == "fear_greed":
                    new_task = asyncio.create_task(alternative_me.run(), name="fear_greed")
                elif name == "btc_dominance":
                    new_task = asyncio.create_task(coingecko.run(), name="btc_dominance")
                else:
                    continue
                tasks = list(pending) + [new_task]
            else:
                log.warning(f"Source '{name}' finished unexpectedly")


if __name__ == "__main__":
    asyncio.run(main())
