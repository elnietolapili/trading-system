-- Activar TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Tabla principal: velas OHLCV + indicadores fijos
CREATE TABLE ohlcv (
    time        TIMESTAMPTZ      NOT NULL,
    symbol      TEXT             NOT NULL,
    timeframe   TEXT             NOT NULL,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION,
    volume      DOUBLE PRECISION,
    -- Indicadores (se rellenan bajo demanda)
    ema_9       DOUBLE PRECISION,
    ema_20      DOUBLE PRECISION,
    ema_50      DOUBLE PRECISION,
    ema_100     DOUBLE PRECISION,
    ema_200     DOUBLE PRECISION,
    sar_015     DOUBLE PRECISION,  -- SAR 0.015/0.015/0.12
    sar_020     DOUBLE PRECISION,  -- SAR 0.02/0.02/0.2
    rsi_14      DOUBLE PRECISION,
    rsi_7       DOUBLE PRECISION,
    rsi_ma_14   DOUBLE PRECISION,  -- MA del RSI 14, periodo 14
    UNIQUE (time, symbol, timeframe)
);

-- Convertir a hypertable de TimescaleDB
SELECT create_hypertable('ohlcv', 'time');

-- Índice para búsquedas: "dame ETH en 1h entre X e Y"
CREATE INDEX idx_ohlcv_lookup ON ohlcv (symbol, timeframe, time DESC);

-- Compresión automática para datos de más de 30 días
ALTER TABLE ohlcv SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, timeframe',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('ohlcv', INTERVAL '30 days');
