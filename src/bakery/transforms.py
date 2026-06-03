"""Transformaciones puras sobre DataFrames de ventas de panadería.

Cada función recibe un DataFrame y devuelve un DataFrame — sin efectos
secundarios, sin lectura/escritura, sin SparkSession en parámetros. Esto las
hace componibles con `df.transform(fn)` y testeables con pytest. Vendorizado en
este repo (antes vivía en el snippet 01 vía un `sys.path` externo) para que el
job y los tests de integración lo importen sin hacks.

Referencia: https://community.databricks.com/t5/technical-blog/how-to-use-the-transform-pattern-in-pyspark-for-modular-and/ba-p/117522
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def normalize_sku(df: DataFrame) -> DataFrame:
    """Normaliza el código SKU: uppercase, sin espacios ni caracteres especiales."""
    return df.withColumn(
        "sku",
        F.upper(F.regexp_replace(F.col("sku"), r"[^A-Za-z0-9]", "")),
    )


def filter_active_products(df: DataFrame) -> DataFrame:
    """Conserva solo productos activos."""
    return df.filter(F.col("is_active"))


def mark_returns(df: DataFrame) -> DataFrame:
    """Marca rows de devolución (quantity < 0) y normaliza el signo."""
    return df.withColumn("is_return", F.col("quantity") < 0).withColumn(
        "abs_quantity", F.abs(F.col("quantity"))
    )


def enrich_with_route(routes_df: DataFrame):
    """Currying: devuelve un transform que enriquece ventas con info de ruta.

    Uso: `sales_df.transform(enrich_with_route(routes_df))`.
    """

    def _apply(sales_df: DataFrame) -> DataFrame:
        return sales_df.join(routes_df, on="store_id", how="left")

    return _apply


def calculate_route_revenue(df: DataFrame) -> DataFrame:
    """Agrega revenue por ruta, separando ventas de devoluciones."""
    return df.groupBy("route_id", "route_name").agg(
        F.sum(F.when(~F.col("is_return"), F.col("amount")).otherwise(0)).alias("gross_revenue"),
        F.sum(F.when(F.col("is_return"), F.col("amount")).otherwise(0)).alias("returns_amount"),
        F.sum("amount").alias("net_revenue"),
        F.countDistinct("sku").alias("distinct_skus"),
    )


def build_daily_route_profitability(sales_df: DataFrame, routes_df: DataFrame) -> DataFrame:
    """Pipeline completo en estilo transform-pattern: cada paso independiente y testeable."""
    return (
        sales_df.transform(normalize_sku)
        .transform(filter_active_products)
        .transform(mark_returns)
        .transform(enrich_with_route(routes_df))
        .transform(calculate_route_revenue)
    )
