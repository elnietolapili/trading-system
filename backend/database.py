import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

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


@contextmanager
def get_cursor(dict_cursor=True):
    conn = get_db()
    factory = psycopg2.extras.RealDictCursor if dict_cursor else None
    cur = conn.cursor(cursor_factory=factory)
    try:
        yield conn, cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
