"""Custom MLflow GenAI scorers for the BimbOps Reviewer (slice 09).

Thin @scorer wrappers over the PURE decision functions in review_core (unit-tested).
Each receives the agent `outputs` (the {summary, findings} payload from predict_fn)
and the dataset `expectations`, and returns a pass/fail Feedback.
"""

from __future__ import annotations

import pathlib
import sys

from mlflow.entities import Feedback
from mlflow.genai.scorers import scorer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "agent"))
import review_core  # noqa: E402 — sibling agent module; needs the sys.path insert above


def _findings(outputs) -> list[dict]:
    if isinstance(outputs, dict) and "findings" in outputs:
        return outputs.get("findings") or []
    return review_core.parse_review(outputs)["findings"]


@scorer
def caught_cross_env_ref(outputs, expectations) -> Feedback:
    exp = bool((expectations or {}).get("has_cross_env", False))
    ok = review_core.score_cross_env(_findings(outputs), exp)
    return Feedback(value=ok, rationale=f"ENV-01 presence vs expected={exp}")


@scorer
def flagged_transform_violation(outputs, expectations) -> Feedback:
    exp = bool((expectations or {}).get("has_transform_issue", False))
    ok = review_core.score_transform(_findings(outputs), exp)
    return Feedback(value=ok, rationale=f"TP-* presence vs expected={exp}")


@scorer
def zero_false_positives_on_clean_code(outputs, expectations) -> Feedback:
    is_clean = bool((expectations or {}).get("is_clean", False))
    ok = review_core.score_no_false_positives(_findings(outputs), is_clean)
    return Feedback(value=ok, rationale=f"is_clean={is_clean}; findings={len(_findings(outputs))}")
