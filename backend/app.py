from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import candles, strategies, collections, bots, health

app = FastAPI(title="Trading System API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(candles.router, tags=["candles"])
app.include_router(strategies.router, tags=["strategies"])
app.include_router(collections.router, tags=["collections"])
app.include_router(bots.router, tags=["bots"])
