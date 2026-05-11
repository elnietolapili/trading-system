CREATE SCHEMA IF NOT EXISTS secondary;

CREATE TABLE IF NOT EXISTS secondary.indicator_values (
    time            TIMESTAMPTZ NOT NULL,
    symbol          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    indicator_name  TEXT NOT NULL,
    indicator_version TEXT NOT NULL,
    params_hash     TEXT NOT NULL,
    value           DOUBLE PRECISION,
    PRIMARY KEY (time, symbol, timeframe, indicator_name, params_hash)
);

CREATE TABLE IF NOT EXISTS secondary.indicator_metadata (
    id              SERIAL PRIMARY KEY,
    indicator_name  TEXT NOT NULL,
    version         TEXT NOT NULL,
    params          JSONB NOT NULL,
    params_hash     TEXT NOT NULL,
    calculated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_range_start TIMESTAMPTZ,
    source_range_end   TIMESTAMPTZ,
    row_count       INTEGER,
    UNIQUE (indicator_name, version, params_hash)
);

CREATE INDEX IF NOT EXISTS idx_iv_symbol_tf ON secondary.indicator_values (symbol, timeframe, indicator_name);
CREATE INDEX IF NOT EXISTS idx_iv_time ON secondary.indicator_values (time DESC);
