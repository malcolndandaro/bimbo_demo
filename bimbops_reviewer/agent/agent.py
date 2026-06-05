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


def _retrieve_rules(query_text: str) -> list[dict]:
    """Query the handbook Vector Search index for diff-relevant rules."""
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
