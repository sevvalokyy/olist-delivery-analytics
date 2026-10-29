-- Q5. Do customers come back? And does a bad first delivery change that?
--
-- Repeat-purchase rate (within 90 days and ever), overall and split by
-- whether the customer's FIRST order arrived late.
--
-- customer_unique_id is the real person; customer_id changes on every order.

WITH customer_orders AS (
    SELECT
        c.customer_unique_id,
        f.order_id,
        f.order_purchase_timestamp,
        f.is_late,
        ROW_NUMBER() OVER (
            PARTITION BY c.customer_unique_id
            ORDER BY f.order_purchase_timestamp
        ) AS order_seq
    FROM fact_orders f
    JOIN dim_customer c USING (customer_id)
    WHERE f.order_status NOT IN ('canceled', 'unavailable')
),
first_and_next AS (
    SELECT
        customer_unique_id,
        order_purchase_timestamp                         AS first_purchase,
        is_late                                          AS first_order_late,
        LEAD(order_purchase_timestamp) OVER (
            PARTITION BY customer_unique_id ORDER BY order_seq
        )                                                AS second_purchase,
        order_seq
    FROM customer_orders
),
customers AS (
    SELECT
        customer_unique_id,
        first_order_late,
        second_purchase IS NOT NULL
            AND DATE_DIFF('day', first_purchase, second_purchase) <= 90 AS repeat_90d,
        second_purchase IS NOT NULL                      AS repeat_ever
    FROM first_and_next
    WHERE order_seq = 1
      -- only cohorts with a full 90 days of follow-up in the data
      AND first_purchase < TIMESTAMP '2018-06-01'
)
SELECT
    'by first-order delivery'                         AS view,
    CASE WHEN first_order_late THEN 'first order late'
         WHEN first_order_late = FALSE THEN 'first order on time'
         ELSE 'first order not delivered yet' END     AS segment,
    COUNT(*)                                          AS customers,
    ROUND(100.0 * AVG(CASE WHEN repeat_90d THEN 1 ELSE 0 END), 2)  AS repeat_90d_pct,
    ROUND(100.0 * AVG(CASE WHEN repeat_ever THEN 1 ELSE 0 END), 2) AS repeat_ever_pct
FROM customers
GROUP BY 1, 2

UNION ALL

SELECT
    'all customers',
    'total',
    COUNT(*),
    ROUND(100.0 * AVG(CASE WHEN repeat_90d THEN 1 ELSE 0 END), 2),
    ROUND(100.0 * AVG(CASE WHEN repeat_ever THEN 1 ELSE 0 END), 2)
FROM customers
ORDER BY view, segment;
