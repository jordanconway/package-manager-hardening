# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Unit tests for audit_go()."""

import audit
from conftest import make_workflow


MINIMAL_GOMOD = "module example.com/foo\n\ngo 1.21\n"


# ---------------------------------------------------------------------------
# Lockfile (go.sum)
# ---------------------------------------------------------------------------

def test_gosum_present_passes(tmp_path):
    (tmp_path / "go.mod").write_text(MINIMAL_GOMOD)
    (tmp_path / "go.sum").write_text("")
    result = audit.audit_go(str(tmp_path))
    assert result["lockfile"]["status"] == "pass"
    assert result["lockfile"]["go.sum"] is True


def test_gosum_missing_fails(tmp_path):
    (tmp_path / "go.mod").write_text(MINIMAL_GOMOD)
    result = audit.audit_go(str(tmp_path))
    assert result["lockfile"]["status"] == "fail"


def test_gosum_gitignored_fails(tmp_path):
    (tmp_path / "go.mod").write_text(MINIMAL_GOMOD)
    (tmp_path / "go.sum").write_text("")
    (tmp_path / ".gitignore").write_text("go.sum\n")
    result = audit.audit_go(str(tmp_path))
    assert result["lockfile"]["status"] == "fail"
    assert result["lockfile"]["go.sum_gitignored"] is True


# ---------------------------------------------------------------------------
# Version pins
# ---------------------------------------------------------------------------

def test_no_bad_refs_passes(tmp_path):
    gomod = MINIMAL_GOMOD + "\nrequire github.com/pkg/errors v0.9.1\n"
    (tmp_path / "go.mod").write_text(gomod)
    (tmp_path / "go.sum").write_text("")
    result = audit.audit_go(str(tmp_path))
    assert result["version_pins"]["status"] == "pass"
    assert result["version_pins"]["bad_refs"] == []


def test_latest_ref_detected(tmp_path):
    gomod = MINIMAL_GOMOD + "\nrequire github.com/foo/bar @latest\n"
    (tmp_path / "go.mod").write_text(gomod)
    (tmp_path / "go.sum").write_text("")
    result = audit.audit_go(str(tmp_path))
    assert result["version_pins"]["status"] == "fail"


def test_master_ref_detected(tmp_path):
    gomod = MINIMAL_GOMOD + "\n// require github.com/foo/bar @master\n"
    (tmp_path / "go.mod").write_text(gomod)
    (tmp_path / "go.sum").write_text("")
    result = audit.audit_go(str(tmp_path))
    assert result["version_pins"]["status"] == "fail"


# ---------------------------------------------------------------------------
# Sum database
# ---------------------------------------------------------------------------

def test_gonosumdb_wildcard_flagged(tmp_path):
    (tmp_path / "go.mod").write_text(MINIMAL_GOMOD)
    (tmp_path / "go.sum").write_text("")
    make_workflow(tmp_path, "ci.yml", "env:\n  GONOSUMDB: '*'\n")
    result = audit.audit_go(str(tmp_path))
    assert result["sum_database"]["status"] == "fail"
    assert result["sum_database"]["gonosumdb_wildcard"] is True


def test_gonosumdb_scoped_passes(tmp_path):
    (tmp_path / "go.mod").write_text(MINIMAL_GOMOD)
    (tmp_path / "go.sum").write_text("")
    make_workflow(tmp_path, "ci.yml", "env:\n  GONOSUMDB: 'github.com/mycompany/*'\n")
    result = audit.audit_go(str(tmp_path))
    assert result["sum_database"]["status"] == "pass"


# ---------------------------------------------------------------------------
# CI checks
# ---------------------------------------------------------------------------

def test_ci_go_mod_verify_found(tmp_path):
    (tmp_path / "go.mod").write_text(MINIMAL_GOMOD)
    (tmp_path / "go.sum").write_text("")
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: go mod verify\n  - run: govulncheck ./...\n")
    result = audit.audit_go(str(tmp_path))
    assert result["ci"]["go_mod_verify"] is True
    assert result["ci"]["govulncheck"] is True
    assert result["ci"]["status"] == "pass"


def test_ci_missing_govulncheck(tmp_path):
    (tmp_path / "go.mod").write_text(MINIMAL_GOMOD)
    (tmp_path / "go.sum").write_text("")
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: go mod verify\n")
    result = audit.audit_go(str(tmp_path))
    assert result["ci"]["go_mod_verify"] is True
    assert result["ci"]["govulncheck"] is False
    assert result["ci"]["status"] == "fail"


def test_ci_no_workflows(tmp_path):
    (tmp_path / "go.mod").write_text(MINIMAL_GOMOD)
    (tmp_path / "go.sum").write_text("")
    result = audit.audit_go(str(tmp_path))
    assert result["ci"]["go_mod_verify"] is False
    assert result["ci"]["govulncheck"] is False
