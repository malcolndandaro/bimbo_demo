"""Serverless integration tests for the daily route-profitability pipeline (slice 07).

Runs against bimbo.dev via Databricks Connect serverless — exercises the SAME
vendored transform the job uses, against real UC tables. Robust to the existing
seeded data (asserts structure + invariants, not hardcoded row counts).
"""

from __future__ import annotations

from bakery.transforms import build_daily_route_profitability, normalize_sku

_AGG_COLUMNS = {
    "route_id",
    "route_name",
    "gross_revenue",
    "returns_amount",
    "net_revenue",
    "distinct_skus",
}


def test_source_tables_exist_and_populated(spark, fqn):
    assert spark.read.table(fqn("fact_sales")).count() > 0
    assert spark.read.table(fqn("dim_store")).count() > 0


def test_normalize_sku_is_idempotent_on_real_data(spark, fqn):
    sales = spark.read.table(fqn("fact_sales"))
    once = sales.transform(normalize_sku).select("sku")
    twice = once.transform(normalize_sku)
    # normalizing twice == normalizing once (no drift)
    assert once.subtract(twice).count() == 0


def test_pipeline_produces_route_aggregates(spark, fqn):
    sales = spark.read.table(fqn("fact_sales"))
    stores = spark.read.table(fqn("dim_store"))
    result = build_daily_route_profitability(sales, stores)

    assert set(result.columns) >= _AGG_COLUMNS
    rows = result.collect()
    assert len(rows) >= 1  # at least one route aggregated
    for r in rows:
        # net revenue = gross + returns (returns are negative), within float tolerance
        assert r["net_revenue"] is not None
        assert abs(r["net_revenue"] - (r["gross_revenue"] + r["returns_amount"])) < 1e-6
        assert r["distinct_skus"] >= 1
