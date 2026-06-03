"""Seed the bakery source tables (`fact_sales` + `dim_store`) for `bimbo_demo.<schema>`.

Closes the recovery gap documented in REBUILD.md: these are the pipeline INPUT tables
(read by `src/daily_route_profitability.py`, asserted populated by `tests/`). They were
originally pre-seeded with no in-repo generator; this script regenerates them
synthetically so they are recoverable from the repo on a shared, mutable workspace.

Run locally via Databricks Connect serverless:
    DATABRICKS_AUTH_STORAGE=plaintext python data/seed_bakery.py            # -> bimbo_demo.dev
    BIMBO_SEED_SCHEMA=qa  python data/seed_bakery.py                        # -> bimbo_demo.qa
or as a Databricks notebook/job task (uses the ambient `spark`).

Idempotent: overwrites the tables. Synthetic data only — no PII, safe for a public repo.
The SKU values are intentionally messy (mixed case, spaces, hyphens) so the pipeline's
`normalize_sku` transform has real work to do in the demo.

Schema produced (the exact columns `bakery/transforms.py` consumes):
    dim_store(store_id, route_id, route_name, store_name)
    fact_sales(store_id, sku, quantity, unit_price, amount, is_active, sale_date)
"""

from __future__ import annotations

import os

CATALOG = os.environ.get("BIMBO_SEED_CATALOG", "bimbo_demo")
SCHEMA = os.environ.get("BIMBO_SEED_SCHEMA", "dev")
N_STORES = int(os.environ.get("BIMBO_SEED_STORES", "20"))
N_SALES = int(os.environ.get("BIMBO_SEED_SALES", "5000"))

# Ambient `spark` when run as a Databricks notebook/job; else a serverless Connect session.
try:
    spark  # noqa: F821,B018 (ambient spark provided by the Databricks runtime)
except NameError:
    from databricks.connect import DatabricksSession

    spark = DatabricksSession.builder.serverless(True).getOrCreate()

from pyspark.sql import functions as F  # noqa: E402 (import after the spark bootstrap above)

ROUTES = [
    ("R01", "Ruta Centro"),
    ("R02", "Ruta Norte"),
    ("R03", "Ruta Sur"),
    ("R04", "Ruta Bajío"),
    ("R05", "Ruta Occidente"),
]
# Messy on purpose — exercises normalize_sku (uppercase + strip non-alphanumerics).
SKUS = [
    "pan-blanco 01", "Pan Integral-02", "DONA_03", "mantecada 04",
    "bimbollo-05", "tortilla 06", "Bolillo_07", "concha-08",
    "rol-canela 09", "multigrano 10", "panque-11", "galleta 12",
]

routes_col = F.array(
    *[F.struct(F.lit(r).alias("route_id"), F.lit(n).alias("route_name")) for r, n in ROUTES]
)
skus_col = F.array(*[F.lit(s) for s in SKUS])

# dim_store — N_STORES tiendas repartidas round-robin entre las 5 rutas.
dim_store = (
    spark.range(N_STORES)
    .withColumn("store_id", F.format_string("S%03d", (F.col("id") + 1).cast("int")))
    .withColumn("_r", F.element_at(routes_col, (F.col("id") % F.lit(len(ROUTES)) + 1).cast("int")))
    .withColumn("route_id", F.col("_r.route_id"))
    .withColumn("route_name", F.col("_r.route_name"))
    .withColumn("store_name", F.format_string("Panadería %03d", (F.col("id") + 1).cast("int")))
    .select("store_id", "route_id", "route_name", "store_name")
)

# fact_sales — N_SALES ventas; ~10% devoluciones (quantity/amount negativos), ~85% activas.
fact_sales = (
    spark.range(N_SALES)
    .withColumn(
        "store_id", F.format_string("S%03d", (F.floor(F.rand(7) * N_STORES) + 1).cast("int"))
    )
    .withColumn("sku", F.element_at(skus_col, (F.floor(F.rand(11) * len(SKUS)) + 1).cast("int")))
    .withColumn("_is_return", F.rand(3) < 0.10)
    .withColumn(
        "quantity",
        F.when(F.col("_is_return"), -(F.floor(F.rand(5) * 5) + 1))
        .otherwise(F.floor(F.rand(1) * 50) + 1)
        .cast("int"),
    )
    .withColumn("unit_price", F.round(F.rand(2) * 40 + 5, 2))
    # amount = quantity * unit_price → negativo en devoluciones
    .withColumn("amount", F.round(F.col("quantity") * F.col("unit_price"), 2))
    .withColumn("is_active", F.rand(9) > 0.15)
    .withColumn(
        "sale_date", F.date_sub(F.current_date(), F.floor(F.rand(4) * 30).cast("int"))
    )
    .select("store_id", "sku", "quantity", "unit_price", "amount", "is_active", "sale_date")
)

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
dim_store.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.dim_store")
fact_sales.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.fact_sales")

fq = f"{CATALOG}.{SCHEMA}"
print(
    f"Seeded {fq}.dim_store ({dim_store.count()} rows) "
    f"+ {fq}.fact_sales ({fact_sales.count()} rows)"
)
