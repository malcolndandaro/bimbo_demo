"""Job de precios estacionales por temporada (BimbOps demo)."""

from __future__ import annotations

from collections.abc import Callable

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def add_seasonal_price(season_factor: float) -> Callable[[DataFrame], DataFrame]:
    """Devuelve un transform que aplica el factor estacional al precio ancla."""

    def _transform(sales: DataFrame) -> DataFrame:
        return sales.withColumn(
            "seasonal_price",
            F.col("base_price") * F.lit(season_factor),
        )

    return _transform


def attach_anchor_price(baseline: DataFrame) -> Callable[[DataFrame], DataFrame]:
    """Devuelve un transform que adjunta el precio ancla de forma declarativa."""

    season_window = Window.orderBy("season")
    anchor = (
        baseline.withColumn("rn", F.row_number().over(season_window))
        .where(F.col("rn") == 1)
        .select(F.col("base_price").alias("base_price"))
    )

    def _transform(sales: DataFrame) -> DataFrame:
        return sales.crossJoin(anchor)

    return _transform


def build_seasonal_prices(
    spark: SparkSession,
    catalog: str,
    schema: str,
    season_factor: float,
) -> DataFrame:
    """Genera los precios estacionales a partir de la línea base del ambiente."""
    baseline = spark.read.table(f"{catalog}.{schema}.seasonal_baseline")
    sales = spark.read.table(f"{catalog}.{schema}.fact_sales")

    return sales.transform(attach_anchor_price(baseline)).transform(
        add_seasonal_price(season_factor)
    )
