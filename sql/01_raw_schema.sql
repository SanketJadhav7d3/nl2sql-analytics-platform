-- ============================================================================
-- RAW SCHEMA
-- Tables mirror the 9 Olist CSVs exactly (column names + order match headers).
-- No constraints/PKs here on purpose: raw is a faithful landing zone for the
-- source files (the Olist data contains some duplicate review_id / order_id
-- rows). Cleaning and keys happen in the analytics layer.
-- ============================================================================

DROP SCHEMA IF EXISTS raw CASCADE;
CREATE SCHEMA raw;

-- olist_customers_dataset.csv
CREATE TABLE raw.customers (
    customer_id              text,
    customer_unique_id       text,
    customer_zip_code_prefix text,   -- keep as text: leading zeros matter ("01037")
    customer_city            text,
    customer_state           text
);

-- olist_geolocation_dataset.csv
CREATE TABLE raw.geolocation (
    geolocation_zip_code_prefix text,
    geolocation_lat             double precision,
    geolocation_lng             double precision,
    geolocation_city            text,
    geolocation_state           text
);

-- olist_order_items_dataset.csv
CREATE TABLE raw.order_items (
    order_id            text,
    order_item_id       integer,
    product_id          text,
    seller_id           text,
    shipping_limit_date timestamp,
    price               numeric(12,2),
    freight_value       numeric(12,2)
);

-- olist_order_payments_dataset.csv
CREATE TABLE raw.order_payments (
    order_id             text,
    payment_sequential   integer,
    payment_type         text,
    payment_installments integer,
    payment_value        numeric(12,2)
);

-- olist_order_reviews_dataset.csv
CREATE TABLE raw.order_reviews (
    review_id               text,
    order_id                text,
    review_score            integer,
    review_comment_title    text,
    review_comment_message  text,
    review_creation_date    timestamp,
    review_answer_timestamp timestamp
);

-- olist_orders_dataset.csv
CREATE TABLE raw.orders (
    order_id                      text,
    customer_id                   text,
    order_status                  text,
    order_purchase_timestamp      timestamp,
    order_approved_at             timestamp,
    order_delivered_carrier_date  timestamp,
    order_delivered_customer_date timestamp,
    order_estimated_delivery_date timestamp
);

-- olist_products_dataset.csv
CREATE TABLE raw.products (
    product_id                 text,
    product_category_name      text,
    product_name_lenght        integer,   -- typo "lenght" preserved from source
    product_description_lenght integer,
    product_photos_qty         integer,
    product_weight_g           integer,
    product_length_cm          integer,
    product_height_cm          integer,
    product_width_cm           integer
);

-- olist_sellers_dataset.csv
CREATE TABLE raw.sellers (
    seller_id              text,
    seller_zip_code_prefix text,
    seller_city            text,
    seller_state           text
);

-- product_category_name_translation.csv
CREATE TABLE raw.product_category_name_translation (
    product_category_name         text,
    product_category_name_english text
);
