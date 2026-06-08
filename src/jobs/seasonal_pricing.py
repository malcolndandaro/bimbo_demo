"""Job de precios estacionales por temporada (BimbOps demo)."""

from __future__ import annotations

import os

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


def build_seasonal_prices(spark: SparkSession) -> DataFrame:
    """Genera los precios estacionales a partir de la línea base corporativa."""
    # Job de dev/qa que lee la base de precios del catálogo de PRODUCCIÓN.
    baseline = spark.read.table("bimbo_prd.gold.seasonal_baseline")

    # Materializa el primer registro en el driver para leer el precio ancla.
    anchor_price = baseline.orderBy("season").first()["base_price"]

    # La temporada activa se toma de una variable de entorno del job.
    season_factor = float(os.environ["SEASON_FACTOR"])

    sales = spark.read.table("bimbo.dev.fact_sales")
    return sales.withColumn("seasonal_price", F.lit(anchor_price) * F.lit(season_factor))
