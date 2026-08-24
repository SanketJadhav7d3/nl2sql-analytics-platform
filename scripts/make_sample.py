"""Generate a small, referentially-consistent sample of the Olist dataset.

The full CSVs (~125 MB) are gitignored, so CI has nothing to load and the
integration tests skip. This script carves out a tiny slice that still loads
into the same warehouse and satisfies every constant the test-suite hardcodes:

  * >= 5 distinct product categories      (test_top_categories_limit_and_rank)
  * >= 10 sellers                         (test_seller_scorecard, limit=10)
  * delivered orders in Jan 2017          (test_revenue_granularity_and_date_filter)
  * >= 1 repeat customer                  (test_repeat_customers, for realism)
  * >= 1 payment type                     (test_aov by_payment_type)

A naive per-file row sample would break referential integrity (order_items
pointing at orders/products/sellers that were dropped), and those rows vanish
when the analytics star schema is built. So we pick a seed set of *orders* and
cascade to only the related rows in every other table.

Output goes to data/sample/ (committed); point the loader at it with
DATA_DIR=data/sample. The reporting views filter order_status='delivered', so
we sample delivered orders only — that way every sampled row feeds the metrics.

Run:  python -m scripts.make_sample      (or: python scripts/make_sample.py)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "sample"

SEED = 7
N_GENERAL = 2500   # random delivered orders across the whole time span
N_JAN2017 = 300    # delivered orders forced from Jan 2017
N_REPEAT_PERSONS = 60  # repeat customers whose every delivered order we keep
N_GEO = 2000       # geolocation is never used by analytics — keep a token slice


def _read(name: str, **kw) -> pd.DataFrame:
    # dtype=str preserves exact source text: leading-zero zips ("01037"),
    # timestamps, and numeric formatting all round-trip unchanged through COPY.
    return pd.read_csv(RAW / name, dtype=str, **kw)


def main() -> int:
    if not RAW.exists():
        print(f"ERROR: {RAW} not found — run this against the full dataset.")
        return 1

    print("Reading full CSVs...")
    orders = _read("olist_orders_dataset.csv")
    customers = _read("olist_customers_dataset.csv")
    items = _read("olist_order_items_dataset.csv")
    payments = _read("olist_order_payments_dataset.csv")
    reviews = _read("olist_order_reviews_dataset.csv")
    products = _read("olist_products_dataset.csv")
    sellers = _read("olist_sellers_dataset.csv")
    translation = _read("product_category_name_translation.csv")  # tiny: keep all
    geolocation = _read("olist_geolocation_dataset.csv", nrows=N_GEO)

    # Only delivered orders that actually have line items can feed the metrics.
    with_items = set(items["order_id"])
    delivered = orders[
        (orders["order_status"] == "delivered")
        & (orders["order_id"].isin(with_items))
    ].copy()
    print(f"  delivered orders with items: {len(delivered):,}")

    # customer_id -> customer_unique_id (the real person) for repeat detection.
    cust_person = customers.set_index("customer_id")["customer_unique_id"]
    delivered["person"] = delivered["customer_id"].map(cust_person)

    chosen: set[str] = set()

    # 1) force some Jan-2017 orders so the daily date-range test has data.
    jan = delivered[delivered["order_purchase_timestamp"].str.startswith("2017-01", na=False)]
    chosen |= set(jan.sample(min(N_JAN2017, len(jan)), random_state=SEED)["order_id"])

    # 2) keep ALL delivered orders of a handful of repeat customers, so the
    #    repeat-customer metric is non-trivial rather than relying on luck.
    per_person = delivered.groupby("person")["order_id"].nunique()
    repeat_persons = per_person[per_person > 1].index
    picked = pd.Series(repeat_persons).sample(
        min(N_REPEAT_PERSONS, len(repeat_persons)), random_state=SEED
    )
    chosen |= set(delivered[delivered["person"].isin(set(picked))]["order_id"])

    # 3) a broad random sample for category/seller variety and a full time span.
    chosen |= set(
        delivered.sample(min(N_GENERAL, len(delivered)), random_state=SEED)["order_id"]
    )

    # ---- cascade to referentially-related rows --------------------------------
    sel_orders = orders[orders["order_id"].isin(chosen)]
    sel_items = items[items["order_id"].isin(chosen)]
    sel_payments = payments[payments["order_id"].isin(chosen)]
    sel_reviews = reviews[reviews["order_id"].isin(chosen)]
    sel_customers = customers[customers["customer_id"].isin(set(sel_orders["customer_id"]))]
    sel_products = products[products["product_id"].isin(set(sel_items["product_id"]))]
    sel_sellers = sellers[sellers["seller_id"].isin(set(sel_items["seller_id"]))]

    # ---- guardrails: fail loudly if the slice can't satisfy the tests ---------
    cat = sel_products.merge(
        translation, on="product_category_name", how="left"
    )["product_category_name_english"].fillna(sel_products["product_category_name"])
    n_categories = cat.nunique()
    n_sellers = sel_sellers["seller_id"].nunique()
    n_jan = sel_orders["order_purchase_timestamp"].str.startswith("2017-01", na=False).sum()
    person = sel_customers.set_index("customer_id")["customer_unique_id"]
    person_orders = sel_orders.assign(p=sel_orders["customer_id"].map(person))
    n_repeat = (person_orders.groupby("p")["order_id"].nunique() > 1).sum()
    n_paytypes = sel_payments["payment_type"].nunique()

    checks = {
        ">=6 categories": n_categories >= 6,
        ">=10 sellers": n_sellers >= 10,
        ">=1 Jan-2017 order": n_jan >= 1,
        ">=1 repeat customer": n_repeat >= 1,
        ">=1 payment type": n_paytypes >= 1,
    }
    print("\nSample guarantees:")
    for label, ok in checks.items():
        got = {
            ">=6 categories": n_categories, ">=10 sellers": n_sellers,
            ">=1 Jan-2017 order": n_jan, ">=1 repeat customer": n_repeat,
            ">=1 payment type": n_paytypes,
        }[label]
        print(f"  [{'OK' if ok else 'FAIL'}] {label:<22} got {got}")
    if not all(checks.values()):
        print("\nERROR: sample does not satisfy test constraints; adjust the knobs.")
        return 1

    # ---- write ----------------------------------------------------------------
    OUT.mkdir(parents=True, exist_ok=True)
    out = {
        "olist_orders_dataset.csv": sel_orders,
        "olist_customers_dataset.csv": sel_customers,
        "olist_order_items_dataset.csv": sel_items,
        "olist_order_payments_dataset.csv": sel_payments,
        "olist_order_reviews_dataset.csv": sel_reviews,
        "olist_products_dataset.csv": sel_products,
        "olist_sellers_dataset.csv": sel_sellers,
        "product_category_name_translation.csv": translation,
        "olist_geolocation_dataset.csv": geolocation,
    }
    print(f"\nWriting sample to {OUT}:")
    total_bytes = 0
    for name, df in out.items():
        path = OUT / name
        # na_rep='' so empty fields match the loader's COPY ... NULL '' contract.
        df.to_csv(path, index=False, na_rep="")
        total_bytes += path.stat().st_size
        print(f"  {name:<45} {len(df):>7,} rows")
    print(f"\nDone. {total_bytes/1e6:.1f} MB total across {len(out)} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
