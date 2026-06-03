# Databricks notebook source
"""Job entrypoint — calcula profitability diaria por ruta.

Este archivo es la *capa de orquestación*: lee tablas, llama transforms puros,
escribe resultados. La lógica de negocio vive en `bakery.transforms`
(vendorizado en `src/bakery`), testeada por unit + integration tests.
"""

import os
import sys

# Add the repo's src/ so the vendored `bakery` package imports. DABs deploys this
# notebook under .../files/src/jobs/, whose working dir is that folder, so src/ is its parent.
sys.path.append(os.path.dirname(os.getcwd()))

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

(result.write.mode("overwrite").saveAsTable(f"{catalog}.{schema}.gold_route_profitability"))

print(f"Wrote {result.count()} rows to {catalog}.{schema}.gold_route_profitability")
