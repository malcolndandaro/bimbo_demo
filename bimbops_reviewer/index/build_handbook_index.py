"""Build the BimbOps Handbook rules table + Vector Search index (slice 02).

Parses the structured `### [RULE-ID]` rule blocks out of ../bimbops_handbook/*.md,
writes one row per rule to a UC volume as JSONL, materializes
`bimbo_demo.dev.bimbops_handbook_rules` (Change Data Feed on), and creates/syncs the
Delta Sync index `bimbo_demo.dev.bimbops_handbook_rules_idx` on the `bimbops-vs`
endpoint with managed `databricks-gte-large-en` embeddings.

Run:  DATABRICKS_AUTH_STORAGE=plaintext python bimbops_reviewer/index/build_handbook_index.py

SDK-only (no databricks-connect): statement execution for DDL, Vector Search API
for the index. Idempotent — safe to re-run after editing a rule.
"""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import re
import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState
from databricks.sdk.service.vectorsearch import (
    DeltaSyncVectorIndexSpecRequest,
    EmbeddingSourceColumn,
    PipelineType,
    VectorIndexType,
)

CATALOG = "bimbo_demo"
SCHEMA = "dev"
TABLE = f"{CATALOG}.{SCHEMA}.bimbops_handbook_rules"
INDEX = f"{CATALOG}.{SCHEMA}.bimbops_handbook_rules_idx"
VS_ENDPOINT = "bimbops-vs"
EMBED_MODEL = "databricks-gte-large-en"
VOLUME_DIR = f"/Volumes/{CATALOG}/{SCHEMA}/handbook_volume/bimbops_rules"
VOLUME_FILE = f"{VOLUME_DIR}/rules.jsonl"

HANDBOOK_DIR = pathlib.Path(__file__).resolve().parents[2] / "bimbops_handbook"
RULE_RE = re.compile(r"^###\s+\[(?P<id>[A-Z]+-\d+)\]\s+(?P<title>.+?)\s*$", re.M)


def parse_rules() -> list[dict]:
    """Extract one dict per `### [RULE-ID]` block across every handbook doc."""
    rules: list[dict] = []
    for md in sorted(HANDBOOK_DIR.glob("*.md")):
        if md.name == "README.md":
            continue
        category = md.stem
        text = md.read_text(encoding="utf-8")
        matches = list(RULE_RE.finditer(text))
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            block = text[start:end].strip()
            severity = _field(block, "Severity") or "SUGGESTION"
            citation = (
                _field(block, "Citation") or f"BimbOps Handbook › {category} › {m.group('id')}"
            )
            body = "\n".join(
                ln
                for ln in block.splitlines()
                if not ln.strip().startswith("- **Severity:**")
                and not ln.strip().startswith("- **Citation:**")
            ).strip()
            rules.append(
                {
                    "rule_id": m.group("id"),
                    "title": m.group("title").strip(),
                    # content is what gets embedded — include title + body (with ❌/✅
                    # examples) so the technical keywords drive retrieval.
                    "content": f"{m.group('title').strip()}\n\n{body}",
                    "citation": citation,
                    "category": category,
                    "severity_hint": severity.upper(),
                }
            )
    return rules


def _field(block: str, name: str) -> str | None:
    m = re.search(rf"-\s+\*\*{name}:\*\*\s+(.+)", block)
    return m.group(1).strip() if m else None


def pick_warehouse(w: WorkspaceClient) -> str:
    running = [
        wh
        for wh in w.warehouses.list()
        if str(wh.state) == "State.RUNNING" or getattr(wh.state, "value", "") == "RUNNING"
    ]
    if not running:
        raise SystemExit("No RUNNING SQL warehouse found; start one and re-run.")
    running.sort(key=lambda wh: (not bool(getattr(wh, "enable_serverless_compute", False)),))
    wh = running[0]
    serverless = getattr(wh, "enable_serverless_compute", "?")
    print(f"  using warehouse: {wh.name} ({wh.id}) serverless={serverless}")
    return wh.id


def run_sql(w: WorkspaceClient, wid: str, sql: str) -> None:
    r = w.statement_execution.execute_statement(warehouse_id=wid, statement=sql, wait_timeout="50s")
    sid = r.statement_id
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(2)
        r = w.statement_execution.get_statement(sid)
    if r.status.state != StatementState.SUCCEEDED:
        err = getattr(r.status, "error", None)
        raise SystemExit(f"SQL failed ({r.status.state}): {err}\n{sql[:200]}")


def main() -> None:
    w = WorkspaceClient()
    print("1/5 parsing handbook rules…")
    rules = parse_rules()
    ids = [r["rule_id"] for r in rules]
    print(f"  parsed {len(rules)} rules: {', '.join(ids)}")
    for required in ("ENV-01", "TP-02", "SEC-02"):
        assert required in ids, f"expected rule {required} missing from handbook"

    print("2/5 uploading rules JSONL to volume…")
    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in rules).encode("utf-8")
    with contextlib.suppress(Exception):
        w.files.create_directory(VOLUME_DIR)
    w.files.upload(VOLUME_FILE, io.BytesIO(payload), overwrite=True)
    print(f"  wrote {VOLUME_FILE}")

    print("3/5 (re)creating Delta table with CDF…")
    wid = pick_warehouse(w)
    # TABLE and VOLUME_FILE are trusted module constants (not external input), and
    # DDL identifiers cannot be parameterized — safe by construction.
    create_sql = f"""
        CREATE OR REPLACE TABLE {TABLE}
        TBLPROPERTIES (delta.enableChangeDataFeed = true)
        AS SELECT rule_id, title, content, citation, category, severity_hint
        FROM read_files('{VOLUME_FILE}', format => 'json', multiLine => false)
    """  # noqa: S608
    run_sql(w, wid, create_sql)
    print(f"  table {TABLE} ready")

    print("4/5 creating Delta Sync index (skip if exists)…")
    try:
        w.vector_search_indexes.create_index(
            name=INDEX,
            endpoint_name=VS_ENDPOINT,
            primary_key="rule_id",
            index_type=VectorIndexType.DELTA_SYNC,
            delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
                source_table=TABLE,
                pipeline_type=PipelineType.TRIGGERED,
                embedding_source_columns=[
                    EmbeddingSourceColumn(name="content", embedding_model_endpoint_name=EMBED_MODEL)
                ],
            ),
        )
        print(f"  created {INDEX}")
    except Exception as e:
        if "already exists" in str(e).lower() or "RESOURCE_ALREADY_EXISTS" in str(e):
            print("  index exists — triggering sync")
            try:
                w.vector_search_indexes.sync_index(index_name=INDEX)
            except Exception as se:
                print(f"  (sync note: {se})")
        else:
            raise

    print("5/5 waiting for index to come online…")
    deadline = time.time() + 540  # ~9 min
    while time.time() < deadline:
        idx = w.vector_search_indexes.get_index(index_name=INDEX)
        status = idx.status
        ready = bool(getattr(status, "ready", False))
        detail = getattr(status, "detailed_state", getattr(status, "index_url", ""))
        print(f"  ready={ready} state={detail}")
        if ready:
            print("✅ index ONLINE")
            return
        time.sleep(20)
    print("⚠️ index not ready within timeout — re-run verify later or sync again")


if __name__ == "__main__":
    main()
