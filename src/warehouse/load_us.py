"""
US e-commerce warehouse loader (second dataset, isolated from Olist).

Creates the `raw_us` schema, COPY-loads all 8 CSVs from data/us-ecommerce-dataset/,
then builds the `analytics_us` star schema + views. Idempotent: re-running drops
and recreates both schemas.

Usage:
    python -m src.warehouse.load_us              # full build
    python -m src.warehouse.load_us --skip-analytics

Connection is read from environment / .env (same Postgres instance as the
Olist warehouse — separate schemas, not a separate database):
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

ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "sql"
DATA_DIR = Path(os.getenv("DATA_DIR_US") or ROOT / "data" / "us-ecommerce-dataset")

CSV_TO_TABLE: list[tuple[str, str]] = [
    ("customers.csv",       "raw_us.customers"),
    ("geolocation.csv",     "raw_us.geolocation"),
    ("order_items.csv",     "raw_us.order_items"),
    ("order_payments.csv",  "raw_us.order_payments"),
    ("order_reviews.csv",   "raw_us.order_reviews"),
    ("orders.csv",          "raw_us.orders"),
    ("products.csv",        "raw_us.products"),
    ("sellers.csv",         "raw_us.sellers"),
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
    sql = f"COPY {table} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')"
    with csv_path.open("rb") as fh, cur.copy(sql) as copy:
        while chunk := fh.read(1 << 16):
            copy.write(chunk)
    cur.execute(f"SELECT count(*) FROM {table}")
    return cur.fetchone()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Load the US e-commerce warehouse.")
    parser.add_argument("--skip-analytics", action="store_true",
                        help="Load raw_us only; skip building the analytics_us schema.")
    args = parser.parse_args()

    missing = [f for f, _ in CSV_TO_TABLE if not (DATA_DIR / f).exists()]
    if missing:
        print(f"ERROR: missing CSV(s) in {DATA_DIR}:", *missing, sep="\n  ")
        return 1

    t0 = time.time()
    conn = connect()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            print("1) Creating raw_us schema...")
            run_sql_file(cur, SQL_DIR / "01_raw_schema_us.sql")

            print("2) Loading CSVs...")
            total = 0
            for fname, table in CSV_TO_TABLE:
                n = copy_csv(cur, DATA_DIR / fname, table)
                total += n
                print(f"     {table:<45} {n:>9,} rows")
            print(f"   loaded {total:,} raw rows total")

            if not args.skip_analytics:
                print("3) Building analytics_us schema (dims, fact, views)...")
                run_sql_file(cur, SQL_DIR / "02_analytics_schema_us.sql")

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
