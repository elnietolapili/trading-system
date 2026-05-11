CREATE TABLE IF NOT EXISTS events (
    id          SERIAL PRIMARY KEY,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    service     TEXT NOT NULL,
    level       TEXT NOT NULL CHECK (level IN ('info', 'warn', 'error')),
    event_type  TEXT NOT NULL,
    message     TEXT NOT NULL,
    metadata    JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_events_time ON events (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_service ON events (service);
CREATE INDEX IF NOT EXISTS idx_events_level ON events (level);
