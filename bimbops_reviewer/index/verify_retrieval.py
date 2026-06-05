"""Verify the BimbOps Handbook index returns the right rule per query (slice 02 AC).

Asserts the two acceptance queries from the issue:
  - a cross-environment reference query surfaces the Catalog-per-Env rule (ENV-01)
  - a driver-side .collect() query surfaces a Transform-pattern rule (TP-*)

Run:  DATABRICKS_AUTH_STORAGE=plaintext python bimbops_reviewer/index/verify_retrieval.py
Exits non-zero if any expectation fails.
"""

from __future__ import annotations

import sys

from databricks.sdk import WorkspaceClient

INDEX = "bimbo.dev.bimbops_handbook_rules_idx"
COLUMNS = ["rule_id", "title", "citation", "severity_hint"]

CHECKS = [
    {
        "label": "cross-environment prod reference from a dev job",
        "query": (
            "un job de dev que referencia el catálogo bimbo_prd gold_pricing "
            "de otro ambiente (cross-environment prod reference)"
        ),
        "expect_exact": "ENV-01",
    },
    {
        "label": "driver-side .collect() inside a transformation",
        "query": (
            "usar .collect() para traer datos al driver dentro de una función "
            "de transformación de PySpark"
        ),
        "expect_prefix": "TP-",
    },
]


def main() -> None:
    w = WorkspaceClient()
    failures = 0
    for c in CHECKS:
        res = w.vector_search_indexes.query_index(
            index_name=INDEX, columns=COLUMNS, query_text=c["query"], num_results=3
        )
        rows = res.result.data_array or []
        top_ids = [r[0] for r in rows]
        print(f"\n▶ {c['label']}")
        for r in rows:
            print(f"    {r[0]:<8} {r[1][:60]:<60} score={r[-1]:.3f}  ({r[2]})")
        ok = False
        if "expect_exact" in c:
            ok = top_ids and top_ids[0] == c["expect_exact"]
            target = c["expect_exact"]
        else:
            ok = any(rid.startswith(c["expect_prefix"]) for rid in top_ids)
            target = c["expect_prefix"] + "*"
        print(f"    => expect {target}: {'PASS' if ok else 'FAIL'} (top: {top_ids})")
        failures += 0 if ok else 1

    if failures:
        print(f"\n❌ {failures} retrieval check(s) failed")
        sys.exit(1)
    print("\n✅ all retrieval checks passed")


if __name__ == "__main__":
    main()
