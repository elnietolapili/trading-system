CREATE TABLE IF NOT EXISTS backtest_results (
    id                  SERIAL PRIMARY KEY,
    strategy_id         INTEGER NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    pnl_total           DECIMAL,
    pnl_pct             DECIMAL,
    win_rate            DECIMAL,
    max_drawdown        DECIMAL,
    profit_factor       DECIMAL,
    sharpe_ratio        DECIMAL,
    num_trades          INTEGER,
    symbol              TEXT NOT NULL,
    timeframe           TEXT NOT NULL,
    date_from           TIMESTAMPTZ,
    date_to             TIMESTAMPTZ,
    indicator_versions  JSONB,
    params_used         JSONB,
    backtest_type       TEXT DEFAULT 'simple',
    duration_seconds    DECIMAL,
    memory_peak_mb      DECIMAL,
    candles_processed   INTEGER,
    candles_per_second  DECIMAL,
    is_favorite         BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS backtest_trades (
    id              SERIAL PRIMARY KEY,
    backtest_id     INTEGER NOT NULL REFERENCES backtest_results(id) ON DELETE CASCADE,
    entry_time      TIMESTAMPTZ NOT NULL,
    exit_time       TIMESTAMPTZ,
    entry_price     DECIMAL NOT NULL,
    exit_price      DECIMAL,
    direction       TEXT NOT NULL CHECK (direction IN ('long', 'short')),
    pnl             DECIMAL,
    pnl_pct         DECIMAL,
    exit_reason     TEXT CHECK (exit_reason IN ('signal', 'stop_loss', 'take_profit', 'end_of_data'))
);

CREATE TABLE IF NOT EXISTS backtest_equity (
    id              SERIAL PRIMARY KEY,
    backtest_id     INTEGER NOT NULL REFERENCES backtest_results(id) ON DELETE CASCADE,
    time            TIMESTAMPTZ NOT NULL,
    equity_value    DECIMAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_br_strategy ON backtest_results (strategy_id);
CREATE INDEX IF NOT EXISTS idx_br_created ON backtest_results (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bt_backtest ON backtest_trades (backtest_id);
CREATE INDEX IF NOT EXISTS idx_be_backtest ON backtest_equity (backtest_id);
