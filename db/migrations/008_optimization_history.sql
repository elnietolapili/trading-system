CREATE TABLE IF NOT EXISTS optimization_history (
    id                  SERIAL PRIMARY KEY,
    strategy_base_id    INTEGER NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    params_hash         TEXT NOT NULL,
    params              JSONB NOT NULL,
    logic_hash          TEXT NOT NULL,
    pnl                 DECIMAL,
    win_rate            DECIMAL,
    max_drawdown        DECIMAL,
    profit_factor       DECIMAL,
    verdict             TEXT NOT NULL CHECK (verdict IN ('satisfactory', 'unsatisfactory', 'early_stop')),
    data_range          TEXT,
    tested_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oh_strategy ON optimization_history (strategy_base_id);
CREATE INDEX IF NOT EXISTS idx_oh_hashes ON optimization_history (logic_hash, params_hash);
