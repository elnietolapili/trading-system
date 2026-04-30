-- Tabla de estrategias
CREATE TABLE IF NOT EXISTS strategies (
    id              SERIAL PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    symbol          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    -- Reglas de entrada: lista de condiciones combinadas con AND
    entry_rules     JSONB NOT NULL DEFAULT '[]',
    -- Reglas de salida: lista de condiciones combinadas con AND
    exit_rules      JSONB NOT NULL DEFAULT '[]',
    -- Parámetros generales
    stop_loss_pct   DOUBLE PRECISION,      -- % de stop loss (ej: 2.0 = 2%)
    take_profit_pct DOUBLE PRECISION,      -- % de take profit
    position_size   DOUBLE PRECISION DEFAULT 100, -- tamaño en USD
    -- Resultados del último backtest
    last_backtest   JSONB,                 -- métricas, equity curve, trades
    backtest_at     TIMESTAMPTZ,           -- cuándo se ejecutó
    -- Meta
    active          BOOLEAN DEFAULT false,  -- si está activa para el bot
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ejemplo de entry_rules:
-- [
--   {"indicator": "ema_9", "operator": "crosses_above", "value": "ema_50"},
--   {"indicator": "rsi_14", "operator": "less_than", "value": 70}
-- ]
--
-- Operadores disponibles:
--   crosses_above, crosses_below  (un indicador cruza otro o un número)
--   greater_than, less_than       (comparación simple)
--   sar_below_price, sar_above_price  (SAR respecto al precio)
