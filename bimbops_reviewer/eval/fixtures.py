"""Build the BimbOps Reviewer eval dataset (slice 09).

Each fixture file is presented to the agent as an added-file diff, with the
expected findings encoded as `expectations`. Mix of a known-bad case (cross-env +
transform) and a clean case (no findings).
"""

from __future__ import annotations

import pathlib

_HERE = pathlib.Path(__file__).resolve().parent
_FIXTURES = _HERE / "fixtures"


def _as_added_diff(path: str, content: str) -> str:
    lines = content.splitlines()
    body = "".join(f"+{ln}\n" for ln in lines)
    return f"diff --git a/{path} b/{path}\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n{body}"


def build_eval_dataset() -> list[dict]:
    cases = [
        (
            "src/jobs/pricing_dev.py",
            (_FIXTURES / "cross_env_violation.py").read_text(encoding="utf-8"),
            {"has_cross_env": True, "has_transform_issue": True, "is_clean": False},
        ),
        (
            "src/bakery/clean_pipeline.py",
            (_FIXTURES / "clean_code.py").read_text(encoding="utf-8"),
            {"has_cross_env": False, "has_transform_issue": False, "is_clean": True},
        ),
    ]
    return [
        {"inputs": {"diff": _as_added_diff(path, content)}, "expectations": exp}
        for path, content, exp in cases
    ]
