-- Q4. Which sellers cause most of the late deliveries?
--
-- Builds a scorecard for sellers with at least 50 delivered orders,
-- splits them into quartiles by late rate with NTILE(4), and shows how much
-- of all late orders the worst quartile is responsible for.
--
-- An order with items from several sellers is counted for each seller
-- (about 1% of orders), which is fine for a scorecard.

WITH seller_orders AS (
    SELECT DISTINCT
        i.seller_id,
        f.order_id,
        f.is_late,
        f.review_score
    FROM fact_order_items i
    JOIN fact_orders f USING (order_id)
    WHERE f.order_status = 'delivered'
      AND f.order_delivered_customer_date IS NOT NULL
),
scorecard AS (
    SELECT
        seller_id,
        COUNT(*)                                     AS orders,
        SUM(CASE WHEN is_late THEN 1 ELSE 0 END)     AS late_orders,
        AVG(CASE WHEN is_late THEN 1.0 ELSE 0.0 END) AS late_rate,
        AVG(review_score)                            AS avg_review
    FROM seller_orders
    GROUP BY seller_id
    HAVING COUNT(*) >= 50
),
ranked AS (
    SELECT
        *,
        NTILE(4) OVER (ORDER BY late_rate DESC) AS late_quartile   -- 1 = worst
    FROM scorecard
)
SELECT
    late_quartile,
    COUNT(*)                                                    AS sellers,
    CAST(SUM(orders) AS INTEGER)                                AS orders,
    ROUND(100.0 * SUM(late_orders) / SUM(orders), 1)            AS late_pct,
    ROUND(AVG(avg_review), 2)                                   AS avg_review,
    ROUND(100.0 * SUM(late_orders) / SUM(SUM(late_orders)) OVER (), 1) AS share_of_all_late_orders_pct
FROM ranked
GROUP BY late_quartile
ORDER BY late_quartile;
