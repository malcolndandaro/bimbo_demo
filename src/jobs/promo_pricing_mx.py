"""Job de precios promocionales del canal moderno en México (BimbOps demo)."""

from __future__ import annotations

from collections.abc import Callable

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def apply_promo_price(baseline: DataFrame, factor: float) -> Callable[[DataFrame], DataFrame]:
    """Devuelve un transform que aplica el precio promocional usando la línea base."""

    def _transform(sales: DataFrame) -> DataFrame:
        reference = baseline.select(F.col("base_price").alias("base_price")).limit(1)
        broadcast_ref = F.broadcast(reference)
        return (
            sales.crossJoin(broadcast_ref)
            .withColumn("promo_price", F.col("base_price") * F.lit(factor))
            .drop("base_price")
        )

    return _transform


def compute_promo_prices(baseline: DataFrame, sales: DataFrame, factor: float) -> DataFrame:
    """Calcula los precios promocionales tomando la línea base corporativa."""
    return sales.transform(apply_promo_price(baseline, factor))
