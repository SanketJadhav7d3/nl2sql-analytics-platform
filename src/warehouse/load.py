"""
Warehouse loader.

Creates the `raw` schema, COPY-loads all 9 Olist CSVs from data/raw/, then
builds the `analytics` star schema + views. Idempotent: re-running drops and
recreates both schemas (the SQL files do `DROP SCHEMA ... CASCADE`).

Usage:
    python -m src.warehouse.load           # full build (schema + load + analytics)
    python -m src.warehouse.load --skip-analytics

Connection is read from environment / .env:
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_HOST, POSTGRES_PORT
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# --- paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "sql"
DATA_DIR = ROOT / "data" / "raw"

# CSV file -> fully-qualified raw table. Column lists are omitted because the
# CSV header order matches each table's column order (HEADER true skips it).
CSV_TO_TABLE: list[tuple[str, str]] = [
    ("olist_customers_dataset.csv",            "raw.customers"),
    ("olist_geolocation_dataset.csv",          "raw.geolocation"),
    ("olist_order_items_dataset.csv",          "raw.order_items"),
    ("olist_order_payments_dataset.csv",       "raw.order_payments"),
    ("olist_order_reviews_dataset.csv",        "raw.order_reviews"),
    ("olist_orders_dataset.csv",               "raw.orders"),
    ("olist_products_dataset.csv",             "raw.products"),
    ("olist_sellers_dataset.csv",              "raw.sellers"),
    ("product_category_name_translation.csv",  "raw.product_category_name_translation"),
]


def connect():
    load_dotenv(ROOT / ".env")
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "analytics"),
        user=os.getenv("POSTGRES_USER", "analytics"),
        password=os.getenv("POSTGRES_PASSWORD", "analytics"),
    )


def run_sql_file(cur, path: Path) -> None:
    print(f"  -> executing {path.name}")
    cur.execute(path.read_text(encoding="utf-8"))


def copy_csv(cur, csv_path: Path, table: str) -> int:
    # COPY ... CSV HEADER handles quoted fields and embedded newlines (reviews).
    # Empty unquoted fields become NULL. Stream the file in binary chunks so the
    # 60 MB geolocation file never lands in memory whole.
    sql = f"COPY {table} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')"
    with csv_path.open("rb") as fh, cur.copy(sql) as copy:
        while chunk := fh.read(1 << 16):
            copy.write(chunk)
    cur.execute(f"SELECT count(*) FROM {table}")
    return cur.fetchone()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Load the Olist warehouse.")
    parser.add_argument("--skip-analytics", action="store_true",
                        help="Load raw only; skip building the analytics schema.")
    args = parser.parse_args()

    missing = [f for f, _ in CSV_TO_TABLE if not (DATA_DIR / f).exists()]
    if missing:
        print("ERROR: missing CSV(s) in data/raw/:", *missing, sep="\n  ")
        return 1

    t0 = time.time()
    conn = connect()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            print("1) Creating raw schema...")
            run_sql_file(cur, SQL_DIR / "01_raw_schema.sql")

            print("2) Loading CSVs...")
            total = 0
            for fname, table in CSV_TO_TABLE:
                n = copy_csv(cur, DATA_DIR / fname, table)
                total += n
                print(f"     {table:<45} {n:>9,} rows")
            print(f"   loaded {total:,} raw rows total")

            if not args.skip_analytics:
                print("3) Building analytics schema (dims, fact, views)...")
                run_sql_file(cur, SQL_DIR / "02_analytics_schema.sql")

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"Done in {time.time() - t0:.1f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
