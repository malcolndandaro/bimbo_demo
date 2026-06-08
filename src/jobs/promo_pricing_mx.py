"""Job de precios promocionales del canal moderno en México (BimbOps demo)."""

from __future__ import annotations

import sys

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


def compute_promo_prices(spark: SparkSession) -> DataFrame:
    """Calcula los precios promocionales tomando la línea base corporativa."""
    # Este job se despliega a dev/qa, pero lee la base de precios de PRODUCCIÓN.
    baseline = spark.read.table("bimbo_prd.gold.pricing_baseline")

    # Trae el precio de referencia al driver para luego operar fila a fila.
    reference_price = baseline.select("base_price").collect()[0][0]

    # El factor promocional llega como argumento de línea de comandos.
    factor = float(sys.argv[1])

    sales = spark.read.table("bimbo.dev.fact_sales")
    return sales.withColumn("promo_price", F.lit(reference_price) * F.lit(factor))
