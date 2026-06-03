"""Pure, deterministic cores for the BimbOps Reviewer (slice 04).

No I/O, no SDK calls, no network — everything here is unit-testable with plain
data. The agent (agent.py) and the CI shell (review_pr.py) import these; the
Vector Search query and the foundation-model call live in the agent shell.

Three cores:
  - build_review_context(diff)   parse a unified diff → structured context
  - build_review_prompt(ctx, rules)  assemble the system/user prompt
  - parse_findings(raw)          validate model output → list[Finding]
"""

from __future__ import annotations

import json
import re

# --- Finding contract (mirrors CONTEXT.md / PRD) ---------------------------------
SEVERITIES = ("BLOCKER", "SUGGESTION", "STYLE")
REQUIRED_FIELDS = ("file", "severity", "rule_id", "citation", "message")

_LANG_BY_EXT = {
    ".py": "python",
    ".sql": "sql",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".sh": "shell",
}


def detect_language(path: str) -> str:
    for ext, lang in _LANG_BY_EXT.items():
        if path.endswith(ext):
            return lang
    return "text"


# --- Core 1: diff → review context -----------------------------------------------
_DIFF_HEADER = re.compile(r"^diff --git a/(?P<a>.+?) b/(?P<b>.+)$")
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,\d+)? @@")


def build_review_context(diff: str) -> dict:
    """Parse a `git diff` into per-file added lines with their new line numbers.

    Returns {"files": [{path, language, is_binary, is_rename, added:[(lineno, text)],
    hunks: str}], "n_files": int}. Robust to empty diffs, binary files, and renames.
    """
    files: list[dict] = []
    cur: dict | None = None
    new_lineno = 0
    for line in (diff or "").splitlines():
        m = _DIFF_HEADER.match(line)
        if m:
            cur = {
                "path": m.group("b"),
                "language": detect_language(m.group("b")),
                "is_binary": False,
                "is_rename": False,
                "added": [],
                "hunks": [],
            }
            files.append(cur)
            new_lineno = 0
            continue
        if cur is None:
            continue
        if line.startswith("Binary files"):
            cur["is_binary"] = True
        elif line.startswith("rename from") or line.startswith("rename to"):
            cur["is_rename"] = True
        elif line.startswith("+++ b/"):
            cur["path"] = line[6:]
            cur["language"] = detect_language(cur["path"])
        else:
            hm = _HUNK.match(line)
            if hm:
                new_lineno = int(hm.group("start"))
                cur["hunks"].append(line)
            elif line.startswith("+") and not line.startswith("+++"):
                cur["added"].append((new_lineno, line[1:]))
                new_lineno += 1
            elif line.startswith("-") and not line.startswith("---"):
                pass  # removed line — does not advance the new-file counter
            elif not line.startswith("\\"):  # context line
                if new_lineno:
                    new_lineno += 1
    for f in files:
        f["hunks"] = "\n".join(f["hunks"])
    return {"files": files, "n_files": len(files)}


# --- Core 2: prompt assembly -----------------------------------------------------
_SYSTEM = (
    "Eres el BimbOps Reviewer, un revisor de código automático para Grupo Bimbo. "
    "Revisas un diff de PR ÚNICAMENTE contra las reglas del BimbOps Handbook que se "
    "te proporcionan. No inventes reglas. Cada hallazgo DEBE citar un rule_id de la "
    "lista provista. Responde en español. Si no hay violaciones, devuelve findings vacío.\n\n"
    "Severidad: usa la severity_hint de la regla, pero ESCALA a BLOCKER cualquier "
    "referencia a un catálogo de otro ambiente (p.ej. *_prd / prod desde dev) o un "
    "secreto/credencial en código. STYLE para nits de formato.\n\n"
    "Devuelve SOLO JSON válido, sin texto extra, con esta forma exacta:\n"
    '{"summary": "<resumen 1 línea en español>", "findings": [{'
    '"file": "<ruta>", "line": <entero o null>, "severity": "BLOCKER|SUGGESTION|STYLE", '
    '"rule_id": "<id de la lista>", "citation": "<citation de la regla>", '
    '"message": "<qué está mal, en español>", "suggestion": "<cómo arreglarlo, español o null>"}]}'
)


def build_review_prompt(context: dict, rules: list[dict]) -> tuple[str, str]:
    """Return (system, user) messages. `rules` are retrieved handbook rows."""
    rules_block = (
        "\n".join(
            f"- {r.get('rule_id')} [{r.get('severity_hint', 'SUGGESTION')}] "
            f"(citation: {r.get('citation')}): {r.get('content', r.get('title', '')).strip()[:400]}"
            for r in rules
        )
        or "(sin reglas recuperadas)"
    )

    files_block = []
    for f in context.get("files", []):
        if f.get("is_binary"):
            files_block.append(f"### {f['path']} (binario — omitir)")
            continue
        added = "\n".join(f"  L{ln}: {code}" for ln, code in f.get("added", [])[:200])
        files_block.append(f"### {f['path']} ({f['language']})\n{added}")
    files_text = "\n\n".join(files_block) or "(diff vacío)"

    user = (
        "REGLAS DEL HANDBOOK (cita SOLO estos rule_id):\n"
        f"{rules_block}\n\n"
        "LÍNEAS AÑADIDAS EN EL PR (usa el número Lxx como `line`):\n"
        f"{files_text}\n\n"
        "Devuelve el JSON de hallazgos."
    )
    return _SYSTEM, user


# --- Core 3: parse + validate model output → findings ----------------------------
def _coerce_finding(obj: object) -> dict | None:
    if not isinstance(obj, dict):
        return None
    if not all(obj.get(k) not in (None, "") for k in REQUIRED_FIELDS):
        return None
    sev = str(obj["severity"]).upper()
    if sev not in SEVERITIES:
        return None
    line = obj.get("line")
    if isinstance(line, str) and line.isdigit():
        line = int(line)
    if not isinstance(line, int):
        line = None
    return {
        "file": str(obj["file"]),
        "line": line,
        "severity": sev,
        "rule_id": str(obj["rule_id"]),
        "citation": str(obj["citation"]),
        "message": str(obj["message"]),
        "suggestion": (str(obj["suggestion"]) if obj.get("suggestion") else None),
        "patch": (str(obj["patch"]) if obj.get("patch") else None),
    }


def parse_findings(raw: object) -> list[dict]:
    """Validate model output → list of Finding dicts. Never raises.

    Accepts a JSON string, a dict (`{"findings": [...]}`), or a list. Malformed
    input or any parse error → [] (the agent stays non-crashing; user story 38).
    """
    data: object = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            # tolerate models that wrap JSON in prose/fences — grab the first {...}
            m = re.search(r"\{.*\}", raw, re.S)
            if not m:
                return []
            try:
                data = json.loads(m.group(0))
            except (ValueError, TypeError):
                return []
    if isinstance(data, dict):
        items = data.get("findings", [])
    elif isinstance(data, list):
        items = data
    else:
        return []
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        f = _coerce_finding(it)
        if f is not None:
            out.append(f)
    return out
