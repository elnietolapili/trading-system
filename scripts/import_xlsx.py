"""
Importar ETH_ALL_TIMEFRAMES.xlsx a la tabla ohlcv de PostgreSQL.

Uso:
    python import_xlsx.py ETH_ALL_TIMEFRAMES.xlsx

Requiere: pip install pandas openpyxl psycopg2-binary
"""

import sys
import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# Conexión a la DB (usa variables de entorno o valores por defecto)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "trading")
DB_USER = os.getenv("DB_USER", "trading")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")

# Mapeo de columnas del xlsx a columnas de la DB
COLUMN_MAP = {
    "time": "time",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "Volume": "volume",
    "EMA1": "ema_9",
    "EMA2": "ema_20",
    "EMA3": "ema_50",
    "EMA4": "ema_100",
    "EMA5": "ema_200",
    "ParabolicSAR": "sar_015",
    "RSI": "rsi_14",
    "RSI_MA": "rsi_ma_14",
}

# Columnas que se insertan en la DB (en orden)
DB_COLUMNS = [
    "time", "symbol", "timeframe",
    "open", "high", "low", "close", "volume",
    "ema_9", "ema_20", "ema_50", "ema_100", "ema_200",
    "sar_015", "rsi_14", "rsi_ma_14",
]

def import_sheet(cursor, df, symbol, timeframe):
    """Importa un DataFrame (una hoja del xlsx) a la tabla ohlcv."""

    # Renombrar columnas según el mapeo
    df = df.rename(columns=COLUMN_MAP)

    # Añadir symbol y timeframe
    df["symbol"] = symbol
    df["timeframe"] = timeframe

    # Quedarse solo con las columnas que existen en la DB
    for col in DB_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[DB_COLUMNS]

    # Convertir NaN a None para PostgreSQL
    df = df.where(df.notna(), None)

    # Insertar en lotes de 1000 filas
    rows = [tuple(row) for row in df.values]
    insert_sql = f"""
        INSERT INTO ohlcv ({', '.join(DB_COLUMNS)})
        VALUES %s
        ON CONFLICT (time, symbol, timeframe) DO NOTHING
    """
    execute_values(cursor, insert_sql, rows, page_size=1000)

    return len(rows)


def main():
    if len(sys.argv) < 2:
        print("Uso: python import_xlsx.py <archivo.xlsx>")
        sys.exit(1)

    filepath = sys.argv[1]
    symbol = "ETHUSDT"  # Cambiar si importas otra cripto

    print(f"Leyendo {filepath}...")
    xls = pd.ExcelFile(filepath)

    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    conn.autocommit = False
    cursor = conn.cursor()

    total = 0
    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet)
        count = import_sheet(cursor, df, symbol, sheet)
        print(f"  {sheet}: {count} filas importadas")
        total += count

    conn.commit()
    cursor.close()
    conn.close()

    print(f"\nTotal: {total} filas importadas para {symbol}")


if __name__ == "__main__":
    main()
