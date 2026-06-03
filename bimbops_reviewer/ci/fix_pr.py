"""CI fix-mode: /bimbops-fix → generate + validate fixes → push to the PR branch.

Triggered by an `issue_comment` containing `/bimbops-fix` (production) or by
`workflow_dispatch` (testing). Flow:
  1. authorize the actor (ADR-0003: write/maintain/admin, never a protected branch);
  2. re-review the PR to get findings, grouped by file;
  3. ask the FM for the COMPLETE corrected file per finding-bearing file;
  4. validate each parses (compile/yaml) — abort the whole push if any is invalid;
  5. the BimbOps Bot (BIMBOPS_BOT_TOKEN, a fine-grained PAT) pushes ONE commit to the
     PR head branch — which re-triggers bimbops-review + pr-checks.
Never hard-fails the job (exits 0); posts a comment with the outcome.

GitHub App is the production identity (ADR-0003); slice 01 chose a fine-grained PAT
as the demo shortcut.
"""

from __future__ import annotations

import contextlib
import os
import pathlib
import subprocess  # noqa: S404 — git CLI is required for the commit/push
import sys

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "agent"))
import review_core  # noqa: E402 — sibling agent module; needs the sys.path insert above

REPO = os.environ.get("GH_REPO", "")
PR = os.environ.get("PR_NUMBER", "")
ACTOR = os.environ.get("ACTOR", "")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ENDPOINT = os.environ.get("ENDPOINT_NAME", "bimbops-reviewer")
LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "databricks-claude-sonnet-4-5")
_GH = {"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"}


def gh_get(path: str) -> dict:
    r = requests.get(f"https://api.github.com{path}", headers=_GH, timeout=30)
    r.raise_for_status()
    return r.json()


def comment(body: str) -> None:
    requests.post(
        f"https://api.github.com/repos/{REPO}/issues/{PR}/comments",
        headers=_GH,
        json={"body": body},
        timeout=30,
    )


def get_findings(diff: str) -> list[dict]:
    from databricks.sdk import WorkspaceClient  # lazy: import errors stay inside main's guard

    w = WorkspaceClient()
    resp = w.api_client.do(
        "POST",
        f"/serving-endpoints/{ENDPOINT}/invocations",
        body={"input": [{"role": "user", "content": diff or "(diff vacío)"}]},
    )
    text = "".join(
        c.get("text", "")
        for it in (resp.get("output") or [])
        for c in (it.get("content") or [])
        if isinstance(c, dict)
    )
    return review_core.parse_review(text)["findings"]


def fm_fix(path: str, original: str, findings: list[dict]) -> str | None:
    from mlflow.deployments import get_deploy_client  # lazy

    system, user = review_core.build_fix_prompt(path, original, findings)
    resp = get_deploy_client("databricks").predict(
        endpoint=LLM_ENDPOINT,
        inputs={
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": 4000,
            "temperature": 0.0,
        },
    )
    return review_core.extract_code(resp["choices"][0]["message"]["content"])


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)  # noqa: S603,S607


def main() -> None:
    if not (REPO and PR and GH_TOKEN and BOT_TOKEN):
        print("missing GH_REPO/PR_NUMBER/GH_TOKEN/BOT_TOKEN — skipping (non-blocking)")
        return

    pr = gh_get(f"/repos/{REPO}/pulls/{PR}")
    head_ref = pr["head"]["ref"]
    head_repo = (pr.get("head", {}).get("repo") or {}).get("full_name")
    base_repo = (pr.get("base", {}).get("repo") or {}).get("full_name")
    if head_repo != base_repo:
        comment("🤖 **BimbOps Bot**: el autofix no opera sobre PRs desde forks (seguridad).")
        return

    try:
        perm = gh_get(f"/repos/{REPO}/collaborators/{ACTOR}/permission").get("permission", "none")
    except requests.HTTPError:
        perm = "none"
    try:
        protected = bool(gh_get(f"/repos/{REPO}/branches/{head_ref}").get("protected", False))
    except requests.HTTPError:
        protected = False
    ok, reason = review_core.is_authorized(perm, protected)
    if not ok:
        comment(f"🤖 **BimbOps Bot** no puede aplicar el arreglo: {reason}")
        return

    diff = _git("--no-pager", "diff", f"origin/{pr['base']['ref']}...HEAD").stdout
    changed_files = {f["path"] for f in review_core.build_review_context(diff)["files"]}
    findings = get_findings(diff)
    by_file = review_core.select_fixable(findings, changed_files)  # confine to PR's changed files
    if not by_file:
        comment("🤖 **BimbOps Bot**: no hay hallazgos aplicables en archivos de este PR.")
        return

    changed: dict[str, str] = {}
    for path, fs in by_file.items():
        p = pathlib.Path(path)
        if not p.exists():
            continue
        original = p.read_text(encoding="utf-8")
        new = fm_fix(path, original, fs)
        valid, err = review_core.validate_content(path, new)
        if not valid:
            comment(
                f"🤖 **BimbOps Bot**: el arreglo propuesto para `{path}` no es válido "
                f"({err}); no se hizo push."
            )
            return
        if new != original:
            changed[path] = new

    if not changed:
        comment("🤖 **BimbOps Bot**: no se generaron cambios aplicables.")
        return

    for path, new in changed.items():
        pathlib.Path(path).write_text(new, encoding="utf-8")
    _git("config", "user.name", "BimbOps Bot")
    _git("config", "user.email", "bimbops-bot@users.noreply.github.com")
    _git("add", *changed)
    files = ", ".join(sorted(changed))
    _git("commit", "-m", f"fix(bimbops): aplica arreglos del BimbOps Reviewer ({files})")
    push = _git(
        "push", f"https://x-access-token:{BOT_TOKEN}@github.com/{REPO}.git", f"HEAD:{head_ref}"
    )
    if push.returncode != 0:
        print(f"push failed: {push.stderr}")  # details to the secret-masked Actions log only
        comment("🤖 **BimbOps Bot**: el push falló (ver logs del workflow).")
        return
    comment(
        f"🤖 **BimbOps Bot** aplicó arreglos en: `{files}`. "
        "La revisión y el CI se re-ejecutarán automáticamente sobre el nuevo commit."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 — fix mode must never fail the job
        print(f"fix degraded: {type(e).__name__}: {e}")
        with contextlib.suppress(Exception):
            comment(
                "🤖 **BimbOps Bot**: no se pudo completar el autofix (ver logs); "
                "el PR no se bloquea."
            )
    sys.exit(0)
