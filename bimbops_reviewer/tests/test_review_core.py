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
