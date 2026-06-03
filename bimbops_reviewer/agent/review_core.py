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
            cur["path"] = line[6:].rstrip()  # git may pad the path with a tab
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


def _first_balanced_object(s: str) -> str | None:
    """Return the first brace-balanced {...} substring (string/escape aware).

    Used to recover JSON from models that wrap it in prose or code fences —
    without the greedy `\\{.*\\}` bug that spans trailing junk and breaks parsing.
    """
    start = s.find("{")
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


def loads_tolerant(raw: object) -> object | None:
    """Best-effort JSON decode. Returns the parsed value, or None on failure."""
    if isinstance(raw, (dict, list)):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        obj = _first_balanced_object(raw)
        if obj is None:
            return None
        try:
            return json.loads(obj)
        except (ValueError, TypeError):
            return None


def parse_findings(raw: object) -> list[dict]:
    """Validate model output → list of Finding dicts. Never raises.

    Accepts a JSON string, a dict (`{"findings": [...]}`), or a list. Malformed
    input or any parse error → [] (the agent stays non-crashing; user story 38).
    """
    data = loads_tolerant(raw)
    if isinstance(data, dict):
        items = data.get("findings", [])
    elif isinstance(data, list):
        items = data
    else:
        return []
    if not isinstance(items, list):
        return []
    return [f for it in items if (f := _coerce_finding(it)) is not None]


def parse_review(raw: object) -> dict:
    """Parse model output into {"summary": str, "findings": [Finding]} tolerantly.

    Single source of truth so the agent and CI never diverge on how output is read
    (the summary is recovered with the same fence-tolerant decode as findings).
    """
    data = loads_tolerant(raw)
    summary = data.get("summary", "") if isinstance(data, dict) else ""
    return {"summary": str(summary or ""), "findings": parse_findings(data)}


# --- Core 4: severity gate + GitHub Check Run mapper (slice 05) -------------------
# GitHub Checks API: max 50 annotations per request; levels are notice/warning/failure.
MAX_ANNOTATIONS = 50
_ANNOTATION_LEVEL = {"BLOCKER": "failure", "SUGGESTION": "warning", "STYLE": "notice"}


def decide_gate(findings: list[dict]) -> dict:
    """Severity gate (ADR-0002): any BLOCKER → failure; only SUGGESTION/STYLE →
    neutral; no findings → success. Returns the GateDecision contract.
    """
    valid = [f for f in (findings or []) if isinstance(f, dict) and f.get("severity") in SEVERITIES]
    n_block = sum(1 for f in valid if f["severity"] == "BLOCKER")
    n = len(valid)
    if n == 0:
        return {
            "conclusion": "success",
            "blocker_count": 0,
            "summary": "✅ Sin hallazgos contra el BimbOps Handbook.",
        }
    if n_block:
        return {
            "conclusion": "failure",
            "blocker_count": n_block,
            "summary": (
                f"🔴 {n_block} de {n} hallazgo(s) son BLOCKER — merge bloqueado hasta resolver."
            ),
        }
    return {
        "conclusion": "neutral",
        "blocker_count": 0,
        "summary": f"🟡 {n} hallazgo(s) asesor(es) — no bloquean el merge.",
    }


def to_check_run(findings: list[dict], decision: dict) -> dict:
    """Map findings → a GitHub Check Run payload (conclusion + output.annotations).

    Line/file-level annotations (file-level uses line 1), severity → annotation
    level, capped at 50 with a Spanish overflow note. Pure — the CI shell posts it.
    """
    annotations = []
    for f in findings or []:
        if not (isinstance(f, dict) and f.get("file") and f.get("severity") in _ANNOTATION_LEVEL):
            continue
        line = f.get("line") if isinstance(f.get("line"), int) and f["line"] >= 1 else 1
        msg = str(f.get("message", "")).strip()
        if f.get("suggestion"):
            msg += f"\n\nSugerencia: {f['suggestion']}"
        if f.get("citation"):
            msg += f"\n\n📖 {f['citation']}"
        annotations.append(
            {
                "path": str(f["file"]),
                "start_line": line,
                "end_line": line,
                "annotation_level": _ANNOTATION_LEVEL[f["severity"]],
                # GitHub limits: title ≤ 255 chars, message ≤ 64KB (else 422s the whole run)
                "title": f"{f['severity']} · {f.get('rule_id', '')}".strip(" ·")[:255],
                "message": (msg or f["severity"])[:65000],
            }
        )
    summary = decision.get("summary", "")
    if len(annotations) > MAX_ANNOTATIONS:
        extra = len(annotations) - MAX_ANNOTATIONS
        annotations = annotations[:MAX_ANNOTATIONS]
        summary += f"\n\n_(+{extra} hallazgo(s) adicionales no anotados; límite de 50 de GitHub.)_"
    titles = {
        "failure": "BimbOps Reviewer — BLOCKER",
        "neutral": "BimbOps Reviewer — sugerencias",
        "success": "BimbOps Reviewer — OK",
    }
    return {
        "conclusion": decision.get("conclusion", "neutral"),
        "output": {
            "title": titles.get(decision.get("conclusion"), "BimbOps Reviewer"),
            "summary": summary,
            "annotations": annotations,
        },
    }


