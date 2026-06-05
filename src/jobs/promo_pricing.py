"""Job de precios promocionales por región (demo BimbOps Reviewer)."""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


def load_pricing_baseline(spark: SparkSession, catalog: str, schema: str) -> DataFrame:
    """Carga la línea base de precios para el ajuste promocional regional."""
    table_name = f"{catalog}.{schema}.pricing_baseline"
    return spark.read.table(table_name)


def apply_promo(df: DataFrame, factor: float) -> DataFrame:
    """Aplica un factor promocional sobre el precio base."""
    return df.withColumn("promo_price", F.col("base_price") * F.lit(factor))
