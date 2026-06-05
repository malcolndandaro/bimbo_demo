"""Cost/usage + recent-traces view from the BimbOps Reviewer inference table (slice 10).

Source: `bimbo.dev.bimbops_reviewer_payload` (AI Gateway inference logging on the
agent endpoint). Prints a Markdown summary: per-day reviews + latency + a token
ESTIMATE, plus a recent-traces panel.

Honesty: the token figure is a LOWER BOUND — chars/4 over the agent's *outer* request/
response only; it excludes the inner FM tool-calling loop and reasoning tokens. The USD
figure uses an ILLUSTRATIVE rate (not real billing). Precise token cost would come from
AI Gateway usage tracking on a dedicated gateway endpoint fronting the FM (see README).

Run:  DATABRICKS_AUTH_STORAGE=plaintext python bimbops_reviewer/gateway/cost_report.py
"""

from __future__ import annotations

import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

TABLE = "bimbo.dev.bimbops_reviewer_payload"
USD_PER_1K_TOKENS = 0.009  # ILLUSTRATIVE blended rate — not real billing

SUMMARY_SQL = f"""
SELECT
  CAST(request_time AS DATE)                                           AS day,
  count(*)                                                             AS pr_reviews,
  round(avg(execution_duration_ms) / 1000.0, 1)                        AS avg_secs,
  CAST(round(sum(length(request) + length(response)) / 4.0) AS BIGINT) AS est_tokens
FROM {TABLE}
WHERE request_time >= current_timestamp() - INTERVAL 30 DAYS
GROUP BY 1
ORDER BY 1 DESC
"""  # noqa: S608 — TABLE is a trusted module constant, not external input

RECENT_SQL = f"""
SELECT request_time, requester, status_code,
       round(execution_duration_ms / 1000.0, 1) AS secs
FROM {TABLE}
ORDER BY request_time DESC
LIMIT 8
"""  # noqa: S608 — TABLE is a trusted module constant, not external input


def _running_warehouse(w: WorkspaceClient) -> str:
    for wh in w.warehouses.list():
        if str(wh.state) == "State.RUNNING" or getattr(wh.state, "value", "") == "RUNNING":
            return wh.id
    raise SystemExit("No RUNNING SQL warehouse found.")


def _run(w: WorkspaceClient, wid: str, sql: str) -> list:
    r = w.statement_execution.execute_statement(warehouse_id=wid, statement=sql, wait_timeout="50s")
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(2)
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state != StatementState.SUCCEEDED:
        raise SystemExit(f"query failed: {getattr(r.status, 'error', None)}")
    return (r.result.data_array if r.result else None) or []


def main() -> None:
    w = WorkspaceClient()
    wid = _running_warehouse(w)

    print("## BimbOps Reviewer — uso / costo (últimos 30 días)\n")
    print("| Día | PR reviews | Seg/PR (avg) | Tokens est. (cota inf.) | USD ilustrativo |")
    print("|---|---|---|---|---|")
    total_reviews, total_usd = 0, 0.0
    for day, n, avg_secs, est_tokens in _run(w, wid, SUMMARY_SQL):
        usd = round(float(est_tokens) / 1000.0 * USD_PER_1K_TOKENS, 4)
        total_reviews += int(n)
        total_usd += usd
        print(f"| {day} | {n} | {avg_secs} | {est_tokens} | ${usd} |")
    per_pr = round(total_usd / total_reviews, 4) if total_reviews else 0.0
    print(f"\n**Total:** {total_reviews} PR reviews · ~${round(total_usd, 4)} · **~${per_pr}/PR**")

    print("\n### Trazas recientes")
    print("| Hora | Requester | status | seg |")
    print("|---|---|---|---|")
    for ts, requester, status, secs in _run(w, wid, RECENT_SQL):
        print(f"| {ts} | {requester} | {status} | {secs} |")

    print(
        f"\n_Fuente: tabla de inferencia `{TABLE}` (AI Gateway inference logging). "
        "Tokens = cota inferior (chars/4 del I/O externo del agente; excluye el loop de "
        f"tool-calling y razonamiento del FM). USD = tarifa ILUSTRATIVA (${USD_PER_1K_TOKENS}/1k), "
        "no facturación real. Costo exacto: usage tracking en un gateway sobre el FM. "
        "Trazas detalladas en MLflow._"
    )


if __name__ == "__main__":
    main()
