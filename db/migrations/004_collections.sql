-- Tabla de colecciones (jerárquica)
CREATE TABLE IF NOT EXISTS collections (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    parent_id   INTEGER REFERENCES collections(id) ON DELETE CASCADE,
    sort_order  INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Añadir collection_id a strategies
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS collection_id INTEGER REFERENCES collections(id) ON DELETE SET NULL;
