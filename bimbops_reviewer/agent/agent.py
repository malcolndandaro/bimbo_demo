"""BimbOps Reviewer — slice 04: real, retrieval-grounded, cited findings.

Imperative shell around the pure cores in review_core.py:
  diff → build_review_context → retrieve handbook rules (Vector Search) →
  build_review_prompt → call the foundation model → parse_findings → return.

Output is the Finding contract as JSON (the CI shell, review_pr.py, renders it).
Retrieval cites the exact handbook rule_id/citation, closing the "same knowledge
base powers Q&A and review" loop.
"""

from __future__ import annotations

import json
import os
import re

import mlflow
import review_core
from databricks.sdk import WorkspaceClient
from mlflow.deployments import get_deploy_client
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse

LLM_ENDPOINT = "databricks-claude-opus-4-8"
VS_INDEX = "bimbo.dev.bimbops_handbook_rules_idx"
VS_COLUMNS = ["rule_id", "title", "content", "citation", "severity_hint"]
N_RULES = 8
# When set, the reviewer CONSULTS the BimbOps Knowledge Assistant (agent-to-agent) for the
# relevant handbook rules instead of querying Vector Search directly — "one handbook brain,
# two faces" (humans chat with the KA; the gate consults it). Empty = query VS directly.
# Falls back to VS automatically if the KA call fails or returns nothing (gate never degrades).
KA_ENDPOINT = os.environ.get("KA_ENDPOINT", "")


def _input_text(req: ResponsesAgentRequest) -> str:
    parts: list[str] = []
    for item in req.input:
        d = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        c = d.get("content")
        if isinstance(c, str):
            parts.append(c)
        elif isinstance(c, list):
            for seg in c:
                if isinstance(seg, dict) and seg.get("text"):
                    parts.append(seg["text"])
    return "\n".join(parts)


def _retrieve_via_vs(query_text: str) -> list[dict]:
    """Query the handbook Vector Search index directly for diff-relevant rules."""
    w = WorkspaceClient()
    res = w.vector_search_indexes.query_index(
        index_name=VS_INDEX,
        columns=VS_COLUMNS,
        query_text=query_text[:2000] or "coding standards",
        num_results=N_RULES,
    )
    rows = (res.result.data_array if res.result else None) or []
    # trailing score column is intentionally dropped (5 cols vs 6-element row)
    return [dict(zip(VS_COLUMNS, row, strict=False)) for row in rows]


_KA_PROMPT = (
    "Eres el BimbOps Handbook. Para el CÓDIGO de un PR de abajo, devuelve SOLO un JSON array "
    "(sin texto fuera del JSON) de las reglas del handbook RELEVANTES (máximo 8). Cada elemento "
    'EXACTAMENTE: {"rule_id":"", "title":"", "content":"<texto de la regla>", "citation":"", '
    '"severity_hint":"BLOCKER|SUGGESTION|STYLE"}. Usa SOLO reglas reales del handbook (rule_id '
    "como ENV-01, TP-02, SQL-01, etc.) con su contenido y cita textuales.\n\nCÓDIGO:\n"
)


def _ka_text(resp: dict) -> str:
    """Extract the assistant text from a KA serving response (chat or responses shape)."""
    try:
        return resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        pass
    parts = [
        c.get("text", "")
        for it in (resp.get("output") or [])
        for c in (it.get("content") or [])
        if isinstance(c, dict)
    ]
    return "".join(parts) or str(resp)


def _retrieve_via_ka(query_text: str) -> list[dict]:
    """Ask the BimbOps Knowledge Assistant which handbook rules apply (agent-to-agent).
    Returns validated rule dicts (real rule_ids only); [] if the KA gives nothing usable."""
    resp = get_deploy_client("databricks").predict(
        endpoint=KA_ENDPOINT,
        inputs={
            "messages": [{"role": "user", "content": _KA_PROMPT + query_text[:2000]}],
            "max_tokens": 1500,
        },
    )
    parsed = review_core.loads_tolerant(_ka_text(resp))
    items = parsed if isinstance(parsed, list) else (parsed or {}).get("rules", [])
    rules: list[dict] = []
    for r in items:
        # Validate: keep only well-formed, real-looking rule_ids — a hallucinated id is dropped
        # here, and downstream parse_findings only cites rule_ids from the rules we pass on.
        if isinstance(r, dict) and re.fullmatch(r"[A-Z]{2,4}-\d{1,3}", str(r.get("rule_id", ""))):
            rules.append({k: r.get(k, "") for k in VS_COLUMNS})
    return rules[:N_RULES]


def _retrieve_rules(query_text: str) -> list[dict]:
    """Consult the Knowledge Assistant when configured (KA_ENDPOINT), else query VS directly.
    Falls back to VS if the KA is unavailable or returns nothing — the gate never degrades."""
    if KA_ENDPOINT:
        try:
            rules = _retrieve_via_ka(query_text)
            if rules:
                return rules
            print("KA returned no usable rules — falling back to Vector Search")
        except Exception as e:  # noqa: BLE001 — never let the KA take down the gate
            print(f"KA retrieval degraded ({type(e).__name__}: {e}); falling back to Vector Search")
    return _retrieve_via_vs(query_text)


def _call_llm(system: str, user: str) -> str:
    client = get_deploy_client("databricks")
    resp = client.predict(
        endpoint=LLM_ENDPOINT,
        inputs={
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": 1800,
            # NOTE: opus-4-8 rejects the `temperature` parameter (400 BAD_REQUEST) — it
            # manages sampling internally. Do not re-add it for this model.
        },
    )
    return resp["choices"][0]["message"]["content"]


class BimbopsReviewer(ResponsesAgent):
    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        diff = _input_text(request)
        context = review_core.build_review_context(diff)
        # Query text = the added code itself, so the embedding matches rules whose
        # content mentions bimbo_prd / .collect() / sys.argv / SQL style, etc.
        query_text = "\n".join(code for f in context["files"] for _, code in f.get("added", []))
        rules = _retrieve_rules(query_text)
        system, user = review_core.build_review_prompt(context, rules)
        raw = _call_llm(system, user)
        payload = review_core.parse_review(raw)  # tolerant: recovers summary + findings together
        return ResponsesAgentResponse(
            output=[
                self.create_text_output_item(
                    text=json.dumps(payload, ensure_ascii=False), id="bimbops_review_1"
                )
            ]
        )


mlflow.models.set_model(BimbopsReviewer())
