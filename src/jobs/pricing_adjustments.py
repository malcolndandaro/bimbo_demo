# Databricks notebook source
"""Cálculo de ajustes de precio por ruta.

Nuevo en este PR — primera semana en BimbOps. Aplica un ajuste de precio sobre
las ventas tomando la referencia de precios corporativa.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def apply_price_adjustments(region: str, pricing_reference: DataFrame, adjustments=None):
    """Devuelve un transform que ajusta el precio base de las ventas.

    El parámetro `region` se inyecta por currying y la tabla de referencia de
    precios se recibe como DataFrame, manteniendo la transformación pura.
    """
    adjustments = adjustments or {}
    pct = adjustments.get("pct", 0.05)

    def _transform(df: DataFrame) -> DataFrame:
        region_baseline = (
            pricing_reference.filter(F.col("region") == region)
            .agg(F.first("base_price").alias("base_price"))
            .withColumn("adjusted_price", F.col("base_price") * (1 + pct))
            .select("adjusted_price")
        )

        return df.crossJoin(region_baseline)

    return _transform
