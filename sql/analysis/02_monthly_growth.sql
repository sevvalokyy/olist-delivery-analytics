-- Q2. How did orders, revenue and on-time delivery change month over month?
--
-- Uses LAG() to compare each month with the previous one.
-- 2016 and Sep-Oct 2018 have only a handful of orders (the dataset starts
-- and ends mid-stream), so the trend is limited to Jan 2017 - Aug 2018.

WITH monthly AS (
    SELECT
        d.month_start,
        COUNT(*)                         AS orders,
        SUM(f.items_value)               AS revenue,
        AVG(CASE WHEN f.is_late THEN 1.0 ELSE 0.0 END)
            FILTER (WHERE f.is_late IS NOT NULL) AS late_rate
    FROM fact_orders f
    JOIN dim_date d ON d.date_key = f.purchase_date
    WHERE f.order_status NOT IN ('canceled', 'unavailable')
      AND d.month_start BETWEEN DATE '2017-01-01' AND DATE '2018-08-01'
    GROUP BY d.month_start
)
SELECT
    month_start,
    orders,
    ROUND(revenue, 0)                                                   AS revenue_brl,
    ROUND(100.0 * (orders  - LAG(orders)  OVER w) / LAG(orders)  OVER w, 1) AS orders_mom_pct,
    ROUND(100.0 * (revenue - LAG(revenue) OVER w) / LAG(revenue) OVER w, 1) AS revenue_mom_pct,
    ROUND(100.0 * late_rate, 1)                                         AS late_pct
FROM monthly
WINDOW w AS (ORDER BY month_start)
ORDER BY month_start;
