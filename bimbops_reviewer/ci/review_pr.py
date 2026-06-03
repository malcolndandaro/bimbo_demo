"""CI entrypoint: query the BimbOps Reviewer endpoint for a PR and post a comment.

Slice 04: sends the PR diff to the `bimbops-reviewer` Model Serving endpoint,
which returns structured findings (Finding contract) grounded in the BimbOps
Handbook; renders them as one Spanish summary comment. Advisory only — never
hard-fails the PR (an endpoint error posts a neutral note and exits 0; story 9).
Severity gating / Check Run lands in slice 05.

Auth: OAuth M2M (DATABRICKS_CLIENT_ID/SECRET) — OIDC federation is the documented
target but is blocked in the shared FE workspace (no account-admin). See ADR-0001.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

import requests
from databricks.sdk import WorkspaceClient

ENDPOINT = os.environ.get("ENDPOINT_NAME", "bimbops-reviewer")
GH_TOKEN = os.environ.get(
    "GH_TOKEN", ""
)  # read tolerantly — a missing var must not crash at import
REPO = os.environ.get("GH_REPO", "")
PR = os.environ.get("PR_NUMBER", "")
DIFF_FILE = os.environ.get("DIFF_FILE", "/tmp/pr.diff")  # noqa: S108 — ephemeral CI runner path, set by the workflow

_SEV_EMOJI = {"BLOCKER": "🔴", "SUGGESTION": "🟡", "STYLE": "⚪"}
_SEV_ORDER = {"BLOCKER": 0, "SUGGESTION": 1, "STYLE": 2}


def post_comment(body: str) -> None:
    r = requests.post(
        f"https://api.github.com/repos/{REPO}/issues/{PR}/comments",
        headers={
            "Authorization": f"Bearer {GH_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        json={"body": body},
        timeout=30,
    )
    r.raise_for_status()


def extract_text(resp: dict) -> str:
    """Pull text out of a Responses-format payload: output[].content[].text."""
    parts: list[str] = []
    for item in resp.get("output") or []:
        for c in item.get("content") or []:
            if isinstance(c, dict) and c.get("text"):
                parts.append(c["text"])
            elif isinstance(c, str):
                parts.append(c)
    return "\n".join(parts).strip()


def render_comment(payload: dict) -> str:
    # Defensive: CI parses the model text independently of the agent's validator,
    # so drop any malformed finding before rendering (no literal "None" rows).
    findings = [
        f
        for f in (payload.get("findings") or [])
        if isinstance(f, dict) and f.get("severity") in _SEV_ORDER and f.get("file")
    ]
    summary = (payload.get("summary") or "").strip()
    if not findings:
        tail = f" {summary}" if summary else ""
        return "## 🤖 BimbOps Reviewer\n\n✅ Sin hallazgos contra el BimbOps Handbook." + tail
    lines = ["## 🤖 BimbOps Reviewer", ""]
    if summary:
        lines += [summary, ""]
    for f in sorted(findings, key=lambda x: _SEV_ORDER.get(x.get("severity", ""), 3)):
        emoji = _SEV_EMOJI.get(f.get("severity", ""), "•")
        loc = f.get("file", "?") + (f":{f['line']}" if f.get("line") else "")
        lines.append(f"### {emoji} {f.get('severity')} — `{loc}` · {f.get('rule_id')}")
        lines.append(str(f.get("message", "")))
        if f.get("suggestion"):
            lines.append(f"> **Sugerencia:** {f['suggestion']}")
        lines.append(f"<sub>📖 {f.get('citation', '')}</sub>")
        lines.append("")
    n_block = sum(1 for f in findings if f.get("severity") == "BLOCKER")
    lines.append(
        f"---\n_{len(findings)} hallazgo(s), {n_block} BLOCKER. "
        "Revisión asesora — no bloquea el merge (el gate de severidad llega en la slice 05)._"
    )
    return "\n".join(lines)


def main() -> None:
    try:
        if not (GH_TOKEN and REPO and PR):
            print("missing GH_TOKEN/GH_REPO/PR_NUMBER — skipping review (non-blocking)")
            return
        diff = ""
        p = pathlib.Path(DIFF_FILE)
        if p.exists():
            diff = p.read_text(errors="ignore")[:14000]
        try:
            w = WorkspaceClient()
            resp = w.api_client.do(
                "POST",
                f"/serving-endpoints/{ENDPOINT}/invocations",
                body={"input": [{"role": "user", "content": diff or "(diff vacío)"}]},
            )
            text = extract_text(resp) if isinstance(resp, dict) else ""
            try:
                payload = json.loads(text)
                if not isinstance(payload, dict):
                    payload = {"findings": payload if isinstance(payload, list) else []}
            except (ValueError, TypeError):
                payload = {"summary": text[:500], "findings": []}
            post_comment(render_comment(payload))
        except Exception as e:  # noqa: BLE001 — any failure must stay non-blocking
            try:
                post_comment(
                    "⚠️ **BimbOps Reviewer** no está disponible ahora mismo; la revisión "
                    "automática no bloquea este PR.\n\n"
                    f"```\n{type(e).__name__}: {str(e)[:300]}\n```"
                )
            except Exception:  # noqa: BLE001 — even the fallback comment must never fail the check
                print(f"review degraded and comment post failed: {type(e).__name__}: {e}")
    finally:
        # Always exit 0 — the AI review is advisory and must never block delivery.
        sys.exit(0)


if __name__ == "__main__":
    main()
