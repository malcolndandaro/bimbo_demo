"""Unit tests for the pure cores (slice 04 agreed test scope).

External behaviour only — no workspace, no network. Covers the PR context builder
and the findings parser/validator.
"""

import json

import review_core


# --- build_review_context --------------------------------------------------------
def test_empty_diff_yields_no_files():
    ctx = review_core.build_review_context("")
    assert ctx == {"files": [], "n_files": 0}


def test_single_python_file_added_line_numbers():
    diff = (
        "diff --git a/src/jobs/x.py b/src/jobs/x.py\n"
        "--- a/src/jobs/x.py\n"
        "+++ b/src/jobs/x.py\n"
        "@@ -0,0 +1,3 @@\n"
        "+import os\n"
        "+\n"
        "+x = 1\n"
    )
    ctx = review_core.build_review_context(diff)
    assert ctx["n_files"] == 1
    f = ctx["files"][0]
    assert f["path"] == "src/jobs/x.py"
    assert f["language"] == "python"
    assert f["added"] == [(1, "import os"), (2, ""), (3, "x = 1")]


def test_context_line_advances_numbering():
    diff = (
        "diff --git a/a.py b/a.py\n"
        "+++ b/a.py\n"
        "@@ -10,3 +10,4 @@\n"
        " existing = 0\n"  # context line at 10
        "+added_at_11 = 1\n"
        " more = 2\n"
    )
    f = review_core.build_review_context(diff)["files"][0]
    assert f["added"] == [(11, "added_at_11 = 1")]


def test_multi_file_diff():
    diff = (
        "diff --git a/a.py b/a.py\n+++ b/a.py\n@@ -0,0 +1 @@\n+a = 1\n"
        "diff --git a/q.sql b/q.sql\n+++ b/q.sql\n@@ -0,0 +1 @@\n+select 1\n"
    )
    ctx = review_core.build_review_context(diff)
    assert ctx["n_files"] == 2
    assert {f["language"] for f in ctx["files"]} == {"python", "sql"}


def test_rename_flagged():
    diff = (
        "diff --git a/old.py b/new.py\n"
        "similarity index 100%\n"
        "rename from old.py\n"
        "rename to new.py\n"
    )
    f = review_core.build_review_context(diff)["files"][0]
    assert f["is_rename"] is True
    assert f["added"] == []


def test_binary_flagged():
    diff = "diff --git a/logo.png b/logo.png\nBinary files a/logo.png and b/logo.png differ\n"
    f = review_core.build_review_context(diff)["files"][0]
    assert f["is_binary"] is True


# --- parse_findings --------------------------------------------------------------
def _valid(**over):
    base = {
        "file": "src/jobs/x.py",
        "line": 27,
        "severity": "BLOCKER",
        "rule_id": "ENV-01",
        "citation": "BimbOps Handbook › Catalog-per-Env › ENV-01",
        "message": "Referencia cross-env a bimbo_prd.",
        "suggestion": "Parametriza el catálogo.",
    }
    base.update(over)
    return base


def test_parse_valid_list():
    out = review_core.parse_findings([_valid()])
    assert len(out) == 1
    assert out[0]["rule_id"] == "ENV-01"
    assert out[0]["line"] == 27
    assert out[0]["patch"] is None


def test_parse_findings_wrapper_object():
    out = review_core.parse_findings({"summary": "x", "findings": [_valid()]})
    assert len(out) == 1


def test_parse_json_string():
    out = review_core.parse_findings(json.dumps({"findings": [_valid()]}))
    assert len(out) == 1


def test_missing_required_field_dropped():
    bad = _valid()
    del bad["rule_id"]
    assert review_core.parse_findings([bad]) == []


def test_invalid_severity_dropped():
    assert review_core.parse_findings([_valid(severity="CRITICAL")]) == []


def test_malformed_json_returns_empty():
    assert review_core.parse_findings("not json at all {[") == []


def test_prose_wrapped_json_extracted():
    raw = 'Claro, aquí está:\n```json\n{"findings": [' + json.dumps(_valid()) + "]}\n```"
    out = review_core.parse_findings(raw)
    assert len(out) == 1


