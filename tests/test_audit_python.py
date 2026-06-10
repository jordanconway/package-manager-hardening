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


def test_requires_python_not_flagged_as_loose_pin(tmp_path):
    # requires-python is an interpreter constraint, not a dependency;
    # a bounded range there is the recommended configuration.
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.10,<3.15"\ndependencies = ["requests==2.31.0"]\n'
    )
    result = audit.audit_python(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"
    assert result["exact_pins"]["loose"] == []


def test_requires_python_skipped_but_loose_deps_still_flagged(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.10,<3.15"\ndependencies = ["requests>=2.0.0"]\n'
    )
    result = audit.audit_python(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"
    assert result["exact_pins"]["loose"] == ["requests>=2.0.0"]


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


# ---------------------------------------------------------------------------
# exact_pins parser scope (lfreleng-actions feedback)
# ---------------------------------------------------------------------------

def test_authors_not_parsed_as_dependency(tmp_path):
    # authors = [{ email = "..." }] lives in [project] but is not a
    # dependency array — the old line-based parser flagged ", email = ".
    content = (
        "[project]\n"
        'name = "x"\n'
        'authors = [{ name = "Jane Dev", email = "jane@example.org" }]\n'
        'maintainers = [{ name = "Joe Dev", email = "joe@example.org" }]\n'
        'dependencies = ["requests==2.31.0"]\n'
    )
    (tmp_path / "pyproject.toml").write_text(content)
    result = audit.audit_python(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"
    assert result["exact_pins"]["loose"] == []


def test_loose_dep_in_multiline_array_flagged(tmp_path):
    content = (
        "[project]\n"
        "dependencies = [\n"
        '  "requests>=2.0.0",\n'
        '  "httpx==0.25.0",\n'
        "]\n"
    )
    (tmp_path / "pyproject.toml").write_text(content)
    result = audit.audit_python(str(tmp_path))
    assert result["exact_pins"]["loose"] == ["requests>=2.0.0"]


def test_loose_dep_in_dependency_groups_flagged(tmp_path):
    content = (
        "[dependency-groups]\n"
        "dev = [\n"
        '  "ruff>=0.11",\n'
        "]\n"
    )
    (tmp_path / "pyproject.toml").write_text(content)
    result = audit.audit_python(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"
    assert result["exact_pins"]["loose"] == ["ruff>=0.11"]


def test_loose_dep_in_optional_dependencies_flagged(tmp_path):
    content = (
        "[project.optional-dependencies]\n"
        'test = ["pytest~=8.0"]\n'
    )
    (tmp_path / "pyproject.toml").write_text(content)
    result = audit.audit_python(str(tmp_path))
    assert result["exact_pins"]["loose"] == ["pytest~=8.0"]


def test_extras_bracket_does_not_end_array(tmp_path):
    content = (
        "[project]\n"
        "dependencies = [\n"
        '  "requests[socks]==2.31.0",\n'
        '  "httpx>=0.25.0",\n'
        "]\n"
    )
    (tmp_path / "pyproject.toml").write_text(content)
    result = audit.audit_python(str(tmp_path))
    assert result["exact_pins"]["loose"] == ["httpx>=0.25.0"]


def test_requires_python_still_not_flagged_with_new_parser(tmp_path):
    content = (
        "[project]\n"
        'requires-python = ">=3.10,<3.15"\n'
        'dependencies = ["requests==2.31.0"]\n'
    )
    (tmp_path / "pyproject.toml").write_text(content)
    result = audit.audit_python(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"


# ---------------------------------------------------------------------------
# CI frozen install — three-state (lfreleng-actions feedback)
# ---------------------------------------------------------------------------

def test_no_install_commands_warns_with_note(tmp_path):
    # Installs delegated to a SHA-pinned composite action are invisible to
    # file-based scanning — that's a warn with an explanation, not a fail.
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / "pyproject.toml").write_text("[tool.uv]\n")
    make_workflow(tmp_path, "ci.yml", "steps:\n  - uses: lfreleng-actions/python-test-action@abc123 # v1\n")
    result = audit.audit_python(str(tmp_path))
    assert result["ci_frozen_install"]["status"] == "warn"
    assert "composite actions" in result["ci_frozen_install"]["note"]


def test_unfrozen_uv_sync_fails_and_lists_workflow(tmp_path):
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / "pyproject.toml").write_text("[tool.uv]\n")
    make_workflow(tmp_path, "functional-tests.yaml", "steps:\n  - run: uv sync --all-extras\n")
    result = audit.audit_python(str(tmp_path))
    assert result["ci_frozen_install"]["status"] == "fail"
    assert result["ci_frozen_install"]["unfrozen_in"] == ["functional-tests.yaml"]


def test_frozen_and_unfrozen_mix_fails(tmp_path):
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / "pyproject.toml").write_text("[tool.uv]\n")
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: uv sync --frozen\n")
    make_workflow(tmp_path, "tests.yml", "steps:\n  - run: uv sync --all-extras\n")
    result = audit.audit_python(str(tmp_path))
    assert result["ci_frozen_install"]["status"] == "fail"
    assert result["ci_frozen_install"]["found_in"] == ["ci.yml"]
    assert result["ci_frozen_install"]["unfrozen_in"] == ["tests.yml"]


def test_commented_install_line_ignored(tmp_path):
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / "pyproject.toml").write_text("[tool.uv]\n")
    make_workflow(tmp_path, "ci.yml", "steps:\n  # - run: uv sync --all-extras\n  - run: uv sync --frozen\n")
    result = audit.audit_python(str(tmp_path))
    assert result["ci_frozen_install"]["status"] == "pass"
