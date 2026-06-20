"""Business logic for the reporting endpoints.

Every query uses SQLAlchemy `text()` with **bound parameters** — no string
interpolation of user input. The one non-bindable knob, `granularity`, is a SQL
keyword (day/week/month) that can't be a bound parameter, so it is validated
against a strict whitelist before being placed into the statement.

Each function takes a Connection and returns plain dicts/objects, keeping it
independent of FastAPI and therefore unit-testable on its own.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Connection

# granularity is a date_trunc field name, not a value -> cannot be bound; whitelist it.
ALLOWED_GRANULARITIES = {"day", "week", "month"}


# ---------------------------------------------------------------------------
def revenue_trend(
    conn: Connection,
    granularity: str = "month",
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    if granularity not in ALLOWED_GRANULARITIES:
        raise ValueError(f"invalid granularity: {granularity!r}")

    sql = text(
        f"""
        WITH per AS (
            SELECT date_trunc('{granularity}', order_purchase_timestamp)::date AS period,
                   sum(item_revenue)        AS revenue,
                   count(DISTINCT order_id) AS orders
            FROM analytics.fct_order_items
            WHERE order_status = 'delivered'
              AND (CAST(:date_from AS date) IS NULL
                   OR order_purchase_timestamp >= CAST(:date_from AS date))
              AND (CAST(:date_to AS date) IS NULL
                   OR order_purchase_timestamp < CAST(:date_to AS date) + INTERVAL '1 day')
            GROUP BY 1
        )
        SELECT
            period,
            revenue,
            orders,
            sum(revenue) OVER (ORDER BY period
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total_revenue,
            round(
                100.0 * (revenue - lag(revenue) OVER (ORDER BY period))
                      / NULLIF(lag(revenue) OVER (ORDER BY period), 0)
            , 2) AS mom_growth_pct
        FROM per
        ORDER BY period
        """
    )
    rows = conn.execute(sql, {"date_from": date_from, "date_to": date_to})
    return [dict(r) for r in rows.mappings()]


# ---------------------------------------------------------------------------
def top_categories(conn: Connection, limit: int = 10) -> list[dict]:
    sql = text(
        """
        SELECT revenue_rank, category, revenue, items_sold, orders,
               avg_review_score, revenue_share_pct
        FROM analytics.vw_category_performance
        ORDER BY revenue_rank
        LIMIT :limit
        """
    )
    return [dict(r) for r in conn.execute(sql, {"limit": limit}).mappings()]


# ---------------------------------------------------------------------------
def aov(conn: Connection) -> dict:
    overall = conn.execute(
        text(
            """
            SELECT sum(item_revenue)                              AS revenue,
                   count(DISTINCT order_id)                       AS orders,
                   sum(item_revenue) / NULLIF(count(DISTINCT order_id), 0) AS aov
            FROM analytics.fct_order_items
            WHERE order_status = 'delivered'
            """
        )
    ).mappings().one()

    by_category = conn.execute(
        text(
            """
            SELECT dp.category,
                   sum(f.item_revenue) / NULLIF(count(DISTINCT f.order_id), 0) AS aov,
                   count(DISTINCT f.order_id) AS orders,
                   sum(f.item_revenue)        AS revenue
            FROM analytics.fct_order_items f
            JOIN analytics.dim_product dp ON dp.product_id = f.product_id
            WHERE f.order_status = 'delivered'
            GROUP BY dp.category
            ORDER BY revenue DESC
            """
        )
    ).mappings().all()

    # Payment type lives in raw; take the primary payment row (sequential = 1)
    # per order so each order is counted once.
    by_payment = conn.execute(
        text(
            """
            WITH order_rev AS (
                SELECT order_id, sum(item_revenue) AS order_revenue
                FROM analytics.fct_order_items
                WHERE order_status = 'delivered'
                GROUP BY order_id
            ),
            primary_pay AS (
                SELECT order_id, payment_type
                FROM raw.order_payments
                WHERE payment_sequential = 1
            )
            SELECT p.payment_type,
                   sum(o.order_revenue) / NULLIF(count(*), 0) AS aov,
                   count(*)             AS orders,
                   sum(o.order_revenue) AS revenue
            FROM order_rev o
            JOIN primary_pay p ON p.order_id = o.order_id
            GROUP BY p.payment_type
            ORDER BY revenue DESC
            """
        )
    ).mappings().all()

    return {
        "overall": dict(overall),
        "by_category": [dict(r) for r in by_category],
        "by_payment_type": [dict(r) for r in by_payment],
    }


# ---------------------------------------------------------------------------
def delivery_sla(conn: Connection) -> dict:
    by_state = conn.execute(
        text(
            """
            SELECT customer_state, delivered_items, avg_delivery_days, on_time_pct
            FROM analytics.vw_delivery_sla
            ORDER BY delivered_items DESC
            """
        )
    ).mappings().all()

    overall = conn.execute(
        text(
            """
            SELECT
                count(*) FILTER (WHERE order_delivered_customer_date IS NOT NULL)
                                                                   AS delivered_items,
                round(avg(delivery_days), 2)                       AS avg_delivery_days,
                round(
                    100.0 * count(*) FILTER (WHERE on_time IS TRUE)
                          / NULLIF(count(*) FILTER (WHERE on_time IS NOT NULL), 0)
                , 2)                                               AS on_time_pct
            FROM analytics.fct_order_items
            """
        )
    ).mappings().one()

    return {"overall": dict(overall), "by_state": [dict(r) for r in by_state]}


# ---------------------------------------------------------------------------
def seller_scorecard(conn: Connection, limit: int = 20) -> list[dict]:
    sql = text(
        """
        SELECT revenue_rank, seller_id, seller_state, revenue, items_sold,
               orders, avg_review_score, avg_delivery_days
        FROM analytics.vw_seller_scorecard
        ORDER BY revenue_rank
        LIMIT :limit
        """
    )
    return [dict(r) for r in conn.execute(sql, {"limit": limit}).mappings()]


# ---------------------------------------------------------------------------
def repeat_customers(conn: Connection) -> dict:
    # A "customer" is the real person (customer_unique_id). Repeat = >1 distinct
    # delivered order. Revenue share = revenue from repeat customers / total.
    sql = text(
        """
        WITH cust AS (
            SELECT dc.customer_unique_id           AS person,
                   count(DISTINCT f.order_id)       AS orders,
                   sum(f.item_revenue)              AS revenue
            FROM analytics.fct_order_items f
            JOIN analytics.dim_customer dc ON dc.customer_id = f.customer_id
            WHERE f.order_status = 'delivered'
            GROUP BY dc.customer_unique_id
        )
        SELECT
            count(*)                                              AS total_customers,
            count(*) FILTER (WHERE orders > 1)                    AS repeat_customers,
            round(100.0 * count(*) FILTER (WHERE orders > 1)
                  / NULLIF(count(*), 0), 2)                       AS repeat_rate_pct,
            sum(revenue)                                          AS total_revenue,
            sum(revenue) FILTER (WHERE orders > 1)                AS repeat_revenue,
            round(100.0 * sum(revenue) FILTER (WHERE orders > 1)
                  / NULLIF(sum(revenue), 0), 2)                   AS repeat_revenue_share_pct
        FROM cust
        """
    )
    return dict(conn.execute(sql).mappings().one())
