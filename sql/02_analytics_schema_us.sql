-- ============================================================================
-- ANALYTICS SCHEMA — US e-commerce dataset (synthetic, 1M orders)
-- Mirrors 02_analytics_schema.sql's star model, adapted to this dataset's
-- extra columns (customer/seller demographics, product cost/brand, discount).
--   dim_date_us, dim_product_us, dim_customer_us, dim_seller_us
--   fct_order_items_us                                  (grain: one order line)
--   vw_*_us pre-aggregated views, same shape as the Olist ones
-- ============================================================================

DROP SCHEMA IF EXISTS analytics_us CASCADE;
CREATE SCHEMA analytics_us;

-- ----------------------------------------------------------------------------
-- DIMENSIONS
-- ----------------------------------------------------------------------------

-- dim_product_us: category is already English in this dataset (no translation
-- table needed, unlike Olist).
CREATE TABLE analytics_us.dim_product AS
SELECT
    p.product_id,
    p.product_category_name AS category,
    p.product_name,
    p.product_brand,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm,
    p.cost,
    p.price                 AS list_price
FROM raw_us.products p;

ALTER TABLE analytics_us.dim_product ADD PRIMARY KEY (product_id);

-- dim_customer_us
CREATE TABLE analytics_us.dim_customer AS
SELECT
    c.customer_id,
    c.customer_unique_id,
    c.customer_name,
    c.customer_gender AS gender,
    c.customer_age     AS age,
    c.customer_segment AS segment,
    c.customer_zip_code_prefix AS zip_code_prefix,
    c.customer_city             AS city,
    c.customer_state             AS state
FROM raw_us.customers c;

ALTER TABLE analytics_us.dim_customer ADD PRIMARY KEY (customer_id);
CREATE INDEX idx_dim_customer_us_unique ON analytics_us.dim_customer (customer_unique_id);

-- dim_seller_us
CREATE TABLE analytics_us.dim_seller AS
SELECT
    s.seller_id,
    s.seller_company_name AS company_name,
    s.seller_contact_name AS contact_name,
    s.seller_zip_code_prefix AS zip_code_prefix,
    s.seller_city             AS city,
    s.seller_state             AS state
FROM raw_us.sellers s;

ALTER TABLE analytics_us.dim_seller ADD PRIMARY KEY (seller_id);

