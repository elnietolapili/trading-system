-- Tabla de órdenes ejecutadas por el bot
CREATE TABLE IF NOT EXISTS bot_orders (
    id              SERIAL PRIMARY KEY,
    bot_name        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL,          -- 'buy' o 'sell'
    price           DOUBLE PRECISION,
    quantity        DOUBLE PRECISION,
    cost            DOUBLE PRECISION,       -- price * quantity
    pnl             DOUBLE PRECISION,       -- beneficio/pérdida (solo en sell)
    order_id        TEXT,                   -- ID de orden en Bitget
    status          TEXT DEFAULT 'filled',  -- 'filled', 'canceled', 'pending'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_bot_orders_bot ON bot_orders (bot_name, created_at DESC);

-- Tabla de configuración de bots activos
CREATE TABLE IF NOT EXISTS bots (
    id              SERIAL PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    symbol          TEXT NOT NULL,
    strategy        TEXT NOT NULL,          -- nombre del módulo de estrategia
    params          JSONB DEFAULT '{}',     -- parámetros de la estrategia
    wallet          DOUBLE PRECISION,       -- cartera asignada al bot
    active          BOOLEAN DEFAULT true,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