# --- Core 5: fix mode (slice 06) -------------------------------------------------
# The fix shell asks the FM for the COMPLETE corrected file (robust vs fragile
# unified-diff application), then validates it parses before the bot pushes.
_WRITE_PERMS = ("write", "maintain", "admin")
_FIX_SYSTEM = (
    "Eres el BimbOps Reviewer en MODO ARREGLO. Recibes el contenido COMPLETO de un "
    "archivo y una lista de hallazgos del BimbOps Handbook. Devuelve el contenido "
    "COMPLETO y corregido del archivo, resolviendo los hallazgos y preservando el "
    "resto del código y su comportamiento. No expliques nada: devuelve SOLO el "
    "archivo corregido dentro de un único bloque ```...``` (sin texto fuera del bloque)."
)
_FENCE = re.compile(r"```[a-zA-Z0-9_+.-]*\n(?P<code>.*?)```", re.S)


def is_authorized(permission: str, branch_is_protected: bool) -> tuple[bool, str]:
    """ADR-0003 authz: only write/maintain/admin collaborators may trigger a fix,
    and never on a protected branch. `permission` is the GitHub collaborator role.
    """
    if branch_is_protected:
        return False, "La rama destino está protegida; el bot no escribe en ramas protegidas."
    if permission not in _WRITE_PERMS:
        return False, f"Permiso insuficiente ('{permission}'); se requiere write/maintain/admin."
    return True, ""


def build_fix_prompt(path: str, original: str, findings: list[dict]) -> tuple[str, str]:
    issues = (
        "\n".join(
            f"- L{f.get('line')}: [{f.get('severity')}] {f.get('rule_id')} — {f.get('message')}"
            + (f" (sugerencia: {f['suggestion']})" if f.get("suggestion") else "")
            for f in findings
        )
        or "(sin hallazgos)"
    )
    user = (
        f"ARCHIVO: {path}\n\nHALLAZGOS A CORREGIR:\n{issues}\n\n"
        f"CONTENIDO ACTUAL:\n```\n{original}\n```\n\n"
        "Devuelve el archivo COMPLETO corregido en un solo bloque de código."
    )
    return _FIX_SYSTEM, user


def extract_code(model_output: str) -> str | None:
    """Pull the corrected file content out of the model's fenced code block.

    Requires a ```fenced``` block — prose without a fence is treated as malformed
    (returns None) so the bot never pushes raw model chatter as file content.
    """
    if not isinstance(model_output, str):
        return None
    m = _FENCE.search(model_output)
    if not m:
        return None
    code = m.group("code").rstrip("\n")
    return (code + "\n") if code.strip() else None


def select_fixable(findings: list[dict], changed_files: set[str]) -> dict[str, list[dict]]:
    """Group findings by file, CONFINED to the PR's changed files.

    Security: finding `file` paths come from (untrusted) model output, so the bot
    must never rewrite a path the PR didn't touch. Also rejects absolute or
    parent-escaping paths.
    """
    by_file: dict[str, list[dict]] = {}
    for f in findings or []:
        path = f.get("file") if isinstance(f, dict) else None
        if not path or path.startswith("/") or ".." in path or path not in changed_files:
            continue
        by_file.setdefault(path, []).append(f)
    return by_file


def validate_content(path: str, content: str | None) -> tuple[bool, str]:
    """Deterministic post-fix validation: the corrected file must still parse."""
    if not content or not content.strip():
        return False, "contenido vacío"
    if path.endswith(".py"):
        try:
            compile(content, path, "exec")
        except SyntaxError as e:
            return False, f"SyntaxError: {e}"
    elif path.endswith((".yml", ".yaml")):
        try:
            import yaml

            yaml.safe_load(content)
        except ImportError:
            pass  # no yaml on the runner — skip (non-empty already checked)
        except Exception as e:  # noqa: BLE001 — any parse error = invalid YAML
            return False, f"YAML inválido: {e}"
    return True, ""


# --- Core 6: eval scorer decisions (slice 09) — pure, unit-testable --------------
def has_rule(findings: list[dict], rule_id: str) -> bool:
    return any(isinstance(f, dict) and f.get("rule_id") == rule_id for f in (findings or []))


def has_rule_prefix(findings: list[dict], prefix: str) -> bool:
    return any(
        isinstance(f, dict) and str(f.get("rule_id", "")).startswith(prefix)
        for f in (findings or [])
    )


def score_cross_env(findings: list[dict], expected: bool) -> bool:
    """Caught-cross-env: ENV-01 presence must match the expectation."""
    return has_rule(findings, "ENV-01") == bool(expected)


def score_transform(findings: list[dict], expected: bool) -> bool:
    """Flagged-transform: a TP-* finding's presence must match the expectation."""
    return has_rule_prefix(findings, "TP-") == bool(expected)


def score_no_false_positives(findings: list[dict], is_clean: bool) -> bool:
    """Zero-false-positives: on clean code, require no findings; else not applicable."""
    if not is_clean:
        return True
    return len(findings or []) == 0
