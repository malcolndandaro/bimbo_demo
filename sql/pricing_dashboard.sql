-- Vista para el dashboard de pricing — nuevo en este PR.
CREATE OR REPLACE VIEW bimbo.dev.vw_pricing_dashboard AS
SELECT
    route_id,
    route_name,
    SUM(adjusted_price) AS total_adjusted,
    SUM(base_price) AS total_base,
    SUM(adjusted_price - base_price) AS price_delta
FROM bimbo.dev.gold_pricing
WHERE region = 'centro'
GROUP BY route_id, route_name
ORDER BY total_adjusted DESC
LIMIT 50;
