CREATE TABLE IF NOT EXISTS strategies (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    entry_rules     JSONB NOT NULL DEFAULT '[]'::jsonb,
    exit_rules      JSONB NOT NULL DEFAULT '[]'::jsonb,
    stop_loss_pct   DOUBLE PRECISION,
    take_profit_pct DOUBLE PRECISION,
    position_size   DOUBLE PRECISION DEFAULT 100,
    collection_id   INTEGER,
    last_backtest   JSONB,
    backtest_at     TIMESTAMPTZ,
    active          BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
