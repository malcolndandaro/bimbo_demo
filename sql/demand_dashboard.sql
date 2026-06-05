-- Vista para el dashboard de pronóstico de demanda — nuevo en este PR.
CREATE OR REPLACE VIEW bimbo_demo.dev.vw_demand_dashboard AS
SELECT
    route_id,
    route_name,
    SUM(forecast_units) AS total_forecast,
    AVG(forecast_units) AS avg_forecast
FROM bimbo_demo.dev.gold_demand_forecast
WHERE region = 'centro'
GROUP BY route_id, route_name
ORDER BY total_forecast DESC
LIMIT 50;
