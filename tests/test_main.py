# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Integration tests for audit.py — runs the script as a subprocess."""

import json
import subprocess
import sys
from pathlib import Path

AUDIT_PY = str(Path(__file__).parent.parent / "skills" / "harden-packages" / "audit.py")


def run_audit(path, pretty=False):
    """Run audit.py and return parsed JSON output."""
    cmd = [sys.executable, AUDIT_PY, "--path", str(path)]
    if pretty:
        cmd.append("--pretty")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result, json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Basic output structure
# ---------------------------------------------------------------------------

def test_empty_repo_valid_json(tmp_path):
    result, report = run_audit(tmp_path)
    assert result.returncode == 0
    assert "repo" in report
    assert "ecosystems_detected" in report
    assert report["ecosystems_detected"] == []
    assert "dependabot" in report
    assert "harden_runner" in report


def test_pretty_flag_produces_indented_output(tmp_path):
    result, _ = run_audit(tmp_path, pretty=True)
    assert result.returncode == 0
    # Pretty output has newlines and spaces
    assert "\n  " in result.stdout


def test_compact_output_without_pretty(tmp_path):
    result, _ = run_audit(tmp_path, pretty=False)
    assert result.returncode == 0
    # Compact output is a single line
    assert result.stdout.strip().count("\n") == 0


def test_invalid_path_exits_nonzero():
    result = subprocess.run(
        [sys.executable, AUDIT_PY, "--path", "/nonexistent/path/abc123"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert "error" in report


# ---------------------------------------------------------------------------
# Single ecosystem — Node.js
# ---------------------------------------------------------------------------

def test_nodejs_repo_detected(tmp_path):
    (tmp_path / "package.json").write_text('{"dependencies": {"lodash": "4.17.21"}}')
    (tmp_path / "package-lock.json").write_text("{}")
    (tmp_path / ".npmrc").write_text("minimum-release-age=10080\n")
    _, report = run_audit(tmp_path)
    assert "nodejs" in report["ecosystems_detected"]
    assert "nodejs" in report
    assert report["nodejs"]["lockfile"]["status"] == "pass"
    assert report["nodejs"]["exact_pins"]["status"] == "pass"
    # Resolver-level cooldown is now a fact (no standalone status); the verdict
    # lives in the cross-cutting cooldown section.
    assert report["nodejs"]["minimum_release_age"]["configured"] is True
    assert report["cooldown"]["ecosystems"]["nodejs"]["resolver_level"] is True


def test_nodejs_loose_pins_detected(tmp_path):
    (tmp_path / "package.json").write_text('{"dependencies": {"lodash": "^4.17.21"}}')
    _, report = run_audit(tmp_path)
    assert report["nodejs"]["exact_pins"]["status"] == "fail"
    assert report["nodejs"]["exact_pins"]["unpinned_count"] >= 1


# ---------------------------------------------------------------------------
# Multi-ecosystem
# ---------------------------------------------------------------------------

def test_multi_ecosystem_all_detected(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "go.mod").write_text("module example.com/app\n\ngo 1.21\n")
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'app'\nversion = '0.1.0'\n")
    _, report = run_audit(tmp_path)
    detected = report["ecosystems_detected"]
    assert "nodejs" in detected
    assert "go" in detected
    assert "rust" in detected
    assert "nodejs" in report
    assert "go" in report
    assert "rust" in report


# ---------------------------------------------------------------------------
# Dependabot and Harden-Runner in output
# ---------------------------------------------------------------------------

def test_dependabot_missing_in_output(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    _, report = run_audit(tmp_path)
    assert report["dependabot"]["status"] == "missing"


def test_harden_runner_no_workflows_in_output(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    _, report = run_audit(tmp_path)
    assert report["harden_runner"]["status"] == "no_workflows"


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------

def test_corrupt_package_json_does_not_crash(tmp_path):
    (tmp_path / "package.json").write_text("{ invalid json !!!")
    result, report = run_audit(tmp_path)
    # Should not crash; either detected with error or gracefully skipped
    assert result.returncode == 0
    assert "repo" in report
