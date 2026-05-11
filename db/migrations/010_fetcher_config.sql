CREATE TABLE IF NOT EXISTS fetcher_config (
    id          SERIAL PRIMARY KEY,
    symbol      TEXT NOT NULL UNIQUE,
    timeframes  TEXT[] NOT NULL DEFAULT ARRAY['30m','1h','2h','4h','8h','12h','1D','1W'],
    active      BOOLEAN DEFAULT TRUE,
    source      TEXT DEFAULT 'bitget',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO fetcher_config (symbol, active) VALUES
    ('ETHUSDT', TRUE),
    ('BTCUSDT', TRUE),
    ('BNBUSDT', TRUE)
ON CONFLICT (symbol) DO NOTHING;
