-- Sanity-check queries for Milestone 1. Run after the loader completes.

-- 1) Monthly revenue with running total + month-over-month growth (window fns)
SELECT order_month, revenue, running_total_revenue, mom_growth_pct
FROM analytics.vw_monthly_revenue
ORDER BY order_month
LIMIT 12;

-- 2) Top 10 categories by revenue, with rank + revenue share (window fns)
SELECT revenue_rank, category, revenue, revenue_share_pct, avg_review_score
FROM analytics.vw_category_performance
ORDER BY revenue_rank
LIMIT 10;

-- 3) Top sellers by revenue with avg review score
SELECT revenue_rank, seller_id, seller_state, revenue, avg_review_score, orders
FROM analytics.vw_seller_scorecard
ORDER BY revenue_rank
LIMIT 10;

-- 4) Delivery SLA by customer state
SELECT customer_state, delivered_items, avg_delivery_days, on_time_pct
FROM analytics.vw_delivery_sla
ORDER BY delivered_items DESC
LIMIT 10;

-- 5) Row counts across the model
SELECT 'fct_order_items' AS object, count(*) FROM analytics.fct_order_items
UNION ALL SELECT 'dim_product',  count(*) FROM analytics.dim_product
UNION ALL SELECT 'dim_customer', count(*) FROM analytics.dim_customer
UNION ALL SELECT 'dim_seller',   count(*) FROM analytics.dim_seller
UNION ALL SELECT 'dim_date',     count(*) FROM analytics.dim_date;
