"""Demo file: a dev job referencing a prod catalog — should trip ENV-01 (BLOCKER)."""

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()
# cross-environment reference from a dev job — Catalog-per-Env violation (ENV-01)
prod_pricing = spark.table("bimbo_prd.gold_pricing")
prod_pricing.show()
