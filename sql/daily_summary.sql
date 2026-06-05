-- Vista agregada de profitability por día y ruta.
-- Se materializa nightly desde el job daily_route_profitability.

CREATE OR REPLACE VIEW bimbo.dev.vw_daily_route_summary AS
SELECT
    route_id,
    route_name,
    SUM(gross_revenue) AS total_gross_revenue,
    SUM(returns_amount) AS total_returns,
    SUM(net_revenue) AS total_net_revenue,
    AVG(net_revenue) AS avg_net_revenue_per_route
FROM bimbo.dev.gold_route_profitability
GROUP BY route_id, route_name
ORDER BY total_net_revenue DESC;