-- dim_date_us: continuous daily calendar covering the order span.
CREATE TABLE analytics_us.dim_date AS
WITH bounds AS (
    SELECT date_trunc('day', min(order_purchase_timestamp))::date AS d0,
           date_trunc('day', max(order_purchase_timestamp))::date AS d1
    FROM raw_us.orders
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

ALTER TABLE analytics_us.dim_date ADD PRIMARY KEY (date_key);

-- ----------------------------------------------------------------------------
-- FACT: one row per order line item
-- ----------------------------------------------------------------------------
CREATE TABLE analytics_us.fct_order_items AS
WITH order_review AS (
    SELECT order_id, avg(review_score)::numeric(4,2) AS avg_review_score
    FROM raw_us.order_reviews
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
    oi.discount_rate,
    (oi.price + oi.freight_value)                                 AS item_revenue,
    CASE
        WHEN o.order_delivered_customer_date IS NOT NULL
        THEN EXTRACT(epoch FROM (o.order_delivered_customer_date
                                 - o.order_purchase_timestamp)) / 86400.0
    END::numeric(8,2)                                             AS delivery_days,
    CASE
        WHEN o.order_delivered_customer_date IS NULL THEN NULL
        WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date
            THEN true
        ELSE false
    END                                                          AS on_time,
    r.avg_review_score
FROM raw_us.order_items oi
JOIN raw_us.orders   o ON o.order_id = oi.order_id
LEFT JOIN order_review r ON r.order_id = oi.order_id;

CREATE INDEX idx_fct_order_month_us ON analytics_us.fct_order_items (order_month);
CREATE INDEX idx_fct_order_date_us  ON analytics_us.fct_order_items (order_date);
CREATE INDEX idx_fct_product_us     ON analytics_us.fct_order_items (product_id);
CREATE INDEX idx_fct_seller_us      ON analytics_us.fct_order_items (seller_id);
CREATE INDEX idx_fct_customer_us    ON analytics_us.fct_order_items (customer_id);
CREATE INDEX idx_fct_status_us      ON analytics_us.fct_order_items (order_status);

-- ----------------------------------------------------------------------------
-- PRE-AGGREGATED VIEWS (same shape as the Olist ones)
-- ----------------------------------------------------------------------------

CREATE VIEW analytics_us.vw_monthly_revenue AS
WITH monthly AS (
    SELECT
        order_month,
        sum(item_revenue)                AS revenue,
        count(DISTINCT order_id)         AS orders,
        sum(price)                       AS product_revenue,
        sum(freight_value)               AS freight_revenue
    FROM analytics_us.fct_order_items
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

CREATE VIEW analytics_us.vw_category_performance AS
WITH cat AS (
    SELECT
        dp.category,
        sum(f.item_revenue)        AS revenue,
        count(*)                   AS items_sold,
        count(DISTINCT f.order_id) AS orders,
        avg(f.avg_review_score)    AS avg_review_score
    FROM analytics_us.fct_order_items f
    JOIN analytics_us.dim_product dp ON dp.product_id = f.product_id
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

CREATE VIEW analytics_us.vw_seller_scorecard AS
WITH s AS (
    SELECT
        f.seller_id,
        ds.state                   AS seller_state,
        sum(f.item_revenue)        AS revenue,
        count(*)                   AS items_sold,
        count(DISTINCT f.order_id) AS orders,
        avg(f.avg_review_score)    AS avg_review_score,
        avg(f.delivery_days)       AS avg_delivery_days
    FROM analytics_us.fct_order_items f
    JOIN analytics_us.dim_seller ds ON ds.seller_id = f.seller_id
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

CREATE VIEW analytics_us.vw_delivery_sla AS
SELECT
    dc.state                                                       AS customer_state,
    count(*) FILTER (WHERE f.order_delivered_customer_date IS NOT NULL)
                                                                   AS delivered_items,
    round(avg(f.delivery_days), 2)                                 AS avg_delivery_days,
    round(
        100.0 * count(*) FILTER (WHERE f.on_time IS TRUE)
              / NULLIF(count(*) FILTER (WHERE f.on_time IS NOT NULL), 0)
    , 2)                                                           AS on_time_pct
FROM analytics_us.fct_order_items f
JOIN analytics_us.dim_customer dc ON dc.customer_id = f.customer_id
GROUP BY dc.state
ORDER BY delivered_items DESC;

-- ----------------------------------------------------------------------------
-- Grant the read-only role access. Self-contained here (rather than only in
-- 03_app_schema.sql) since this schema gets DROP/CREATE'd independently by
-- load_us.py, potentially after 03_app_schema.sql already ran once — grants
-- on a schema don't survive DROP SCHEMA CASCADE, so they must be reapplied
-- every time this file runs. Guarded in case analytics_ro doesn't exist yet
-- (first-ever run, before `manage.py init`).
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'analytics_ro') THEN
        EXECUTE 'GRANT USAGE ON SCHEMA analytics_us TO analytics_ro';
        EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA analytics_us TO analytics_ro';
        EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA analytics_us GRANT SELECT ON TABLES TO analytics_ro';
        EXECUTE 'REVOKE CREATE ON SCHEMA analytics_us FROM analytics_ro';
        -- Belt and braces: no reach into raw_us (matches the Olist raw/ policy).
        -- Postgres grants nothing on a new schema by default, so this is
        -- defense-in-depth, not a fix for an actual open grant.
        EXECUTE 'REVOKE ALL ON SCHEMA raw_us FROM analytics_ro';
    END IF;
END $$;
