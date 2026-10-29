-- Q1. How much does a late delivery hurt the customer's review score?
--
-- Approach: put every delivered order into a bucket by how early/late it
-- arrived compared with the date promised at checkout, then compare the
-- average review score and the share of 1-2 star reviews per bucket.

WITH delivered AS (
    SELECT
        order_id,
        days_vs_promise,
        review_score
    FROM fact_orders
    WHERE order_status = 'delivered'
      AND order_delivered_customer_date IS NOT NULL
      AND review_score IS NOT NULL
),
bucketed AS (
    SELECT
        *,
        CASE
            WHEN days_vs_promise <= -7 THEN '1. 7+ days early'
            WHEN days_vs_promise <   0 THEN '2. 1-6 days early'
            WHEN days_vs_promise =   0 THEN '3. on the promised day'
            WHEN days_vs_promise <=  3 THEN '4. 1-3 days late'
            WHEN days_vs_promise <=  7 THEN '5. 4-7 days late'
            ELSE                            '6. 8+ days late'
        END AS delivery_bucket
    FROM delivered
)
SELECT
    delivery_bucket,
    COUNT(*)                                             AS orders,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)   AS pct_of_orders,
    ROUND(AVG(review_score), 2)                          AS avg_review,
    ROUND(100.0 * AVG(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END), 1) AS pct_1_2_star
FROM bucketed
GROUP BY delivery_bucket
ORDER BY delivery_bucket;
