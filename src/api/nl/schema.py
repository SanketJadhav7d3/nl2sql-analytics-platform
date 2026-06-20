"""Builds the analytics-schema description sent to the LLM.

Introspects the live `analytics` schema (tables/views + columns) so the prompt
always matches reality. Cached after first build.
"""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import text

from ..db import engine

# Short human descriptions to give the model business context.
_OBJECT_NOTES = {
    "fct_order_items": "fact table, one row per order line (item_revenue, delivery_days, on_time, order_month)",
    "dim_product": "products with English category",
    "dim_customer": "customers (customer_unique_id identifies a person)",
    "dim_seller": "sellers with state",
    "dim_date": "calendar",
    "vw_monthly_revenue": "monthly revenue with running total + MoM growth",
    "vw_category_performance": "revenue by category with rank + share",
    "vw_seller_scorecard": "seller revenue + avg review, ranked",
    "vw_delivery_sla": "on-time % and avg delivery days by customer state",
}


@lru_cache(maxsize=1)
def build_schema_prompt() -> str:
    sql = text(
        """
        SELECT table_name, column_name, data_type, ordinal_position
        FROM information_schema.columns
        WHERE table_schema = 'analytics'
        ORDER BY table_name, ordinal_position
        """
    )
    cols: dict[str, list[str]] = {}
    with engine.connect() as conn:
        for r in conn.execute(sql).mappings():
            cols.setdefault(r["table_name"], []).append(
                f"{r['column_name']} {r['data_type']}"
            )

    lines = ["Schema `analytics` (read-only). Tables and views:"]
    for obj, columns in cols.items():
        note = _OBJECT_NOTES.get(obj, "")
        suffix = f"  -- {note}" if note else ""
        lines.append(f"\n{obj} ({', '.join(columns)}){suffix}")
    return "\n".join(lines)
