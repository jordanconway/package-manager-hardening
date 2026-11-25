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


# ---------------------------------------------------------------------------
# uv ecosystem key satisfies python (lfreleng-actions feedback)
# ---------------------------------------------------------------------------

def test_uv_ecosystem_key_satisfies_python(tmp_path):
    content = """\
version: 2
updates:
  - package-ecosystem: "uv"
    directory: "/"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 7
"""
    write_file(tmp_path, ".github/dependabot.yml", content)
    result = audit.audit_dependabot(str(tmp_path), ["python"])
    assert result["ecosystems"]["python"]["status"] == "pass"
    assert result["ecosystems"]["python"]["ecosystem_key"] == "uv"
    assert result["ecosystems"]["python"]["cooldown_default_days"] == 7


def test_uv_ecosystem_without_cooldown_warns(tmp_path):
    content = """\
version: 2
updates:
  - package-ecosystem: "uv"
    directory: "/"
    schedule:
      interval: "weekly"
"""
    write_file(tmp_path, ".github/dependabot.yml", content)
    result = audit.audit_dependabot(str(tmp_path), ["python"])
    assert result["ecosystems"]["python"]["status"] == "warn"
    assert result["ecosystems"]["python"]["ecosystem_key"] == "uv"


def test_pip_key_still_satisfies_python(tmp_path):
    write_file(tmp_path, ".github/dependabot.yml", DEPENDABOT_FULL)
    result = audit.audit_dependabot(str(tmp_path), ["python"])
    assert result["ecosystems"]["python"]["status"] == "pass"
    assert result["ecosystems"]["python"]["ecosystem_key"] == "pip"


# ---------------------------------------------------------------------------
# Each entry is matched only by its own package-ecosystem value
# ---------------------------------------------------------------------------

def test_header_comment_naming_ecosystem_does_not_hide_its_entry(tmp_path):
    # Regression: a comment above the first entry that mentions "npm" used to
    # be matched as npm's block, so its real cooldown went unseen.
    content = """\
version: 2
updates:
  # npm runtime + dev dependencies (package.json / package-lock.json).
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 7
"""
    write_file(tmp_path, ".github/dependabot.yml", content)
    result = audit.audit_dependabot(str(tmp_path), ["nodejs"])
    assert result["ecosystems"]["nodejs"]["status"] == "pass"
    assert result["ecosystems"]["nodejs"]["cooldown_configured"] is True
    assert result["ecosystems"]["nodejs"]["cooldown_default_days"] == 7


def test_comment_in_other_ecosystem_entry_is_not_matched(tmp_path):
    # The github-actions entry (no cooldown) mentions npm in a comment and
    # comes first; npm's own entry has the cooldown.
    content = """\
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    # Group with npm updates where possible.
    schedule:
      interval: "weekly"

  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 5
"""
    write_file(tmp_path, ".github/dependabot.yml", content)
    result = audit.audit_dependabot(str(tmp_path), ["nodejs"])
    assert result["ecosystems"]["nodejs"]["status"] == "pass"
    assert result["ecosystems"]["nodejs"]["cooldown_default_days"] == 5


def test_unquoted_ecosystem_value(tmp_path):
    content = """\
version: 2
updates:
  - package-ecosystem: npm  # JavaScript
    directory: /
    schedule:
      interval: weekly
    cooldown:
      default-days: 3
"""
    write_file(tmp_path, ".github/dependabot.yml", content)
    result = audit.audit_dependabot(str(tmp_path), ["nodejs"])
    assert result["ecosystems"]["nodejs"]["status"] == "pass"
    assert result["ecosystems"]["nodejs"]["ecosystem_key"] == "npm"
    assert result["ecosystems"]["nodejs"]["cooldown_default_days"] == 3


def test_commented_out_entry_is_not_present(tmp_path):
    content = """\
version: 2
updates:
  # - package-ecosystem: "npm"
  #   cooldown:
  #     default-days: 7
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
"""
    write_file(tmp_path, ".github/dependabot.yml", content)
    result = audit.audit_dependabot(str(tmp_path), ["nodejs", "python"])
    assert result["ecosystems"]["nodejs"]["status"] == "missing"
    assert result["ecosystems"]["python"]["cooldown_configured"] is False


def test_gradle_wrapper_entry_does_not_satisfy_gradle(tmp_path):
    content = """\
version: 2
updates:
- package-ecosystem: gradle-wrapper
  directory: /
  schedule:
    interval: weekly
  cooldown:
    default-days: 7
"""
    write_file(tmp_path, ".github/dependabot.yml", content)
    result = audit.audit_dependabot(str(tmp_path), ["gradle"])
    assert result["ecosystems"]["gradle"]["status"] == "missing"


def test_update_entries_parse_key_order_and_bare_dash():
    content = """\
version: 2
updates:
  - directory: "/"
    package-ecosystem: 'cargo'
    cooldown:
      default-days: 7
  -
    package-ecosystem: "gomod"
    directory: "/"
registries: {}
"""
    entries = audit.dependabot_update_entries(content)
    assert [eco for eco, _ in entries] == ["cargo", "gomod"]
    assert "cooldown:" in entries[0][1]
    assert "registries" not in entries[1][1]
