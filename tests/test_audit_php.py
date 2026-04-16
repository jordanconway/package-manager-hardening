# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Unit tests for audit_php()."""

import json

import audit
from conftest import make_workflow


def make_composer_json(tmp_path, require=None, require_dev=None):
    data = {}
    if require:
        data["require"] = require
    if require_dev:
        data["require-dev"] = require_dev
    (tmp_path / "composer.json").write_text(json.dumps(data))


# ---------------------------------------------------------------------------
# Lockfile
# ---------------------------------------------------------------------------

def test_composer_lock_present_passes(tmp_path):
    make_composer_json(tmp_path)
    (tmp_path / "composer.lock").write_text("{}")
    result = audit.audit_php(str(tmp_path))
    assert result["lockfile"]["status"] == "pass"


def test_composer_lock_missing_fails(tmp_path):
    make_composer_json(tmp_path)
    result = audit.audit_php(str(tmp_path))
    assert result["lockfile"]["status"] == "fail"


def test_composer_lock_gitignored(tmp_path):
    make_composer_json(tmp_path)
    (tmp_path / "composer.lock").write_text("{}")
    (tmp_path / ".gitignore").write_text("composer.lock\n")
    result = audit.audit_php(str(tmp_path))
    assert result["lockfile"]["gitignored"] is True


# ---------------------------------------------------------------------------
# Exact pins
# ---------------------------------------------------------------------------

def test_exact_pins_pass(tmp_path):
    make_composer_json(tmp_path, require={"vendor/package": "1.2.3"})
    result = audit.audit_php(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"


def test_caret_pin_detected(tmp_path):
    make_composer_json(tmp_path, require={"vendor/package": "^1.2.3"})
    result = audit.audit_php(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"
    assert result["exact_pins"]["loose_count"] == 1


def test_tilde_pin_detected(tmp_path):
    make_composer_json(tmp_path, require={"vendor/package": "~1.2.3"})
    result = audit.audit_php(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"


def test_php_key_skipped(tmp_path):
    make_composer_json(tmp_path, require={"php": ">=8.0", "vendor/lib": "1.0.0"})
    result = audit.audit_php(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"


def test_require_dev_loose_pin_detected(tmp_path):
    make_composer_json(tmp_path, require_dev={"phpunit/phpunit": "^10.0"})
    result = audit.audit_php(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"


# ---------------------------------------------------------------------------
# Roave Security Advisories
# ---------------------------------------------------------------------------

def test_roave_present(tmp_path):
    make_composer_json(tmp_path, require_dev={"roave/security-advisories": "dev-latest"})
    result = audit.audit_php(str(tmp_path))
    assert result["roave_security_advisories"]["status"] == "pass"
    assert result["roave_security_advisories"]["present"] is True


def test_roave_missing(tmp_path):
    make_composer_json(tmp_path, require_dev={"phpunit/phpunit": "10.0.0"})
    result = audit.audit_php(str(tmp_path))
    assert result["roave_security_advisories"]["status"] == "fail"
    assert result["roave_security_advisories"]["present"] is False


# ---------------------------------------------------------------------------
# CI flags
# ---------------------------------------------------------------------------

def test_ci_all_flags_present(tmp_path):
    make_composer_json(tmp_path)
    content = (
        "steps:\n"
        "  - env:\n      COMPOSER_NO_INTERACTION: 1\n"
        "    run: composer install --no-scripts --no-plugins --prefer-dist\n"
        "  - run: composer audit\n"
    )
    make_workflow(tmp_path, "ci.yml", content)
    result = audit.audit_php(str(tmp_path))
    assert result["ci"]["no_scripts"] is True
    assert result["ci"]["no_plugins"] is True
    assert result["ci"]["composer_audit"] is True
    assert result["ci"]["no_interaction"] is True
    assert result["ci"]["status"] == "pass"


def test_ci_missing_no_scripts_fails(tmp_path):
    make_composer_json(tmp_path)
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: composer install --no-plugins\n  - run: composer audit\n  - env:\n      COMPOSER_NO_INTERACTION: 1\n")
    result = audit.audit_php(str(tmp_path))
    assert result["ci"]["no_scripts"] is False
    assert result["ci"]["status"] == "fail"
