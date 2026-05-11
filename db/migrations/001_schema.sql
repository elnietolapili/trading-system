CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS ohlcv (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    timeframe   TEXT NOT NULL,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION,
    volume      DOUBLE PRECISION,
    ema_9       DOUBLE PRECISION,
    ema_20      DOUBLE PRECISION,
    ema_50      DOUBLE PRECISION,
    ema_100     DOUBLE PRECISION,
    ema_200     DOUBLE PRECISION,
    sar_015     DOUBLE PRECISION,
    sar_020     DOUBLE PRECISION,
    rsi_14      DOUBLE PRECISION,
    rsi_7       DOUBLE PRECISION,
    rsi_ma_14   DOUBLE PRECISION,
    UNIQUE (time, symbol, timeframe)
);

SELECT create_hypertable('ohlcv', 'time', if_not_exists => TRUE);