def test_empty_and_none():
    assert review_core.parse_findings("") == []
    assert review_core.parse_findings(None) == []
    assert review_core.parse_findings({"findings": []}) == []


def test_extra_fields_ignored_and_string_line_coerced():
    f = _valid(line="42", unexpected="ignored")
    out = review_core.parse_findings([f])
    assert out[0]["line"] == 42
    assert "unexpected" not in out[0]


def test_non_numeric_line_becomes_null():
    out = review_core.parse_findings([_valid(line="n/a")])
    assert out[0]["line"] is None


def test_multiple_hunks_one_file_line_numbers():
    diff = (
        "diff --git a/m.py b/m.py\n"
        "+++ b/m.py\n"
        "@@ -1,1 +1,2 @@\n"
        " a = 0\n"
        "+b = 1\n"
        "@@ -20,1 +21,2 @@\n"
        " c = 2\n"
        "+d = 3\n"
    )
    f = review_core.build_review_context(diff)["files"][0]
    assert f["added"] == [(2, "b = 1"), (22, "d = 3")]


def test_deleted_only_file_has_no_added():
    diff = "diff --git a/d.py b/d.py\n+++ b/d.py\n@@ -1,2 +0,0 @@\n-gone = 1\n-also = 2\n"
    f = review_core.build_review_context(diff)["files"][0]
    assert f["added"] == []


def test_parse_findings_recovers_despite_trailing_junk():
    raw = '{"findings": [' + json.dumps(_valid()) + "]} and then trailing {garbage"
    assert len(review_core.parse_findings(raw)) == 1


def test_parse_review_recovers_summary_from_code_fence():
    raw = '```json\n{"summary": "hola", "findings": [' + json.dumps(_valid()) + "]}\n```"
    review = review_core.parse_review(raw)
    assert review["summary"] == "hola"
    assert len(review["findings"]) == 1


# --- decide_gate (severity gate, ADR-0002) ---------------------------------------
def test_decide_gate_empty_is_success():
    d = review_core.decide_gate([])
    assert d["conclusion"] == "success"
    assert d["blocker_count"] == 0


def test_decide_gate_only_advisory_is_neutral():
    d = review_core.decide_gate([_valid(severity="SUGGESTION"), _valid(severity="STYLE")])
    assert d["conclusion"] == "neutral"
    assert d["blocker_count"] == 0


def test_decide_gate_any_blocker_is_failure():
    d = review_core.decide_gate([_valid(severity="SUGGESTION"), _valid(severity="BLOCKER")])
    assert d["conclusion"] == "failure"
    assert d["blocker_count"] == 1


def test_decide_gate_ignores_invalid_severity():
    assert review_core.decide_gate([{"severity": "CRITICAL"}])["conclusion"] == "success"


# --- to_check_run (GitHub Check Run payload mapper) ------------------------------
def test_to_check_run_severity_levels_and_conclusion():
    findings = [
        _valid(severity="BLOCKER"),
        _valid(severity="SUGGESTION"),
        _valid(severity="STYLE"),
    ]
    cr = review_core.to_check_run(findings, review_core.decide_gate(findings))
    assert cr["conclusion"] == "failure"
    assert [a["annotation_level"] for a in cr["output"]["annotations"]] == [
        "failure",
        "warning",
        "notice",
    ]


def test_to_check_run_file_level_line_defaults_to_1():
    cr = review_core.to_check_run([_valid(line=None)], {"conclusion": "failure", "summary": "x"})
    a = cr["output"]["annotations"][0]
    assert a["start_line"] == 1 and a["end_line"] == 1


def test_to_check_run_caps_at_50_with_overflow_note():
    findings = [_valid(severity="STYLE", file=f"f{i}.py", line=i + 1) for i in range(60)]
    cr = review_core.to_check_run(findings, review_core.decide_gate(findings))
    assert len(cr["output"]["annotations"]) == 50
    assert "no anotados" in cr["output"]["summary"]


