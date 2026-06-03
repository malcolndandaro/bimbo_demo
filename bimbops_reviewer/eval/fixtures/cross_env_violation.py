# Eval fixture (KNOWN-BAD): a dev job with a cross-env prod reference (ENV-01) and a
# driver-side .collect() inside transform logic (TP-02 / TP-01). Used by the eval
# harness to verify the reviewer catches the semantic findings. Not deployed.
# ruff: noqa: F821  (illustrative fixture; `spark` is a Databricks runtime global)
from pyspark.sql import functions as F


def adjust_prices(df, pct=0.05):
    baseline = df.select("base_price").collect()[0][0]  # driver action — TP-02
    prod = spark.table("bimbo_prd.gold_pricing")  # cross-env prod ref from dev — ENV-01
    return df.withColumn("adjusted", F.lit(baseline * (1 + pct))).join(prod, "sku")
