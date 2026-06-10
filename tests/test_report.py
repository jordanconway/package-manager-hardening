# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Unit tests for report.py (markdown rendering + CI gate)."""

import json
import subprocess
import sys
from pathlib import Path

import report

REPORT_PY = Path(__file__).parent.parent / "skills" / "harden-packages" / "report.py"


# ---------------------------------------------------------------------------
# walk
# ---------------------------------------------------------------------------

def test_walk_yields_nested_statuses():
    tree = {
        "lockfile": {"status": "pass"},
        "ci": {"status": "fail", "nested": {"status": "warn"}},
    }
    found = dict(report.walk(tree, ["nodejs"]))
    assert found["nodejs.lockfile"] == "pass"
    assert found["nodejs.ci"] == "fail"
    assert found["nodejs.ci.nested"] == "warn"


def test_walk_reports_error_keys_as_fail():
    tree = {"error": "boom"}
    found = dict(report.walk(tree, ["rust"]))
    assert found["rust.error"] == "fail"


def test_walk_ignores_non_dict_and_missing_status():
    tree = {"manager": "npm", "list": [1, 2], "sub": {"no_status_here": True}}
    assert list(report.walk(tree, ["nodejs"])) == []


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

def test_render_all_pass_has_no_recommendations():
    audit = {
        "repo": "/x",
        "ecosystems_detected": ["nodejs"],
        "nodejs": {"lockfile": {"status": "pass"}},
    }
    markdown, failing = report.render(audit)
    assert failing == []
    assert "Recommended changes" not in markdown
    assert "No failing checks" in markdown
    assert "✅" in markdown


def test_render_failures_include_hint_and_doc_link():
    audit = {
        "ecosystems_detected": ["python"],
        "python": {"lockfile": {"status": "fail"}},
    }
    markdown, failing = report.render(audit)
    assert failing == ["python.lockfile"]
    assert "Recommended changes" in markdown
    assert "Commit the lockfile" in markdown
    assert "docs/python.md" in markdown


def test_render_missing_counts_as_failing():
    audit = {
        "dependabot": {"status": "missing", "ecosystems": {"go": {"status": "missing"}}},
    }
    _markdown, failing = report.render(audit)
    assert "dependabot" in failing
    assert "dependabot.ecosystems.go" in failing


def test_render_warn_and_na_do_not_fail():
    audit = {
        "harden_runner": {"status": "warn", "workflows": {"codeql.yml": {"status": "warn"}}},
        "nodejs": {"build_script_control": {"status": "n/a"}},
    }
    markdown, failing = report.render(audit)
    assert failing == []
    assert "⚠️" in markdown


def test_render_per_workflow_harden_runner_failure_hint():
    audit = {
        "harden_runner": {"status": "warn", "workflows": {"release.yml": {"status": "fail"}}},
    }
    markdown, failing = report.render(audit)
    assert failing == ["harden_runner.workflows.release.yml"]
    assert "step-security/harden-runner" in markdown
    assert "docs/harden-runner.md" in markdown


# ---------------------------------------------------------------------------
# CLI gate (subprocess: exit codes are the contract the workflow relies on)
# ---------------------------------------------------------------------------

def run_cli(payload, *flags):
    return subprocess.run(
        [sys.executable, str(REPORT_PY), *flags],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_cli_exits_zero_when_clean():
    payload = json.dumps({"nodejs": {"lockfile": {"status": "pass"}}})
    result = run_cli(payload)
    assert result.returncode == 0
    assert "self-audit" in result.stdout


def test_cli_exits_one_on_failure():
    payload = json.dumps({"nodejs": {"lockfile": {"status": "fail"}}})
    result = run_cli(payload)
    assert result.returncode == 1
    assert "failing check" in result.stderr


def test_cli_warn_only_exits_zero_on_failure():
    payload = json.dumps({"nodejs": {"lockfile": {"status": "fail"}}})
    result = run_cli(payload, "--warn-only")
    assert result.returncode == 0
    assert "Recommended changes" in result.stdout


def test_cli_invalid_json_exits_two():
    result = run_cli("not json{")
    assert result.returncode == 2


def test_cli_non_object_json_exits_two():
    result = run_cli(json.dumps(["a", "b"]))
    assert result.returncode == 2


def test_cli_reads_file_argument(tmp_path):
    audit_file = tmp_path / "audit.json"
    audit_file.write_text(json.dumps({"go": {"lockfile": {"status": "pass"}}}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(REPORT_PY), str(audit_file)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0
    assert "go.lockfile" in result.stdout


# ---------------------------------------------------------------------------
# End-to-end against audit.py on a synthetic repo
# ---------------------------------------------------------------------------

def test_end_to_end_with_audit(tmp_path):
    import audit

    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"left-pad": "^1.0.0"}}), encoding="utf-8")
    findings = {
        "repo": str(tmp_path),
        "ecosystems_detected": ["nodejs"],
        "nodejs": audit.audit_nodejs(str(tmp_path)),
    }
    markdown, failing = report.render(findings)
    assert "nodejs.lockfile" in failing  # no lockfile committed
    assert "nodejs.exact_pins" in failing  # ^1.0.0 is loose
    assert "Recommended changes" in markdown
