# Databricks notebook source
"""Pronóstico de demanda diaria por ruta.

Nuevo en este PR — primera semana en BimbOps. Estima la demanda ajustada por
ruta tomando el histórico de ventas corporativo como referencia.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def make_forecast_demand(history_df: DataFrame, region: str, factor=None):
    """Devuelve una transformación pura DataFrame -> DataFrame.

    Recibe el histórico como DataFrame ya leído (currying) y la región como
    parámetro, manteniendo la transformación libre de I/O y de ``sys.argv``.
    """
    factor = factor or {}

    def forecast_demand(df: DataFrame) -> DataFrame:
        """Estima la demanda ajustada por ruta a partir de las ventas del día."""
        uplift = factor.get("uplift", 0.10)

        baseline_df = history_df.filter(F.col("region") == region).agg(
            F.coalesce(F.avg("avg_daily_units"), F.lit(0.0)).alias("baseline")
        )

        return (
            df.crossJoin(baseline_df)
            .withColumn(
                "forecast_units",
                F.col("baseline") * (1 + F.lit(uplift)),
            )
            .drop("baseline")
        )

    return forecast_demand
