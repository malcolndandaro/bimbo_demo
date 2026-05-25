# Databricks notebook source
"""Job entrypoint — calcula profitability diaria por ruta.

Este archivo es la *capa de orquestación*: lee tablas, llama transforms puros,
escribe resultados. La lógica de negocio vive en `bakery.transforms` (snippet
01) que se testea unitariamente sin Databricks.
"""
import sys

sys.path.append("../../01-transform-pattern/src")  # demo only

from bakery.transforms import build_daily_route_profitability  # noqa: E402

# COMMAND ----------

dbutils.widgets.text("catalog", "bimbo_demo")
dbutils.widgets.text("schema", "dev")
catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

# COMMAND ----------

sales = spark.read.table(f"{catalog}.{schema}.fact_sales")
routes = spark.read.table(f"{catalog}.{schema}.dim_store")

result = build_daily_route_profitability(sales, routes)

(
    result
    .write.mode("overwrite")
    .saveAsTable(f"{catalog}.{schema}.gold_route_profitability")
)

print(f"Wrote {result.count()} rows to {catalog}.{schema}.gold_route_profitability")
