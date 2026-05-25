-- Ejemplo de SQL que el quality gate debe rechazar.
-- Violaciones intencionales que sqlfluff (dialect=databricks) detecta.

select  -- L010 / capitalisation.keywords — debe ser SELECT
        route_id,
        Route_Name,                          -- mezcla case en identificadores
        sum( gross_revenue ) total_gross,    -- AL01 — debe ser AS total_gross
        sum(returns_amount) AS total_returns,
        sum(NET_REVENUE) total_net           -- mezcla case + alias sin AS
from bimbo_demo.dev.gold_route_profitability  -- línea 4 sin uppercase FROM
where total_net > 1000
group by  route_id, Route_Name,total_net      -- L039 — espaciado inconsistente
having sum(net_revenue)>50000                  -- sin espacios alrededor de >
order by 4 desc                                -- ST06 — order by ordinal position
LIMIT     100                                  -- L009 / espaciado inconsistente
