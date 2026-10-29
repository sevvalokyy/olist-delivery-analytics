-- Q6. Which product categories drive revenue, and how concentrated is it?
--
-- Running total with SUM() OVER (ORDER BY ...) gives a Pareto view:
-- how many categories make up 80% of revenue.

WITH category_revenue AS (
    SELECT
        p.category,
        COUNT(DISTINCT i.order_id) AS orders,
        SUM(i.price)               AS revenue,
        AVG(i.freight_value / NULLIF(i.price, 0)) AS avg_freight_to_price
    FROM fact_order_items i
    JOIN dim_product p USING (product_id)
    JOIN fact_orders f USING (order_id)
    WHERE f.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY p.category
),
ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (ORDER BY revenue DESC)        AS revenue_rank,
        revenue / SUM(revenue) OVER ()                   AS revenue_share,
        SUM(revenue) OVER (ORDER BY revenue DESC
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            / SUM(revenue) OVER ()                       AS cumulative_share
    FROM category_revenue
)
SELECT
    revenue_rank,
    category,
    orders,
    ROUND(revenue, 0)                    AS revenue_brl,
    ROUND(100.0 * revenue_share, 1)      AS revenue_pct,
    ROUND(100.0 * cumulative_share, 1)   AS cumulative_pct,
    ROUND(100.0 * avg_freight_to_price, 1) AS freight_to_price_pct
FROM ranked
ORDER BY revenue_rank;
