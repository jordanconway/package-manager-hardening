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
    (tmp_path / ".npmrc").write_text("min-release-age=7\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["configured"] is True
    assert result["minimum_release_age"]["min-release-age"] == "7"


def test_npm_mra_pnpm_spelling_is_not_configured(tmp_path):
    """`minimum-release-age` is not an npm key: npm warns and applies no gate."""
    make_pkg(tmp_path)
    (tmp_path / ".npmrc").write_text("minimum-release-age=10080\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["configured"] is False
    assert "min-release-age" in result["minimum_release_age"]["unsupported_key"]


def test_npm_mra_exclude_key_alone_is_not_configured(tmp_path):
    make_pkg(tmp_path)
    (tmp_path / ".npmrc").write_text("min-release-age-exclude=typescript\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["configured"] is False


def test_npm_mra_missing(tmp_path):
    make_pkg(tmp_path)
    (tmp_path / ".npmrc").write_text("registry=https://registry.npmjs.org\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["configured"] is False


def test_pnpm_mra_configured(tmp_path):
    make_pkg(tmp_path, pkg_manager="pnpm@8.0.0")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    (tmp_path / "pnpm-workspace.yaml").write_text("minimumReleaseAge: 10080  # 7 days\ntrustPolicy: never\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["configured"] is True
    assert result["minimum_release_age"]["minimumReleaseAge"] == "10080"


def test_pnpm_mra_duration_string_is_not_configured(tmp_path):
    """pnpm takes minutes; a duration string is not a valid value on any release."""
    make_pkg(tmp_path, pkg_manager="pnpm@8.0.0")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    (tmp_path / "pnpm-workspace.yaml").write_text("minimumReleaseAge: '7 days'\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["configured"] is False
    assert result["minimum_release_age"]["minimumReleaseAge"] == "7 days"
    assert "minutes" in result["minimum_release_age"]["invalid_value"]


def test_pnpm_mra_exclude_key_alone_is_not_configured(tmp_path):
    make_pkg(tmp_path, pkg_manager="pnpm@8.0.0")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    (tmp_path / "pnpm-workspace.yaml").write_text("minimumReleaseAgeExclude:\n  - typescript\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["configured"] is False


def test_yarn_mra_configured(tmp_path):
    make_pkg(tmp_path, pkg_manager="yarn@4.0.0")
    (tmp_path / "yarn.lock").write_text("")
    (tmp_path / ".yarnrc.yml").write_text("npmMinimalAgeGate: 10080\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["configured"] is True


def test_yarn_mra_duration_string_configured(tmp_path):
    """Yarn >= 4.11 accepts duration strings such as "7d"."""
    make_pkg(tmp_path, pkg_manager="yarn@4.11.0")
    (tmp_path / "yarn.lock").write_text("")
    (tmp_path / ".yarnrc.yml").write_text('npmMinimalAgeGate: "7d"\n')
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["configured"] is True
    assert result["minimum_release_age"]["npmMinimalAgeGate"] == "7d"


def test_yarn_mra_zero_is_not_configured(tmp_path):
    make_pkg(tmp_path, pkg_manager="yarn@4.11.0")
    (tmp_path / "yarn.lock").write_text("")
    (tmp_path / ".yarnrc.yml").write_text("npmMinimalAgeGate: 0\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["configured"] is False


def test_bun_mra_configured(tmp_path):
    make_pkg(tmp_path, pkg_manager="bun@1.0.0")
    (tmp_path / "bun.lock").write_text("")
    (tmp_path / "bunfig.toml").write_text("[install]\nminimumReleaseAge = 604800\nexact = true\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["configured"] is True
    # The captured value must stop at the end of the line.
    assert result["minimum_release_age"]["minimumReleaseAge"] == "604800"
    assert "requires" not in result["minimum_release_age"]


def test_bun_mra_duration_string_flags_version_requirement(tmp_path):
    """Strings are only accepted from Bun 1.4.4; older releases reject the bunfig."""
    make_pkg(tmp_path, pkg_manager="bun@1.0.0")
    (tmp_path / "bun.lock").write_text("")
    (tmp_path / "bunfig.toml").write_text('[install]\nminimumReleaseAge = "7d"\n')
    result = audit.audit_nodejs(str(tmp_path))
    assert result["minimum_release_age"]["configured"] is True
    assert result["minimum_release_age"]["minimumReleaseAge"] == "7d"
    assert "1.4.4" in result["minimum_release_age"]["requires"]


# ---------------------------------------------------------------------------
# Build script control
# ---------------------------------------------------------------------------

def test_pnpm_build_script_control_allow_builds(tmp_path):
    make_pkg(tmp_path, pkg_manager="pnpm@11.0.0")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    (tmp_path / "pnpm-workspace.yaml").write_text("allowBuilds:\n  esbuild: true\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["build_script_control"]["status"] == "pass"


def test_pnpm_build_script_control_legacy_keys_warn(tmp_path):
    """pnpm 11 removed onlyBuiltDependencies; it only still works on pnpm 10."""
    make_pkg(tmp_path, pkg_manager="pnpm@8.0.0")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    (tmp_path / "pnpm-workspace.yaml").write_text("onlyBuiltDependencies:\n  - esbuild\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["build_script_control"]["status"] == "warn"
    assert "allowBuilds" in result["build_script_control"]["note"]


def test_pnpm_build_script_control_missing(tmp_path):
    make_pkg(tmp_path, pkg_manager="pnpm@8.0.0")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - '.'\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["build_script_control"]["status"] == "fail"


def test_bun_ignore_scripts_true(tmp_path):
    make_pkg(tmp_path, pkg_manager="bun@1.0.0")
    (tmp_path / "bun.lock").write_text("")
    (tmp_path / "bunfig.toml").write_text("[install]\nignoreScripts = true\n")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["build_script_control"]["status"] == "pass"
    assert result["build_script_control"]["ignoreScripts"] is True


def test_bun_trusted_dependencies_in_package_json(tmp_path):
    """An explicit package.json list replaces Bun's default-trusted list."""
    (tmp_path / "package.json").write_text(
        json.dumps({"packageManager": "bun@1.0.0", "trustedDependencies": ["esbuild"]})
    )
    (tmp_path / "bun.lock").write_text("")
    result = audit.audit_nodejs(str(tmp_path))
    assert result["build_script_control"]["status"] == "pass"
    assert result["build_script_control"]["trustedDependencies"] is True


def test_bun_unsupported_bunfig_keys_do_not_pass(tmp_path):
    """Bun reads neither `lifecycleScripts` nor a bunfig trustedDependencies table."""
    make_pkg(tmp_path, pkg_manager="bun@1.0.0")
    (tmp_path / "bun.lock").write_text("")
    (tmp_path / "bunfig.toml").write_text(
        '[install]\nlifecycleScripts = false\n\n[install.trustedDependencies]\npackages = ["esbuild"]\n'
    )
    result = audit.audit_nodejs(str(tmp_path))
    assert result["build_script_control"]["status"] == "fail"
    assert result["build_script_control"]["unsupported_bunfig_keys"] == [
        "lifecycleScripts",
        "[install.trustedDependencies]",
    ]


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
