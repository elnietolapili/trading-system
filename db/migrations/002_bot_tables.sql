CREATE TABLE IF NOT EXISTS bots (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    symbol      TEXT NOT NULL,
    strategy    TEXT,
    params      JSONB DEFAULT '{}'::jsonb,
    wallet      DOUBLE PRECISION DEFAULT 0,
    active      BOOLEAN DEFAULT FALSE,
    started_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS bot_orders (
    id          SERIAL PRIMARY KEY,
    bot_name    TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    price       DOUBLE PRECISION,
    quantity    DOUBLE PRECISION,
    cost        DOUBLE PRECISION,
    pnl         DOUBLE PRECISION,
    order_id    TEXT,
    status      TEXT DEFAULT 'filled',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
