-- ============================================================================
-- RAW SCHEMA — US e-commerce dataset (synthetic, 1M orders)
-- Tables mirror the 8 source CSVs exactly (column names + order match
-- headers). No constraints/PKs here on purpose — raw is a faithful landing
-- zone. Cleaning and keys happen in the analytics_us layer.
-- ============================================================================

DROP SCHEMA IF EXISTS raw_us CASCADE;
CREATE SCHEMA raw_us;

-- customers.csv
CREATE TABLE raw_us.customers (
    customer_id              text,
    customer_unique_id       text,
    customer_name            text,
    customer_gender          text,
    customer_age             integer,
    customer_zip_code_prefix text,   -- keep as text: leading zeros matter
    customer_city            text,
    customer_state           text,
    customer_segment         text
);

-- geolocation.csv
CREATE TABLE raw_us.geolocation (
    zip_code_prefix   text,
    geolocation_lat   double precision,
    geolocation_lng   double precision,
    geolocation_city  text,
    geolocation_state text
);

-- orders.csv
CREATE TABLE raw_us.orders (
    order_id                      text,
    customer_id                   text,
    order_status                  text,
    order_purchase_timestamp      timestamp,
    order_approved_at             timestamp,
    order_delivered_carrier_date  timestamp,
    order_delivered_customer_date timestamp,
    order_estimated_delivery_date timestamp
);

-- order_items.csv
CREATE TABLE raw_us.order_items (
    order_id            text,
    order_item_id       integer,
    product_id          text,
    seller_id           text,
    shipping_limit_date timestamp,
    price                numeric(12,2),
    freight_value        numeric(12,2),
    discount_rate         numeric(6,4)
);

-- order_payments.csv
CREATE TABLE raw_us.order_payments (
    order_id             text,
    payment_sequential   integer,
    payment_type         text,
    payment_installments integer,
    payment_value        numeric(12,2)
);

-- order_reviews.csv
CREATE TABLE raw_us.order_reviews (
    review_id               text,
    order_id                text,
    review_score            integer,
    review_comment_title    text,
    review_comment_message  text,
    review_creation_date    timestamp,
    review_answer_timestamp timestamp
);

-- products.csv
CREATE TABLE raw_us.products (
    product_id             text,
    product_category_name  text,
    product_name           text,
    product_brand          text,
    product_weight_g       integer,
    product_length_cm      integer,
    product_height_cm      integer,
    product_width_cm       integer,
    cost                    numeric(12,2),
    price                   numeric(12,2)
);

-- sellers.csv
CREATE TABLE raw_us.sellers (
    seller_id            text,
    seller_company_name  text,
    seller_contact_name  text,
    seller_contact_gender text,
    seller_contact_age   integer,
    seller_zip_code_prefix text,
    seller_city          text,
    seller_state         text
);
