"""Run mlflow.genai.evaluate() on the BimbOps Reviewer (slice 09).

Calls the deployed `bimbops-reviewer` endpoint for each fixture diff, scores with the
custom scorers, logs an MLflow run, and acts as a REGRESSION GATE: exits non-zero if
any custom scorer drops below 100% on the curated fixtures (i.e., the agent missed an
expected finding or hallucinated on clean code).

Run:  DATABRICKS_AUTH_STORAGE=plaintext python bimbops_reviewer/eval/run_eval.py
"""

from __future__ import annotations

import pathlib
import sys

import mlflow

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))  # scorers, fixtures
sys.path.insert(0, str(_HERE.parent / "agent"))  # review_core

import review_core  # noqa: E402
from fixtures import build_eval_dataset  # noqa: E402
from scorers import (  # noqa: E402
    caught_cross_env_ref,
    flagged_transform_violation,
    zero_false_positives_on_clean_code,
)

ENDPOINT = "bimbops-reviewer"
EXPERIMENT = "/Users/malcoln.dandaro@databricks.com/bimbops_reviewer/eval"
SCORERS = [caught_cross_env_ref, flagged_transform_violation, zero_false_positives_on_clean_code]


def predict_fn(diff: str) -> dict:
    """Invoke the deployed reviewer endpoint and return the parsed findings."""
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    resp = w.api_client.do(
        "POST",
        f"/serving-endpoints/{ENDPOINT}/invocations",
        body={"input": [{"role": "user", "content": diff}]},
    )
    text = "".join(
        c.get("text", "")
        for it in (resp.get("output") or [])
        for c in (it.get("content") or [])
        if isinstance(c, dict)
    )
    return review_core.parse_review(text)


def main() -> None:
    mlflow.set_tracking_uri("databricks")
    mlflow.set_experiment(EXPERIMENT)
    results = mlflow.genai.evaluate(
        data=build_eval_dataset(),
        predict_fn=predict_fn,
        scorers=SCORERS,
    )
    metrics = dict(results.metrics or {})
    print("=== eval metrics ===")
    for k, v in sorted(metrics.items()):
        print(f"  {k}: {v}")

    # Regression gate: every custom scorer must pass 100% on the curated fixtures.
    failed = []
    for s in (
        "caught_cross_env_ref",
        "flagged_transform_violation",
        "zero_false_positives_on_clean_code",
    ):
        vals = [v for k, v in metrics.items() if k.startswith(s) and isinstance(v, (int, float))]
        if not vals or min(vals) < 1.0:
            failed.append(s)
    if failed:
        print(f"\n❌ REGRESSION — scorers below 100%: {', '.join(failed)}")
        sys.exit(1)
    print("\n✅ all scorers at 100% — no regression")


if __name__ == "__main__":
    main()
