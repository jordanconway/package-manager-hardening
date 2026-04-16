# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Unit tests for audit_ruby()."""

import audit
from conftest import make_workflow


# ---------------------------------------------------------------------------
# Lockfile
# ---------------------------------------------------------------------------

def test_gemfile_lock_present_passes(tmp_path):
    (tmp_path / "Gemfile").write_text('source "https://rubygems.org"\n')
    (tmp_path / "Gemfile.lock").write_text("GEM\n  remote: https://rubygems.org/\n")
    result = audit.audit_ruby(str(tmp_path))
    assert result["lockfile"]["status"] == "pass"


def test_gemfile_lock_missing_fails(tmp_path):
    (tmp_path / "Gemfile").write_text('source "https://rubygems.org"\n')
    result = audit.audit_ruby(str(tmp_path))
    assert result["lockfile"]["status"] == "fail"


def test_gemfile_lock_gitignored(tmp_path):
    (tmp_path / "Gemfile").write_text('source "https://rubygems.org"\n')
    (tmp_path / "Gemfile.lock").write_text("")
    (tmp_path / ".gitignore").write_text("Gemfile.lock\n")
    result = audit.audit_ruby(str(tmp_path))
    assert result["lockfile"]["gitignored"] is True


# ---------------------------------------------------------------------------
# Exact version pins
# ---------------------------------------------------------------------------

def test_exact_pin_passes(tmp_path):
    gemfile = 'source "https://rubygems.org"\ngem "rails", "7.1.2"\n'
    (tmp_path / "Gemfile").write_text(gemfile)
    result = audit.audit_ruby(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"
    assert result["exact_pins"]["loose_count"] == 0


def test_pessimistic_tilde_detected(tmp_path):
    gemfile = 'source "https://rubygems.org"\ngem "rails", "~> 7.1"\n'
    (tmp_path / "Gemfile").write_text(gemfile)
    result = audit.audit_ruby(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"
    assert result["exact_pins"]["loose_count"] == 1


def test_gte_constraint_detected(tmp_path):
    gemfile = 'source "https://rubygems.org"\ngem "rails", ">= 7.1"\n'
    (tmp_path / "Gemfile").write_text(gemfile)
    result = audit.audit_ruby(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"


def test_gem_without_version_not_flagged(tmp_path):
    # gem declarations without a version string are not flagged by exact_pins check
    gemfile = 'source "https://rubygems.org"\ngem "rails"\n'
    (tmp_path / "Gemfile").write_text(gemfile)
    result = audit.audit_ruby(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"


# ---------------------------------------------------------------------------
# Ruby version
# ---------------------------------------------------------------------------

def test_ruby_version_in_gemfile(tmp_path):
    gemfile = 'source "https://rubygems.org"\nruby "3.2.2"\n'
    (tmp_path / "Gemfile").write_text(gemfile)
    result = audit.audit_ruby(str(tmp_path))
    assert result["ruby_version"]["status"] == "pass"
    assert result["ruby_version"]["gemfile_directive"] is True


def test_ruby_version_file(tmp_path):
    (tmp_path / "Gemfile").write_text('source "https://rubygems.org"\n')
    (tmp_path / ".ruby-version").write_text("3.2.2\n")
    result = audit.audit_ruby(str(tmp_path))
    assert result["ruby_version"]["status"] == "pass"
    assert result["ruby_version"]["ruby_version_file"] is True


def test_no_ruby_version_fails(tmp_path):
    (tmp_path / "Gemfile").write_text('source "https://rubygems.org"\n')
    result = audit.audit_ruby(str(tmp_path))
    assert result["ruby_version"]["status"] == "fail"


# ---------------------------------------------------------------------------
# CI patterns
# ---------------------------------------------------------------------------

def test_ci_frozen_and_audit_passes(tmp_path):
    (tmp_path / "Gemfile").write_text('source "https://rubygems.org"\n')
    content = "env:\n  BUNDLE_FROZEN: 'true'\nsteps:\n  - run: bundle install\n  - run: bundle audit\n"
    make_workflow(tmp_path, "ci.yml", content)
    result = audit.audit_ruby(str(tmp_path))
    assert result["ci"]["bundle_frozen"] is True
    assert result["ci"]["bundle_audit"] is True
    assert result["ci"]["status"] == "pass"


def test_ci_missing_bundle_audit(tmp_path):
    (tmp_path / "Gemfile").write_text('source "https://rubygems.org"\n')
    make_workflow(tmp_path, "ci.yml", "env:\n  BUNDLE_FROZEN: 'true'\nsteps:\n  - run: bundle install\n")
    result = audit.audit_ruby(str(tmp_path))
    assert result["ci"]["bundle_audit"] is False
    assert result["ci"]["status"] == "fail"


def test_ci_bundle_update_flagged(tmp_path):
    (tmp_path / "Gemfile").write_text('source "https://rubygems.org"\n')
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: bundle update\n")
    result = audit.audit_ruby(str(tmp_path))
    assert result["ci"]["install_not_update"] is False
