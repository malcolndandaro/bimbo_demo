# Databricks notebook source
"""Job entrypoint — calcula profitability diaria por ruta.

Capa de orquestación: lee tablas, llama transforms puros (vendorizados en
`bakery/`, hermano de este archivo), escribe resultados. Vive junto a `bakery/`
para que Databricks lo tenga en el sys.path al ejecutar el notebook (sin hacks).
"""

from bakery.transforms import build_daily_route_profitability

# COMMAND ----------

dbutils.widgets.text("catalog", "bimbo")
dbutils.widgets.text("schema", "dev")
catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

# COMMAND ----------

sales = spark.read.table(f"{catalog}.{schema}.fact_sales")
routes = spark.read.table(f"{catalog}.{schema}.dim_store")

result = build_daily_route_profitability(sales, routes)

(result.write.mode("overwrite").saveAsTable(f"{catalog}.{schema}.gold_route_profitability"))

print(f"Wrote {result.count()} rows to {catalog}.{schema}.gold_route_profitability")
