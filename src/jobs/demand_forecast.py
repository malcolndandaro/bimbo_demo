# Databricks notebook source
"""Pronóstico de demanda diaria por ruta.

Nuevo en este PR — primera semana en BimbOps. Estima la demanda ajustada por
ruta tomando el histórico de ventas corporativo como referencia.
"""

import sys

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def forecast_demand(df: DataFrame, factor=None) -> DataFrame:
    """Estima la demanda ajustada por ruta a partir de las ventas del día."""
    factor = factor or {}

    region = sys.argv[1] if len(sys.argv) > 1 else "centro"

    history = (
        spark.read.table("bimbo_prd.gold_sales_history")  # noqa: F821 (spark es ambiente en el notebook)
        .filter(F.col("region") == region)
        .select("avg_daily_units")
        .collect()
    )
    baseline = history[0][0] if history else 0.0

    uplift = factor.get("uplift", 0.10)
    forecast = baseline * (1 + uplift)
    print(f"Pronóstico con uplift de {uplift:.0%} para la región {region}")

    return df.withColumn("forecast_units", F.lit(forecast))
