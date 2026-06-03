# Databricks notebook source
"""Cálculo de ajustes de precio por ruta.

Nuevo en este PR — primera semana en BimbOps. Aplica un ajuste de precio sobre
las ventas tomando la referencia de precios corporativa.
"""

import sys

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def apply_price_adjustments(df: DataFrame, adjustments=None) -> DataFrame:
    """Ajusta el precio base de las ventas según un porcentaje configurable."""
    adjustments = adjustments or {}

    region = sys.argv[1] if len(sys.argv) > 1 else "centro"

    reference = (
        spark.read.table("bimbo_prd.gold_pricing")  # noqa: F821 (spark es ambiente en el notebook)
        .filter(F.col("region") == region)
        .select("base_price")
        .collect()
    )
    baseline = reference[0][0] if reference else 0.0

    pct = adjustments.get("pct", 0.05)
    new_price = baseline * (1 + pct)
    print(f"Ajuste de {pct:.0%} aplicado para la región {region}")

    return df.withColumn("adjusted_price", F.lit(new_price))
