# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""
Property-based fuzz tests for the audit script.

Uses Hypothesis to generate adversarial inputs for the per-ecosystem audit
functions and the parsing helpers. The contract under test is simple but
important: no audit function should ever raise an unhandled exception,
regardless of the contents of the manifests, lockfiles, or workflows it
encounters in a target repository.

This catches:
  - Regex catastrophic backtracking (ReDoS) in the helpers
  - Encoding / decoding issues in `read()`
  - Crashes on malformed YAML, TOML, JSON, or workflow files
  - Crashes on empty / huge / null-byte-laden inputs

Satisfies OpenSSF Scorecard's "Fuzzing" check (recognises Hypothesis as a
fuzzing tool for Python projects).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "harden-packages"))

import audit  # noqa: E402  (path injection above)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Reasonably-sized text blobs that include the kinds of bytes we expect to
# trip up regex and encoding paths: nulls, unicode, very long lines, etc.
adversarial_text = st.text(
    alphabet=st.characters(blacklist_categories=()),  # full unicode incl. control chars
    min_size=0,
    max_size=4096,
)

# Filenames the audit functions look for, plus arbitrary names to make sure
# extra files don't perturb behaviour.
manifest_names = st.sampled_from(
    [
        "package.json",
        "pnpm-workspace.yaml",
        ".npmrc",
        "pyproject.toml",
        "uv.lock",
        "requirements.txt",
        "go.mod",
        "Cargo.toml",
        "Cargo.lock",
        "composer.json",
        "composer.lock",
        "Gemfile",
        "Gemfile.lock",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "main.tf",
        "versions.tf",
        ".terraform.lock.hcl",
        ".github/dependabot.yml",
        ".github/workflows/ci.yml",
        ".github/workflows/release.yml",
    ]
)


@st.composite
def synthetic_repo(draw, tmp_path_factory):
    """Build a tmp directory populated with random manifest files."""
    root = tmp_path_factory.mktemp("fuzz_repo")
    files = draw(
        st.lists(
            st.tuples(manifest_names, adversarial_text),
            min_size=0,
            max_size=8,
            unique_by=lambda t: t[0],
        )
    )
    for name, content in files:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(content, encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            # Some inputs (e.g. embedded NULs on certain filesystems) can
            # fail to write — skip them, the audit script handles missing
            # files via its `read()` helper anyway.
            pass
    return root


# ---------------------------------------------------------------------------
# Helper-level properties
# ---------------------------------------------------------------------------


@given(content=adversarial_text, pattern=st.sampled_from([
    r"version\s*=\s*\"([^\"]+)\"",
    r"^\s*([A-Za-z0-9_-]+)\s*=",
    r"\$\{\{\s*[^}]+\s*\}\}",
    r"#\s*v\d+\.\d+\.\d+",
]))
@settings(max_examples=200, deadline=500)
def test_grep_never_raises(content, pattern):
    """audit.grep must return a bool for any input; never raise, never hang."""
    result = audit.grep(content, pattern)
    assert isinstance(result, bool)


@given(content=adversarial_text)
@settings(max_examples=200, deadline=500)
def test_find_value_never_raises(content):
    """audit.find_value must return str|None for any input; never raise."""
    result = audit.find_value(content, r"version\s*=\s*\"([^\"]+)\"")
    assert result is None or isinstance(result, str)


@given(name=st.text(min_size=0, max_size=200))
@settings(
    max_examples=100,
    deadline=500,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_is_gitignored_never_raises(tmp_path, name):
    """audit.is_gitignored handles arbitrary names without crashing."""
    (tmp_path / ".gitignore").write_text("node_modules\n*.pyc\n")
    result = audit.is_gitignored(str(tmp_path), name)
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Audit-function-level properties
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "audit_fn",
    [
        audit.audit_nodejs,
        audit.audit_python,
        audit.audit_go,
        audit.audit_rust,
        audit.audit_php,
        audit.audit_ruby,
        audit.audit_terraform,
        audit.audit_maven,
        audit.audit_gradle,
        audit.audit_harden_runner,
    ],
)
@given(content=adversarial_text, name=manifest_names)
@settings(
    max_examples=50,
    deadline=2000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_audit_function_never_crashes(tmp_path, audit_fn, content, name):
    """No per-ecosystem audit function should crash on adversarial manifests."""
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(content, encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        pytest.skip("filesystem rejected the generated content")
    # Result shape varies per function; we only assert no exception escapes.
    audit_fn(str(tmp_path))


@given(content=adversarial_text)
@settings(
    max_examples=50,
    deadline=2000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_audit_dependabot_never_crashes(tmp_path, content):
    """audit_dependabot must handle arbitrary dependabot.yml content."""
    db = tmp_path / ".github" / "dependabot.yml"
    db.parent.mkdir(parents=True, exist_ok=True)
    try:
        db.write_text(content, encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        pytest.skip("filesystem rejected the generated content")
    audit.audit_dependabot(str(tmp_path), [])


@given(content=adversarial_text)
@settings(
    max_examples=50,
    deadline=2000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_detect_ecosystems_never_crashes(tmp_path, content):
    """detect_ecosystems must handle arbitrary marker-file content."""
    for marker in ["package.json", "pyproject.toml", "go.mod", "Cargo.toml"]:
        try:
            (tmp_path / marker).write_text(content, encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass
    result = audit.detect_ecosystems(str(tmp_path))
    assert isinstance(result, list)
