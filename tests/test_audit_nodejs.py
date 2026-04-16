# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Unit tests for audit_nodejs()."""

import json

import pytest

import audit
from conftest import make_workflow, write_file


def make_pkg(tmp_path, deps=None, dev_deps=None, pkg_manager=""):
    data = {}
    if deps:
        data["dependencies"] = deps
    if dev_deps:
        data["devDependencies"] = dev_deps
    if pkg_manager:
        data["packageManager"] = pkg_manager
    (tmp_path / "package.json").write_text(json.dumps(data))


# ---------------------------------------------------------------------------
# Manager detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lockfile,expected_manager", [
    ("package-lock.json", "npm"),
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lock", "bun"),
])
def test_manager_detected_from_lockfile(tmp_path, lockfile, expected_manager):
    make_pkg(tmp_path)
    (tmp_path / lockfile).write_text("")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["manager"] == expected_manager


def test_package_manager_field_overrides_lockfile(tmp_path):
    make_pkg(tmp_path, pkg_manager="pnpm@8.0.0")
    (tmp_path / "package-lock.json").write_text("")  # npm lockfile present
    result = audit.audit_nodejs(str(tmp_path))
    assert result["manager"] == "pnpm"


def test_manager_defaults_to_npm_when_no_lockfile(tmp_path):
    make_pkg(tmp_path)
    result = audit.audit_nodejs(str(tmp_path))
    assert result["manager"] == "npm"


# ---------------------------------------------------------------------------
# Lockfile checks
# ---------------------------------------------------------------------------

def test_lockfile_present_passes(tmp_path):
    make_pkg(tmp_path)
    (tmp_path / "package-lock.json").write_text("")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["lockfile"]["status"] == "pass"
    assert result["lockfile"]["file"] == "package-lock.json"


def test_lockfile_missing_fails(tmp_path):
    make_pkg(tmp_path)
    result = audit.audit_nodejs(str(tmp_path))
    assert result["lockfile"]["status"] == "fail"


def test_lockfile_gitignored_flagged(tmp_path):
    make_pkg(tmp_path)
    (tmp_path / "package-lock.json").write_text("")
    (tmp_path / ".gitignore").write_text("package-lock.json\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["lockfile"]["gitignored"] is True


# ---------------------------------------------------------------------------
# Exact version pins
# ---------------------------------------------------------------------------

def test_exact_pins_all_exact(tmp_path):
    make_pkg(tmp_path, deps={"lodash": "4.17.21", "axios": "1.6.0"})
    result = audit.audit_nodejs(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"
    assert result["exact_pins"]["unpinned_count"] == 0


def test_exact_pins_caret_detected(tmp_path):
    make_pkg(tmp_path, deps={"lodash": "^4.17.21"})
    result = audit.audit_nodejs(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"
    assert result["exact_pins"]["unpinned_count"] == 1


def test_exact_pins_tilde_detected(tmp_path):
    make_pkg(tmp_path, deps={"lodash": "~4.17.21"})
    result = audit.audit_nodejs(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"


def test_exact_pins_latest_detected(tmp_path):
    make_pkg(tmp_path, deps={"lodash": "latest"})
    result = audit.audit_nodejs(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"


def test_exact_pins_dev_deps_checked(tmp_path):
    make_pkg(tmp_path, dev_deps={"jest": "^29.0.0"})
    result = audit.audit_nodejs(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"


# ---------------------------------------------------------------------------
# Minimum release age
# ---------------------------------------------------------------------------

def test_npm_mra_configured(tmp_path):
    make_pkg(tmp_path)
    (tmp_path / ".npmrc").write_text("minimum-release-age=10080\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["status"] == "pass"
    assert result["minimum_release_age"]["minimum-release-age"] == "10080"


def test_npm_mra_missing(tmp_path):
    make_pkg(tmp_path)
    (tmp_path / ".npmrc").write_text("registry=https://registry.npmjs.org\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["status"] == "fail"


def test_pnpm_mra_configured(tmp_path):
    make_pkg(tmp_path, pkg_manager="pnpm@8.0.0")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    (tmp_path / "pnpm-workspace.yaml").write_text("minimumReleaseAge: '7 days'\ntrustPolicy: never\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["status"] == "pass"


def test_yarn_mra_configured(tmp_path):
    make_pkg(tmp_path, pkg_manager="yarn@4.0.0")
    (tmp_path / "yarn.lock").write_text("")
    (tmp_path / ".yarnrc.yml").write_text("npmMinimalAgeGate: 10080\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["status"] == "pass"


def test_bun_mra_configured(tmp_path):
    make_pkg(tmp_path, pkg_manager="bun@1.0.0")
    (tmp_path / "bun.lock").write_text("")
    (tmp_path / "bunfig.toml").write_text('minimumReleaseAge = "10080m"\n')
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["status"] == "pass"


# ---------------------------------------------------------------------------
# Build script control
# ---------------------------------------------------------------------------

def test_pnpm_build_script_control_only_built(tmp_path):
    make_pkg(tmp_path, pkg_manager="pnpm@8.0.0")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    (tmp_path / "pnpm-workspace.yaml").write_text("onlyBuiltDependencies:\n  - esbuild\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["build_script_control"]["status"] == "pass"


def test_pnpm_build_script_control_missing(tmp_path):
    make_pkg(tmp_path, pkg_manager="pnpm@8.0.0")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - '.'\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["build_script_control"]["status"] == "fail"


def test_bun_lifecycle_scripts_false(tmp_path):
    make_pkg(tmp_path, pkg_manager="bun@1.0.0")
    (tmp_path / "bun.lock").write_text("")
    (tmp_path / "bunfig.toml").write_text("[install]\nlifecycleScripts = false\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["build_script_control"]["status"] == "pass"


def test_npm_build_script_control_na(tmp_path):
    make_pkg(tmp_path)
    result = audit.audit_nodejs(str(tmp_path))
    assert result["build_script_control"]["status"] == "n/a"


# ---------------------------------------------------------------------------
# CI frozen install
# ---------------------------------------------------------------------------

def test_npm_ci_frozen_install_found(tmp_path):
    make_pkg(tmp_path)
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: npm ci\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["ci_frozen_install"]["status"] == "pass"
    assert "ci.yml" in result["ci_frozen_install"]["found_in"]


def test_npm_ci_frozen_install_missing(tmp_path):
    make_pkg(tmp_path)
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: npm install\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["ci_frozen_install"]["status"] == "fail"


def test_pnpm_frozen_lockfile_found(tmp_path):
    make_pkg(tmp_path, pkg_manager="pnpm@8.0.0")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: pnpm install --frozen-lockfile\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["ci_frozen_install"]["status"] == "pass"


def test_yarn_immutable_found(tmp_path):
    make_pkg(tmp_path, pkg_manager="yarn@4.0.0")
    (tmp_path / "yarn.lock").write_text("")
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: yarn install --immutable\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["ci_frozen_install"]["status"] == "pass"
