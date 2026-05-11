import os
import psycopg2
import psycopg2.extras

DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "trading")
DB_USER = os.getenv("DB_USER", "trading")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")


def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
    )


def get_active_symbols():
    """Read active symbols from fetcher_config table."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT symbol, timeframes, source FROM fetcher_config WHERE active = TRUE")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows
