-- ============================================================================
-- ANALYTICS SCHEMA
-- Star-style model built from the raw landing zone:
--   dim_date, dim_product, dim_customer, dim_seller   (dimension tables)
--   fct_order_items                                   (grain: one order line)
--   vw_* pre-aggregated views consumed by the reporting API
--
-- Window functions live in the views:
--   * running total of revenue         -> vw_monthly_revenue
--   * month-over-month growth %         -> vw_monthly_revenue
--   * category rank by revenue          -> vw_category_performance
-- ============================================================================

DROP SCHEMA IF EXISTS analytics CASCADE;
CREATE SCHEMA analytics;

-- ----------------------------------------------------------------------------
-- DIMENSIONS
-- ----------------------------------------------------------------------------

-- dim_product: one row per product, with English category name resolved.
CREATE TABLE analytics.dim_product AS
SELECT
    p.product_id,
    p.product_category_name                                       AS category_pt,
    COALESCE(t.product_category_name_english,
             p.product_category_name,
             'unknown')                                           AS category,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm
FROM raw.products p
LEFT JOIN raw.product_category_name_translation t
       ON t.product_category_name = p.product_category_name;

ALTER TABLE analytics.dim_product ADD PRIMARY KEY (product_id);

-- dim_customer: customer_id is the per-order key; customer_unique_id identifies
-- the real person (used for repeat-purchase analysis later).
CREATE TABLE analytics.dim_customer AS
SELECT
    c.customer_id,
    c.customer_unique_id,
    c.customer_zip_code_prefix AS zip_code_prefix,
    c.customer_city            AS city,
    c.customer_state           AS state
FROM raw.customers c;

ALTER TABLE analytics.dim_customer ADD PRIMARY KEY (customer_id);
CREATE INDEX idx_dim_customer_unique ON analytics.dim_customer (customer_unique_id);

-- dim_seller
CREATE TABLE analytics.dim_seller AS
SELECT
    s.seller_id,
    s.seller_zip_code_prefix AS zip_code_prefix,
    s.seller_city            AS city,
    s.seller_state           AS state
FROM raw.sellers s;

ALTER TABLE analytics.dim_seller ADD PRIMARY KEY (seller_id);

-- dim_date: continuous daily calendar covering the order span.
CREATE TABLE analytics.dim_date AS
WITH bounds AS (
    SELECT date_trunc('day', min(order_purchase_timestamp))::date AS d0,
           date_trunc('day', max(order_purchase_timestamp))::date AS d1
    FROM raw.orders
    WHERE order_purchase_timestamp IS NOT NULL
)
SELECT
    d::date                                   AS date_key,
    EXTRACT(year   FROM d)::int               AS year,
    EXTRACT(quarter FROM d)::int              AS quarter,
    EXTRACT(month  FROM d)::int               AS month,
    to_char(d, 'YYYY-MM')                     AS year_month,
    EXTRACT(day    FROM d)::int               AS day,
    EXTRACT(isodow FROM d)::int               AS iso_dow,
    to_char(d, 'Day')                         AS weekday_name,
    (EXTRACT(isodow FROM d) >= 6)             AS is_weekend
FROM bounds, generate_series(bounds.d0, bounds.d1, interval '1 day') AS g(d);

ALTER TABLE analytics.dim_date ADD PRIMARY KEY (date_key);

-- ----------------------------------------------------------------------------
-- FACT: one row per order line item
-- ----------------------------------------------------------------------------
-- Payments are per-order (not per-item); attaching them per line would double
-- count, so the order-level review score is averaged and joined, while revenue
-- is derived purely from the line (price + freight).
CREATE TABLE analytics.fct_order_items AS
WITH order_review AS (
    SELECT order_id, avg(review_score)::numeric(4,2) AS avg_review_score
    FROM raw.order_reviews
    WHERE review_score IS NOT NULL
    GROUP BY order_id
)
SELECT
    oi.order_id,
    oi.order_item_id,
    oi.product_id,
    oi.seller_id,
    o.customer_id,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_purchase_timestamp::date                              AS order_date,
    date_trunc('month', o.order_purchase_timestamp)::date         AS order_month,
    o.order_approved_at,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    oi.price,
    oi.freight_value,
    (oi.price + oi.freight_value)                                 AS item_revenue,
    -- delivery_days: only meaningful once actually delivered
    CASE
        WHEN o.order_delivered_customer_date IS NOT NULL
        THEN EXTRACT(epoch FROM (o.order_delivered_customer_date
                                 - o.order_purchase_timestamp)) / 86400.0
    END::numeric(8,2)                                             AS delivery_days,
    -- on_time: delivered on or before the customer-facing estimate
    CASE
        WHEN o.order_delivered_customer_date IS NULL THEN NULL
        WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date
            THEN true
        ELSE false
    END                                                          AS on_time,
    r.avg_review_score
FROM raw.order_items oi
JOIN raw.orders   o ON o.order_id = oi.order_id
LEFT JOIN order_review r ON r.order_id = oi.order_id;

CREATE INDEX idx_fct_order_month   ON analytics.fct_order_items (order_month);
CREATE INDEX idx_fct_order_date    ON analytics.fct_order_items (order_date);
CREATE INDEX idx_fct_product       ON analytics.fct_order_items (product_id);
CREATE INDEX idx_fct_seller        ON analytics.fct_order_items (seller_id);
CREATE INDEX idx_fct_customer      ON analytics.fct_order_items (customer_id);
CREATE INDEX idx_fct_status        ON analytics.fct_order_items (order_status);

-- ----------------------------------------------------------------------------
-- PRE-AGGREGATED VIEWS (consumed by the FastAPI reporting layer)
-- ----------------------------------------------------------------------------

-- vw_monthly_revenue
--   WINDOW FUNCTIONS: running_total (cumulative SUM), mom_growth_pct (LAG).
--   "delivered"-status orders only, so revenue reflects realised sales.
CREATE VIEW analytics.vw_monthly_revenue AS
WITH monthly AS (
    SELECT
        order_month,
        sum(item_revenue)                AS revenue,
        count(DISTINCT order_id)         AS orders,
        sum(price)                       AS product_revenue,
        sum(freight_value)               AS freight_revenue
    FROM analytics.fct_order_items
    WHERE order_status = 'delivered'
    GROUP BY order_month
)
SELECT
    order_month,
    revenue,
    orders,
    product_revenue,
    freight_revenue,
    sum(revenue) OVER (ORDER BY order_month
                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                                          AS running_total_revenue,
    round(
        100.0 * (revenue - lag(revenue) OVER (ORDER BY order_month))
              / NULLIF(lag(revenue) OVER (ORDER BY order_month), 0)
    , 2)                                  AS mom_growth_pct
FROM monthly
ORDER BY order_month;

-- vw_category_performance
--   WINDOW FUNCTION: revenue_rank (RANK over revenue desc) + revenue share.
CREATE VIEW analytics.vw_category_performance AS
WITH cat AS (
    SELECT
        dp.category,
        sum(f.item_revenue)        AS revenue,
        count(*)                   AS items_sold,
        count(DISTINCT f.order_id) AS orders,
        avg(f.avg_review_score)    AS avg_review_score
    FROM analytics.fct_order_items f
    JOIN analytics.dim_product dp ON dp.product_id = f.product_id
    WHERE f.order_status = 'delivered'
    GROUP BY dp.category
)
SELECT
    category,
    revenue,
    items_sold,
    orders,
    round(avg_review_score, 2)                                   AS avg_review_score,
    rank() OVER (ORDER BY revenue DESC)                          AS revenue_rank,
    round(100.0 * revenue / sum(revenue) OVER (), 2)             AS revenue_share_pct
FROM cat
ORDER BY revenue DESC;

-- vw_seller_scorecard: seller revenue + avg review, ranked by revenue.
CREATE VIEW analytics.vw_seller_scorecard AS
WITH s AS (
    SELECT
        f.seller_id,
        ds.state                   AS seller_state,
        sum(f.item_revenue)        AS revenue,
        count(*)                   AS items_sold,
        count(DISTINCT f.order_id) AS orders,
        avg(f.avg_review_score)    AS avg_review_score,
        avg(f.delivery_days)       AS avg_delivery_days
    FROM analytics.fct_order_items f
    JOIN analytics.dim_seller ds ON ds.seller_id = f.seller_id
    WHERE f.order_status = 'delivered'
    GROUP BY f.seller_id, ds.state
)
SELECT
    seller_id,
    seller_state,
    revenue,
    items_sold,
    orders,
    round(avg_review_score, 2)               AS avg_review_score,
    round(avg_delivery_days, 2)              AS avg_delivery_days,
    rank() OVER (ORDER BY revenue DESC)      AS revenue_rank
FROM s
ORDER BY revenue DESC;

-- vw_delivery_sla: on-time % and avg delivery days by customer state.
CREATE VIEW analytics.vw_delivery_sla AS
SELECT
    dc.state                                                       AS customer_state,
    count(*) FILTER (WHERE f.order_delivered_customer_date IS NOT NULL)
                                                                   AS delivered_items,
    round(avg(f.delivery_days), 2)                                 AS avg_delivery_days,
    round(
        100.0 * count(*) FILTER (WHERE f.on_time IS TRUE)
              / NULLIF(count(*) FILTER (WHERE f.on_time IS NOT NULL), 0)
    , 2)                                                           AS on_time_pct
FROM analytics.fct_order_items f
JOIN analytics.dim_customer dc ON dc.customer_id = f.customer_id
GROUP BY dc.state
ORDER BY delivered_items DESC;
