# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Unit tests for audit_dependabot()."""

import audit
from conftest import write_file

DEPENDABOT_FULL = """\
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 7

  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 7
"""

DEPENDABOT_NO_COOLDOWN = """\
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
"""


# ---------------------------------------------------------------------------
# Missing file
# ---------------------------------------------------------------------------

def test_missing_dependabot_file(tmp_path):
    result = audit.audit_dependabot(str(tmp_path), ["nodejs"])
    assert result["file"] is None
    assert result["status"] == "missing"
    assert result["ecosystems"]["nodejs"] == "missing"


def test_missing_file_multiple_ecosystems(tmp_path):
    result = audit.audit_dependabot(str(tmp_path), ["nodejs", "python", "go"])
    assert all(v == "missing" for v in result["ecosystems"].values())


# ---------------------------------------------------------------------------
# File present but ecosystem missing
# ---------------------------------------------------------------------------

def test_ecosystem_not_in_dependabot(tmp_path):
    write_file(tmp_path, ".github/dependabot.yml", DEPENDABOT_NO_COOLDOWN)
    result = audit.audit_dependabot(str(tmp_path), ["go"])
    assert result["ecosystems"]["go"]["status"] == "missing"


# ---------------------------------------------------------------------------
# Cooldown not configured (warn)
# ---------------------------------------------------------------------------

def test_ecosystem_present_no_cooldown_warns(tmp_path):
    write_file(tmp_path, ".github/dependabot.yml", DEPENDABOT_NO_COOLDOWN)
    result = audit.audit_dependabot(str(tmp_path), ["nodejs"])
    assert result["ecosystems"]["nodejs"]["status"] == "warn"
    assert result["ecosystems"]["nodejs"]["cooldown_configured"] is False


# ---------------------------------------------------------------------------
# Cooldown configured (pass)
# ---------------------------------------------------------------------------

def test_ecosystem_with_cooldown_passes(tmp_path):
    write_file(tmp_path, ".github/dependabot.yml", DEPENDABOT_FULL)
    result = audit.audit_dependabot(str(tmp_path), ["nodejs"])
    assert result["ecosystems"]["nodejs"]["status"] == "pass"
    assert result["ecosystems"]["nodejs"]["cooldown_configured"] is True
    assert result["ecosystems"]["nodejs"]["cooldown_default_days"] == 7


def test_multiple_ecosystems_all_configured(tmp_path):
    write_file(tmp_path, ".github/dependabot.yml", DEPENDABOT_FULL)
    result = audit.audit_dependabot(str(tmp_path), ["nodejs", "python"])
    assert result["ecosystems"]["nodejs"]["status"] == "pass"
    assert result["ecosystems"]["python"]["status"] == "pass"
    assert result["status"] == "pass"


def test_overall_status_fail_when_any_missing(tmp_path):
    write_file(tmp_path, ".github/dependabot.yml", DEPENDABOT_FULL)
    result = audit.audit_dependabot(str(tmp_path), ["nodejs", "go"])
    # go is not in DEPENDABOT_FULL, so it's missing
    assert result["ecosystems"]["go"]["status"] == "missing"
    assert result["status"] == "fail"


# ---------------------------------------------------------------------------
# Terraform known bug note
# ---------------------------------------------------------------------------

def test_terraform_known_bug_noted(tmp_path):
    content = """\
version: 2
updates:
  - package-ecosystem: "terraform"
    directory: "/"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 7
"""
    write_file(tmp_path, ".github/dependabot.yml", content)
    result = audit.audit_dependabot(str(tmp_path), ["terraform"])
    assert "known_bug" in result["ecosystems"]["terraform"]


# ---------------------------------------------------------------------------
# dependabot.yaml (alternative extension)
# ---------------------------------------------------------------------------

def test_dependabot_yaml_extension(tmp_path):
    write_file(tmp_path, ".github/dependabot.yaml", DEPENDABOT_FULL)
    result = audit.audit_dependabot(str(tmp_path), ["nodejs"])
    assert result["file"] is not None
    assert result["ecosystems"]["nodejs"]["status"] == "pass"
