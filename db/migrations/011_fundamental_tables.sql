CREATE TABLE IF NOT EXISTS funding_rate (
    time    TIMESTAMPTZ NOT NULL,
    symbol  TEXT NOT NULL,
    rate    DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (time, symbol)
);

CREATE TABLE IF NOT EXISTS open_interest (
    time    TIMESTAMPTZ NOT NULL,
    symbol  TEXT NOT NULL,
    value   DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (time, symbol)
);

CREATE TABLE IF NOT EXISTS fear_greed (
    time    TIMESTAMPTZ NOT NULL PRIMARY KEY,
    value   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS btc_dominance (
    time    TIMESTAMPTZ NOT NULL PRIMARY KEY,
    value   DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fr_symbol ON funding_rate (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_oi_symbol ON open_interest (symbol, time DESC);
