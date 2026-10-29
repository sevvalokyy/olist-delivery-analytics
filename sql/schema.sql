-- Star schema built from the cleaned staging tables (stg_*).
--
--                 dim_date
--                    |
--   dim_customer - fact_orders - fact_order_items - dim_product
--                                       |
--                                   dim_seller
--
-- fact_orders      : one row per order (delivery times, money, review score)
-- fact_order_items : one row per item in an order (which seller, which product)

-- ------------------------------------------------------------- dimensions

CREATE OR REPLACE TABLE dim_customer AS
SELECT
    customer_id,                 -- key used by orders (a new id per order)
    customer_unique_id,          -- the real person; use this to find repeat buyers
    customer_zip_code_prefix AS zip_prefix,
    customer_city            AS city,
    customer_state           AS state
FROM stg_customers;

CREATE OR REPLACE TABLE dim_seller AS
SELECT
    seller_id,
    seller_zip_code_prefix AS zip_prefix,
    seller_city            AS city,
    seller_state           AS state
FROM stg_sellers;

CREATE OR REPLACE TABLE dim_product AS
SELECT
    product_id,
    category,
    product_photos_qty AS photos_qty,
    product_weight_g   AS weight_g,
    product_length_cm * product_height_cm * product_width_cm AS volume_cm3
FROM stg_products;

CREATE OR REPLACE TABLE dim_date AS
WITH bounds AS (
    SELECT
        MIN(CAST(order_purchase_timestamp AS DATE)) AS start_date,
        MAX(CAST(order_purchase_timestamp AS DATE)) AS end_date
    FROM stg_orders
)
SELECT
    CAST(d AS DATE)                    AS date_key,
    EXTRACT(year FROM d)               AS year,
    EXTRACT(quarter FROM d)            AS quarter,
    EXTRACT(month FROM d)              AS month,
    CAST(DATE_TRUNC('month', d) AS DATE) AS month_start,
    DAYNAME(d)                         AS day_name,
    ISODOW(d) IN (6, 7)                AS is_weekend
FROM bounds,
     generate_series(start_date, end_date, INTERVAL 1 DAY) AS t(d);

-- ------------------------------------------------------------- facts

CREATE OR REPLACE TABLE fact_order_items AS
SELECT
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    CAST(o.order_purchase_timestamp AS DATE) AS purchase_date,
    i.price,
    i.freight_value
FROM stg_order_items i
JOIN stg_orders o USING (order_id);

CREATE OR REPLACE TABLE fact_orders AS
WITH items AS (
    SELECT
        order_id,
        COUNT(*)              AS items_count,
        COUNT(DISTINCT seller_id) AS sellers_count,
        SUM(price)            AS items_value,
        SUM(freight_value)    AS freight_value
    FROM stg_order_items
    GROUP BY order_id
)
SELECT
    o.order_id,
    o.customer_id,
    CAST(o.order_purchase_timestamp AS DATE) AS purchase_date,     -- joins to dim_date
    o.order_status,
    o.order_purchase_timestamp,
    o.order_delivered_customer_date,
    CAST(o.order_estimated_delivery_date AS DATE) AS estimated_delivery_date,

    -- delivery measures (NULL unless the order was delivered)
    DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_customer_date)
        AS delivery_days,
    DATE_DIFF('day', CAST(o.order_purchase_timestamp AS DATE), CAST(o.order_estimated_delivery_date AS DATE))
        AS promised_days,
    -- positive = arrived after the promised date, negative = arrived early
    DATE_DIFF('day', CAST(o.order_estimated_delivery_date AS DATE), CAST(o.order_delivered_customer_date AS DATE))
        AS days_vs_promise,
    CASE
        WHEN o.order_delivered_customer_date IS NULL THEN NULL
        ELSE CAST(o.order_delivered_customer_date AS DATE) > CAST(o.order_estimated_delivery_date AS DATE)
    END AS is_late,

    -- money
    it.items_count,
    it.sellers_count,
    it.items_value,
    it.freight_value,
    p.payment_value,
    p.payment_type,

    -- customer feedback
    r.review_score
FROM stg_orders o
LEFT JOIN items        it USING (order_id)
LEFT JOIN stg_payments p  USING (order_id)
LEFT JOIN stg_reviews  r  USING (order_id);
