# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Unit tests for audit_rust()."""

import audit
from conftest import make_workflow, write_file


MINIMAL_CARGO_TOML = "[package]\nname = 'foo'\nversion = '0.1.0'\n"


# ---------------------------------------------------------------------------
# Lockfile
# ---------------------------------------------------------------------------

def test_cargo_lock_present_passes(tmp_path):
    (tmp_path / "Cargo.toml").write_text(MINIMAL_CARGO_TOML)
    (tmp_path / "Cargo.lock").write_text("")
    result = audit.audit_rust(str(tmp_path))
    assert result["lockfile"]["status"] == "pass"


def test_cargo_lock_missing_fails(tmp_path):
    (tmp_path / "Cargo.toml").write_text(MINIMAL_CARGO_TOML)
    result = audit.audit_rust(str(tmp_path))
    assert result["lockfile"]["status"] == "fail"


def test_cargo_lock_gitignored_flagged(tmp_path):
    (tmp_path / "Cargo.toml").write_text(MINIMAL_CARGO_TOML)
    (tmp_path / "Cargo.lock").write_text("")
    (tmp_path / ".gitignore").write_text("Cargo.lock\n")
    result = audit.audit_rust(str(tmp_path))
    assert result["lockfile"]["gitignored"] is True


# ---------------------------------------------------------------------------
# Exact pins
# ---------------------------------------------------------------------------

def test_exact_pin_passes(tmp_path):
    cargo = MINIMAL_CARGO_TOML + '\n[dependencies]\nserde = "=1.0.193"\n'
    (tmp_path / "Cargo.toml").write_text(cargo)
    result = audit.audit_rust(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"


def test_loose_pin_detected(tmp_path):
    cargo = MINIMAL_CARGO_TOML + '\n[dependencies]\nserde = "1.0"\n'
    (tmp_path / "Cargo.toml").write_text(cargo)
    result = audit.audit_rust(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"
    assert result["exact_pins"]["loose_count"] > 0


def test_caret_pin_detected(tmp_path):
    cargo = MINIMAL_CARGO_TOML + '\n[dependencies]\nserde = "^1.0.193"\n'
    (tmp_path / "Cargo.toml").write_text(cargo)
    result = audit.audit_rust(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"


# ---------------------------------------------------------------------------
# Cooldown config
# ---------------------------------------------------------------------------

def test_cooldown_native_cargo_configured(tmp_path):
    """Cargo >= 1.100 reads [registry] global-min-publish-age natively."""
    (tmp_path / "Cargo.toml").write_text(MINIMAL_CARGO_TOML)
    write_file(tmp_path, ".cargo/config.toml", '[registry]\nglobal-min-publish-age = "7 days"\n')
    result = audit.audit_rust(str(tmp_path))
    assert result["cooldown"]["configured"] is True
    assert result["cooldown"]["global_min_publish_age"] == "7 days"
    assert result["cooldown"]["source"] == ".cargo/config.toml"


def test_cooldown_cargo_cooldown_plugin_configured(tmp_path):
    """cargo-cooldown >= 0.3.1 reads the same key from cooldown.toml."""
    (tmp_path / "Cargo.toml").write_text(MINIMAL_CARGO_TOML)
    write_file(tmp_path, "cooldown.toml", '[registry]\nglobal-min-publish-age = "7 days"\n')
    result = audit.audit_rust(str(tmp_path))
    assert result["cooldown"]["configured"] is True
    assert result["cooldown"]["source"] == "cooldown.toml"


def test_cooldown_zero_is_not_configured(tmp_path):
    (tmp_path / "Cargo.toml").write_text(MINIMAL_CARGO_TOML)
    write_file(tmp_path, ".cargo/config.toml", '[registry]\nglobal-min-publish-age = "0"\n')
    result = audit.audit_rust(str(tmp_path))
    assert result["cooldown"]["configured"] is False


def test_cooldown_legacy_table_is_not_configured(tmp_path):
    """`[cooldown] days = 7` in .cargo/config.toml is read by nothing."""
    (tmp_path / "Cargo.toml").write_text(MINIMAL_CARGO_TOML)
    write_file(tmp_path, ".cargo/config.toml", "[cooldown]\ndays = 7\n")
    result = audit.audit_rust(str(tmp_path))
    assert result["cooldown"]["configured"] is False
    assert "global-min-publish-age" in result["cooldown"]["unsupported_table"]


def test_cooldown_missing(tmp_path):
    (tmp_path / "Cargo.toml").write_text(MINIMAL_CARGO_TOML)
    write_file(tmp_path, ".cargo/config.toml", "[net]\noffline = false\n")
    result = audit.audit_rust(str(tmp_path))
    assert result["cooldown"]["configured"] is False


def test_cooldown_no_config_file(tmp_path):
    (tmp_path / "Cargo.toml").write_text(MINIMAL_CARGO_TOML)
    result = audit.audit_rust(str(tmp_path))
    assert result["cooldown"]["configured"] is False


# ---------------------------------------------------------------------------
# CI
# ---------------------------------------------------------------------------

def test_ci_locked_and_audit_passes(tmp_path):
    (tmp_path / "Cargo.toml").write_text(MINIMAL_CARGO_TOML)
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: cargo build --locked\n  - run: cargo audit\n")
    result = audit.audit_rust(str(tmp_path))
    assert result["ci"]["locked_flag"] is True
    assert result["ci"]["cargo_audit"] is True
    assert result["ci"]["status"] == "pass"


def test_ci_missing_locked_fails(tmp_path):
    (tmp_path / "Cargo.toml").write_text(MINIMAL_CARGO_TOML)
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: cargo audit\n")
    result = audit.audit_rust(str(tmp_path))
    assert result["ci"]["locked_flag"] is False
    assert result["ci"]["status"] == "fail"


def test_ci_no_workflows(tmp_path):
    (tmp_path / "Cargo.toml").write_text(MINIMAL_CARGO_TOML)
    result = audit.audit_rust(str(tmp_path))
    assert result["ci"]["status"] == "fail"
