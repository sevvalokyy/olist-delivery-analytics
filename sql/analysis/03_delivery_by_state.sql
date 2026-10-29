-- Q3. Which customer states get the slowest and least reliable deliveries?
--
-- For each state: average delivery time, how many days the checkout promise
-- was padded, and the late rate. RANK() orders states from worst to best.
-- States with fewer than 300 delivered orders are left out to avoid noise.

WITH delivered AS (
    SELECT
        c.state,
        f.delivery_days,
        f.promised_days,
        f.is_late,
        f.review_score
    FROM fact_orders f
    JOIN dim_customer c USING (customer_id)
    WHERE f.order_status = 'delivered'
      AND f.order_delivered_customer_date IS NOT NULL
),
by_state AS (
    SELECT
        state,
        COUNT(*)                                     AS orders,
        AVG(delivery_days)                           AS avg_delivery_days,
        AVG(promised_days)                           AS avg_promised_days,
        AVG(CASE WHEN is_late THEN 1.0 ELSE 0.0 END) AS late_rate,
        AVG(review_score)                            AS avg_review
    FROM delivered
    GROUP BY state
    HAVING COUNT(*) >= 300
)
SELECT
    RANK() OVER (ORDER BY late_rate DESC)           AS late_rank,
    state,
    orders,
    ROUND(avg_delivery_days, 1)                     AS avg_delivery_days,
    ROUND(avg_promised_days, 1)                     AS avg_promised_days,
    ROUND(avg_promised_days - avg_delivery_days, 1) AS avg_buffer_days,
    ROUND(100.0 * late_rate, 1)                     AS late_pct,
    ROUND(avg_review, 2)                            AS avg_review
FROM by_state
ORDER BY late_rank;
