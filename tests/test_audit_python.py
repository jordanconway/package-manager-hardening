# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Unit tests for audit_python()."""

import audit
from conftest import make_workflow, write_file


# ---------------------------------------------------------------------------
# Manager detection
# ---------------------------------------------------------------------------

def test_uv_detected_by_uv_lock(tmp_path):
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    result = audit.audit_python(str(tmp_path))
    assert result["manager"] == "uv"


def test_uv_detected_by_tool_section(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n\n[tool.uv]\nexclude-newer = '2025-01-01'\n")
    result = audit.audit_python(str(tmp_path))
    assert result["manager"] == "uv"


def test_pip_detected_by_requirements(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
    result = audit.audit_python(str(tmp_path))
    assert result["manager"] == "pip"


def test_pip_when_no_uv_indicators(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    result = audit.audit_python(str(tmp_path))
    assert result["manager"] == "pip"


# ---------------------------------------------------------------------------
# Lockfile
# ---------------------------------------------------------------------------

def test_uv_lockfile_present(tmp_path):
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / "pyproject.toml").write_text("[tool.uv]\n")
    result = audit.audit_python(str(tmp_path))
    assert result["lockfile"]["status"] == "pass"
    assert result["lockfile"]["file"] == "uv.lock"


def test_uv_lockfile_missing(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.uv]\n")
    result = audit.audit_python(str(tmp_path))
    assert result["lockfile"]["status"] == "fail"


def test_pip_lockfile_requirements_lock(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
    (tmp_path / "requirements.lock").write_text("requests==2.31.0 --hash=sha256:abc\n")
    result = audit.audit_python(str(tmp_path))
    assert result["lockfile"]["status"] == "pass"


def test_pip_lockfile_missing(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
    result = audit.audit_python(str(tmp_path))
    assert result["lockfile"]["status"] == "fail"


# ---------------------------------------------------------------------------
# Exact pins
# ---------------------------------------------------------------------------

def test_exact_pins_pass(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["requests==2.31.0", "httpx==0.25.0"]\n'
    )
    result = audit.audit_python(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"


def test_exact_pins_loose_detected(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["requests>=2.0.0"]\n'
    )
    result = audit.audit_python(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"
    assert len(result["exact_pins"]["loose"]) > 0


# ---------------------------------------------------------------------------
# UV config
# ---------------------------------------------------------------------------

def test_uv_config_all_set(tmp_path):
    content = (
        "[tool.uv]\n"
        "exclude-newer = '2025-01-01T00:00:00Z'\n"
        "require-hashes = true\n"
        "verify-hashes = true\n"
    )
    (tmp_path / "pyproject.toml").write_text(content)
    (tmp_path / "uv.lock").write_text("")
    result = audit.audit_python(str(tmp_path))
    assert result["uv_config"]["status"] == "pass"
    assert result["uv_config"]["require_hashes"] is True
    assert result["uv_config"]["verify_hashes"] is True
    assert result["uv_config"]["exclude_newer"] is not None


def test_uv_config_missing_exclude_newer(tmp_path):
    content = "[tool.uv]\nrequire-hashes = true\nverify-hashes = true\n"
    (tmp_path / "pyproject.toml").write_text(content)
    (tmp_path / "uv.lock").write_text("")
    result = audit.audit_python(str(tmp_path))
    assert result["uv_config"]["status"] == "fail"
    assert result["uv_config"]["exclude_newer"] is None


def test_uv_config_missing_require_hashes(tmp_path):
    content = "[tool.uv]\nexclude-newer = '2025-01-01T00:00:00Z'\n"
    (tmp_path / "pyproject.toml").write_text(content)
    (tmp_path / "uv.lock").write_text("")
    result = audit.audit_python(str(tmp_path))
    assert result["uv_config"]["status"] == "fail"
    assert result["uv_config"]["require_hashes"] is False


# ---------------------------------------------------------------------------
# CI frozen install
# ---------------------------------------------------------------------------

def test_uv_sync_frozen_found(tmp_path):
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / "pyproject.toml").write_text("[tool.uv]\n")
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: uv sync --frozen\n")
    result = audit.audit_python(str(tmp_path))
    assert result["ci_frozen_install"]["status"] == "pass"


def test_pip_require_hashes_found(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: pip install -r requirements.lock --require-hashes\n")
    result = audit.audit_python(str(tmp_path))
    assert result["ci_frozen_install"]["status"] == "pass"


def test_ci_frozen_install_missing(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: pip install -r requirements.txt\n")
    result = audit.audit_python(str(tmp_path))
    assert result["ci_frozen_install"]["status"] == "fail"