# --- fix mode (slice 06) ---------------------------------------------------------
def test_is_authorized_matrix():
    assert review_core.is_authorized("write", False)[0] is True
    assert review_core.is_authorized("admin", False)[0] is True
    assert review_core.is_authorized("maintain", False)[0] is True
    assert review_core.is_authorized("read", False)[0] is False  # insufficient permission
    assert review_core.is_authorized("triage", False)[0] is False
    assert review_core.is_authorized("write", True)[0] is False  # protected branch


def test_extract_code_from_fence():
    assert review_core.extract_code("Claro:\n```python\nx = 1\n```\nlisto") == "x = 1\n"


def test_extract_code_requires_fence():
    assert review_core.extract_code("x = 2") is None  # no fence → rejected, not raw-accepted
    assert review_core.extract_code("```\ny = 3\n```") == "y = 3\n"
    assert review_core.extract_code("") is None
    assert review_core.extract_code(None) is None


def test_select_fixable_confines_to_changed_files():
    findings = [
        _valid(file="src/a.py"),
        _valid(file="src/b.py"),
        _valid(file="../evil.py"),
        _valid(file="/etc/passwd"),
    ]
    out = review_core.select_fixable(findings, {"src/a.py"})
    assert set(out) == {"src/a.py"}  # b.py unchanged; ../ and /abs rejected


def test_validate_content_python():
    assert review_core.validate_content("a.py", "def f():\n    return 1\n")[0] is True
    bad, err = review_core.validate_content("a.py", "def f(:\n")
    assert bad is False and "SyntaxError" in err


def test_validate_content_empty_and_sql():
    assert review_core.validate_content("a.py", "")[0] is False
    assert review_core.validate_content("q.sql", "SELECT 1\n")[0] is True


def test_build_fix_prompt_includes_findings_and_full_file_ask():
    sys_p, user_p = review_core.build_fix_prompt("x.py", "old = 1\n", [_valid(message="m1")])
    assert "MODO ARREGLO" in sys_p
    assert "x.py" in user_p and "ENV-01" in user_p and "COMPLETO" in user_p


def test_build_fix_prompt_includes_handbook_rules():
    rules = [
        {
            "rule_id": "ENV-01",
            "citation": "Handbook > Catalog-per-Env",
            "content": "Sin refs cross-env",
        }
    ]
    _, user_p = review_core.build_fix_prompt("x.py", "old = 1\n", [_valid()], rules)
    assert "HANDBOOK" in user_p and "ENV-01" in user_p and "Sin refs cross-env" in user_p


def test_build_fix_retry_prompt_includes_lint_errors():
    sys_p, user_p = review_core.build_fix_retry_prompt("x.py", "import os, sys\n", "E401 imports")
    assert "REINTENTO" in sys_p
    assert "x.py" in user_p and "E401" in user_p
    assert "import os, sys" in user_p


def test_linter_for_by_extension():
    assert review_core.linter_for("src/jobs/x.py") == "ruff"
    assert review_core.linter_for("sql/q.sql") == "sqlfluff"
    assert review_core.linter_for("README.md") is None
    assert review_core.linter_for("databricks.yml") is None


# --- eval scorer decisions (slice 09) --------------------------------------------
def test_score_cross_env():
    env = [_valid(rule_id="ENV-01")]
    assert review_core.score_cross_env(env, True) is True
    assert review_core.score_cross_env(env, False) is False
    assert review_core.score_cross_env([], True) is False  # missed → fail
    assert review_core.score_cross_env([], False) is True  # correctly absent


def test_score_transform():
    assert review_core.score_transform([_valid(rule_id="TP-02")], True) is True
    assert review_core.score_transform([_valid(rule_id="ENV-01")], True) is False  # wrong rule
    assert review_core.score_transform([], False) is True


def test_score_no_false_positives():
    assert review_core.score_no_false_positives([], True) is True  # clean + none → pass
    assert review_core.score_no_false_positives([_valid()], True) is False  # clean + finding → FP
    assert review_core.score_no_false_positives([_valid()], False) is True  # not clean → n/a
