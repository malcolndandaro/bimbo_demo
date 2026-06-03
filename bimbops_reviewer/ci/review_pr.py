"""CI entrypoint: query the BimbOps Reviewer endpoint for a PR and post a comment.

Slice 03 (tracer): sends the PR diff to the `bimbops-reviewer` Model Serving
endpoint and posts the agent's response as one summary comment. Never hard-fails
the PR — an endpoint error posts a neutral note and exits 0 (user story 9).

Auth: OAuth M2M (DATABRICKS_CLIENT_ID/SECRET) — OIDC federation is the documented
target but is blocked in the shared FE workspace (no account-admin). See ADR-0001.
"""

from __future__ import annotations

import os
import pathlib
import sys

import requests
from databricks.sdk import WorkspaceClient

ENDPOINT = os.environ.get("ENDPOINT_NAME", "bimbops-reviewer")
GH_TOKEN = os.environ["GH_TOKEN"]
REPO = os.environ["GH_REPO"]
PR = os.environ["PR_NUMBER"]
DIFF_FILE = os.environ.get("DIFF_FILE", "/tmp/pr.diff")  # noqa: S108 — ephemeral CI runner path, set by the workflow


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


def main() -> None:
    diff = ""
    p = pathlib.Path(DIFF_FILE)
    if p.exists():
        diff = p.read_text(errors="ignore")[:12000]
    prompt = (
        "Revisa este diff de PR contra los estándares de BimbOps y resume tus "
        f"hallazgos:\n\n{diff or '(diff vacío)'}"
    )
    try:
        w = WorkspaceClient()
        resp = w.api_client.do(
            "POST",
            f"/serving-endpoints/{ENDPOINT}/invocations",
            body={"input": [{"role": "user", "content": prompt}]},
        )
        text = extract_text(resp) if isinstance(resp, dict) else ""
        post_comment(text or "🤖 BimbOps Reviewer respondió sin contenido.")
    except Exception as e:  # noqa: BLE001 — any failure must stay non-blocking
        post_comment(
            "⚠️ **BimbOps Reviewer** no está disponible ahora mismo; la revisión "
            "automática no bloquea este PR.\n\n"
            f"```\n{type(e).__name__}: {str(e)[:300]}\n```"
        )
    # Always exit 0 — the AI review is advisory and must never block delivery.
    sys.exit(0)


if __name__ == "__main__":
    main()
