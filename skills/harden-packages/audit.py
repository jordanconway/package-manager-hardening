# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""
audit.py — mechanical data-collection pass for the harden-packages skill.

Scans a repository for package manager configuration and emits a compact JSON
findings report to stdout. Intended to be invoked by Claude at the start of the
harden-packages skill to avoid repeated file reads during the audit phase.

Usage: python audit.py [--path /path/to/repo]

All checks are deterministic file/regex operations. Interpretation, prioritisation,
and fix application remain with the LLM.
"""

import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def exists(path):
    return Path(path).exists()


def is_gitignored(root, name):
    gi = Path(root) / ".gitignore"
    if not gi.exists():
        return False
    for line in read(gi).splitlines():
        line = line.strip()
        if line and not line.startswith("#") and name in line:
            return True
    return False


def glob_files(root, pattern):
    return list(Path(root).rglob(pattern))


def grep(content, pattern, flags=0):
    return bool(re.search(pattern, content, flags))


def find_value(content, key_pattern):
    """Return the first captured group from key_pattern in content, or None."""
    m = re.search(key_pattern, content)
    return m.group(1) if m else None


def workflow_files(root):
    wf_dir = Path(root) / ".github" / "workflows"
    if not wf_dir.is_dir():
        return {}
    result = {}
    for f in wf_dir.glob("*.yml"):
        result[f.name] = read(f)
    for f in wf_dir.glob("*.yaml"):
        result[f.name] = read(f)
    return result


def status(ok):
    return "pass" if ok else "fail"


# ---------------------------------------------------------------------------
# Ecosystem detectors
# ---------------------------------------------------------------------------


def detect_ecosystems(root):
    detected = []
    r = Path(root)

    if (r / "package.json").exists():
        detected.append("nodejs")
    if (r / "pyproject.toml").exists() or (r / "requirements.txt").exists():
        detected.append("python")
    if (r / "go.mod").exists():
        detected.append("go")
    if (r / "Cargo.toml").exists():
        detected.append("rust")
    if (r / "composer.json").exists():
        detected.append("php")
    if (r / "Gemfile").exists():
        detected.append("ruby")
    tf_files = list(r.rglob("*.tf"))
    if tf_files or (r / ".terraform.lock.hcl").exists():
        # Confirm at least one file looks like a terraform root
        for tf in tf_files:
            content = read(tf)
            if "required_providers" in content or re.search(r"^terraform\s*\{", content, re.MULTILINE):
                detected.append("terraform")
                break

    if (r / "pom.xml").exists():
        detected.append("maven")
    if (r / "build.gradle").exists() or (r / "build.gradle.kts").exists() \
            or (r / "settings.gradle").exists() or (r / "settings.gradle.kts").exists():
        detected.append("gradle")

    return detected


# ---------------------------------------------------------------------------
# Per-ecosystem audits
# ---------------------------------------------------------------------------


def audit_nodejs(root):
    r = Path(root)
    findings = {}

    # Detect lockfile and manager
    lockfile_map = {
        "pnpm-lock.yaml": "pnpm",
        "yarn.lock": "yarn",
        "bun.lock": "bun",
        "package-lock.json": "npm",
    }
    lockfile = None
    manager = None
    for fname, mgr in lockfile_map.items():
        if (r / fname).exists():
            lockfile = fname
            manager = mgr
            break

    # packageManager field can override manager detection
    pkg = {}
    try:
        import json as _json

        pkg = _json.loads(read(r / "package.json"))
    except Exception:
        pass
    pm_field = pkg.get("packageManager", "")
    if pm_field.startswith("pnpm"):
        manager = "pnpm"
    elif pm_field.startswith("yarn"):
        manager = "yarn"
    elif pm_field.startswith("bun"):
        manager = "bun"

    manager = manager or "npm"
    findings["manager"] = manager
    findings["lockfile"] = {
        "file": lockfile,
        "status": status(lockfile is not None),
        "gitignored": is_gitignored(root, lockfile) if lockfile else False,
    }

    # Exact version pins in package.json
    loose = []
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        for pkg_name, ver in pkg.get(section, {}).items():
            if re.search(r"[\^~>*]|latest", str(ver)):
                loose.append(f"{section}/{pkg_name}@{ver}")
    findings["exact_pins"] = {
        "status": status(len(loose) == 0),
        "unpinned": loose[:20],  # cap at 20 to keep JSON compact
        "unpinned_count": len(loose),
    }

    # Minimum release age
    mra = {}
    if manager == "pnpm":
        ws = read(r / "pnpm-workspace.yaml")
        age = find_value(ws, r'minimumReleaseAge[:\s]+["\']?([^\s"\']+)')
        trust = find_value(ws, r"trustPolicy[:\s]+([^\s\n]+)")
        mra["minimumReleaseAge"] = age
        mra["trustPolicy"] = trust
        mra["status"] = status(age is not None)
    elif manager == "npm":
        npmrc = read(r / ".npmrc")
        age = find_value(npmrc, r"minimum-release-age\s*=\s*(\d+)")
        mra["minimum-release-age"] = age
        mra["status"] = status(age is not None)
    elif manager == "yarn":
        yarnrc = read(r / ".yarnrc.yml")
        age = find_value(yarnrc, r"npmMinimalAgeGate[:\s]+(\d+)")
        mra["npmMinimalAgeGate"] = age
        mra["status"] = status(age is not None)
    elif manager == "bun":
        bunfig = read(r / "bunfig.toml")
        age = find_value(bunfig, r'minimumReleaseAge\s*=\s*["\']?([^"\'\\n]+)')
        mra["minimumReleaseAge"] = age
        mra["status"] = status(age is not None)
    else:
        mra["status"] = "unknown"
    findings["minimum_release_age"] = mra

    # Build script control
    bsc = {}
    if manager == "pnpm":
        ws = read(r / "pnpm-workspace.yaml")
        bsc["onlyBuiltDependencies"] = grep(ws, r"onlyBuiltDependencies")
        bsc["ignoredBuiltDependencies"] = grep(ws, r"ignoredBuiltDependencies")
        bsc["status"] = status(bsc["onlyBuiltDependencies"] or bsc["ignoredBuiltDependencies"])
    elif manager == "bun":
        bunfig = read(r / "bunfig.toml")
        bsc["lifecycleScripts_false"] = grep(bunfig, r"lifecycleScripts\s*=\s*false")
        bsc["trustedDependencies"] = grep(bunfig, r"trustedDependencies")
        bsc["status"] = status(bsc["lifecycleScripts_false"])
    else:
        bsc["status"] = "n/a"
    findings["build_script_control"] = bsc

    # CI frozen install
    ci_frozen_patterns = {
        "npm": r"npm ci\b",
        "pnpm": r"pnpm install.*--frozen-lockfile|--frozen-lockfile.*pnpm install",
        "yarn": r"yarn install.*--immutable|--immutable",
        "bun": r"bun install.*--frozen-lockfile|--frozen-lockfile",
    }
    wfs = workflow_files(root)
    pattern = ci_frozen_patterns.get(manager or "npm", r"npm ci\b")
    found_in = [name for name, content in wfs.items() if grep(content, pattern)]
    findings["ci_frozen_install"] = {
        "status": status(bool(found_in)),
        "found_in": found_in,
    }

    return findings


def audit_python(root):
    r = Path(root)
    findings = {}

    # Detect manager (uv vs pip)
    has_uv = (r / "uv.lock").exists() or (
        grep(read(r / "pyproject.toml"), r"\[tool\.uv\]") if (r / "pyproject.toml").exists() else False
    )
    manager = "uv" if has_uv else "pip"
    findings["manager"] = manager

    # Lockfile
    if manager == "uv":
        lf = (r / "uv.lock").exists()
        findings["lockfile"] = {
            "file": "uv.lock" if lf else None,
            "status": status(lf),
            "gitignored": is_gitignored(root, "uv.lock"),
        }
    else:
        rl = (r / "requirements.lock").exists()
        findings["lockfile"] = {
            "file": "requirements.lock" if rl else None,
            "status": status(rl),
            "note": "requirements.lock from pip-compile --generate-hashes expected",
        }

    # Exact pins in pyproject.toml
    if (r / "pyproject.toml").exists():
        content = read(r / "pyproject.toml")
        # Extract dependencies section lines
        loose = []
        in_deps = False
        for line in content.splitlines():
            if re.match(r"\[project\.dependencies\]|\[project\]", line):
                in_deps = True
            elif line.startswith("[") and in_deps:
                in_deps = False
            if in_deps or "dependencies" in line:
                # Look for lines that have package specs without ==
                m = re.search(r'"([^"]+[><=!~][^"]*)"', line)
                if m:
                    spec = m.group(1)
                    if not re.search(r"==", spec) and re.search(r"[><=~!]", spec):
                        loose.append(spec)
        findings["exact_pins"] = {
            "status": status(len(loose) == 0),
            "loose": loose[:20],
        }

    # UV-specific settings
    if manager == "uv":
        pyproject = read(r / "pyproject.toml") if (r / "pyproject.toml").exists() else ""
        exclude_newer = find_value(pyproject, r'exclude-newer\s*=\s*["\']?([^"\'\\n\]]+)')
        require_hashes = grep(pyproject, r"require-hashes\s*=\s*true")
        verify_hashes = grep(pyproject, r"verify-hashes\s*=\s*true")
        findings["uv_config"] = {
            "exclude_newer": exclude_newer.strip() if exclude_newer else None,
            "require_hashes": require_hashes,
            "verify_hashes": verify_hashes,
            "status": status(bool(exclude_newer) and require_hashes and verify_hashes),
        }

    # CI frozen install
    wfs = workflow_files(root)
    if manager == "uv":
        pattern = r"uv sync.*--frozen|--frozen.*uv sync"
    else:
        pattern = r"pip install.*--require-hashes"
    found_in = [name for name, content in wfs.items() if grep(content, pattern)]
    findings["ci_frozen_install"] = {
        "status": status(bool(found_in)),
        "found_in": found_in,
    }

    return findings


def audit_go(root):
    r = Path(root)
    findings = {}

    gomod = read(r / "go.mod")
    gosum_exists = (r / "go.sum").exists()

    findings["lockfile"] = {
        "go.mod": (r / "go.mod").exists(),
        "go.sum": gosum_exists,
        "go.sum_gitignored": is_gitignored(root, "go.sum"),
        "status": status(gosum_exists and not is_gitignored(root, "go.sum")),
    }

    # Check for @latest or @master references
    bad_refs = re.findall(r"^\s*require\s+\S+\s+\S*(?:@latest|@master|@main)", gomod, re.MULTILINE)
    # Also check indirect requires
    bad_refs += re.findall(r"@latest|@master|@main", gomod)
    findings["version_pins"] = {
        "status": status(len(bad_refs) == 0),
        "bad_refs": list(set(bad_refs)),
    }

    # GONOSUMDB / GONOSUMCHECK set to * (disabling all sum checks)
    wfs = workflow_files(root)
    all_wf = "\n".join(wfs.values())
    gonosumdb_all = grep(all_wf, r"GONOSUMDB\s*[=:]\s*['\"]?\*['\"]?|GONOSUMCHECK\s*[=:]\s*['\"]?\*['\"]?")
    findings["sum_database"] = {
        "status": status(not gonosumdb_all),
        "gonosumdb_wildcard": gonosumdb_all,
    }

    # CI checks
    has_verify = any(grep(c, r"go mod verify") for c in wfs.values())
    tidy_pattern = r"git diff.*go\.(mod|sum)|go\.(mod|sum).*git diff"
    has_tidy_check = any(grep(c, r"go mod tidy") and grep(c, tidy_pattern) for c in wfs.values())
    has_govulncheck = any(grep(c, r"govulncheck") for c in wfs.values())
    findings["ci"] = {
        "go_mod_verify": has_verify,
        "tidy_diff_check": has_tidy_check,
        "govulncheck": has_govulncheck,
        "status": status(has_verify and has_govulncheck),
    }

    return findings


def audit_rust(root):
    r = Path(root)
    findings = {}

    cargo_lock = (r / "Cargo.lock").exists()
    findings["lockfile"] = {
        "file": "Cargo.lock" if cargo_lock else None,
        "status": status(cargo_lock),
        "gitignored": is_gitignored(root, "Cargo.lock"),
    }

    # Exact version pins (= prefix)
    cargo_toml = read(r / "Cargo.toml")
    # Strip [package] and [workspace] sections to avoid false positives on package metadata
    dep_content = re.sub(r"^\[(package|workspace)\][^\[]*", "", cargo_toml, flags=re.MULTILINE | re.DOTALL)
    # Look for dependency entries without = prefix
    loose = re.findall(r'^\s*\w[\w-]*\s*=\s*["\'](?!=)([0-9^~><=*][^"\']*)["\']', dep_content, re.MULTILINE)
    # Also table-form deps
    loose += re.findall(r'version\s*=\s*["\'](?!=)([^"\']+)["\']', dep_content)
    findings["exact_pins"] = {
        "status": status(len(loose) == 0),
        "loose": loose[:20],
        "loose_count": len(loose),
    }

    # cargo-cooldown config
    config_toml = read(r / ".cargo" / "config.toml")
    cooldown_days = find_value(config_toml, r"\[cooldown\].*?days\s*=\s*(\d+)")
    if not cooldown_days:
        cooldown_days = find_value(config_toml, r"days\s*=\s*(\d+)")
    has_cooldown_section = grep(config_toml, r"\[cooldown\]")
    findings["cooldown"] = {
        "status": status(has_cooldown_section and cooldown_days is not None),
        "days": cooldown_days,
    }

    # CI
    wfs = workflow_files(root)
    has_locked = any(grep(c, r"--locked") for c in wfs.values())
    has_audit = any(grep(c, r"cargo audit") for c in wfs.values())
    findings["ci"] = {
        "locked_flag": has_locked,
        "cargo_audit": has_audit,
        "status": status(has_locked and has_audit),
    }

    return findings


def audit_php(root):
    r = Path(root)
    findings = {}

    lock_exists = (r / "composer.lock").exists()
    findings["lockfile"] = {
        "file": "composer.lock" if lock_exists else None,
        "status": status(lock_exists),
        "gitignored": is_gitignored(root, "composer.lock"),
    }

    # Exact pins in composer.json
    composer_json = {}
    try:
        import json as _json

        composer_json = _json.loads(read(r / "composer.json"))
    except Exception:
        pass

    loose = []
    for section in ("require", "require-dev"):
        for pkg_name, ver in composer_json.get(section, {}).items():
            if pkg_name == "php":
                continue
            if re.search(r"[\^~>*]|\|\|", str(ver)):
                loose.append(f"{section}/{pkg_name}:{ver}")
    findings["exact_pins"] = {
        "status": status(len(loose) == 0),
        "loose": loose[:20],
        "loose_count": len(loose),
    }

    # roave/security-advisories
    has_roave = "roave/security-advisories" in composer_json.get("require-dev", {})
    findings["roave_security_advisories"] = {
        "status": status(has_roave),
        "present": has_roave,
    }

    # CI patterns
    wfs = workflow_files(root)
    all_wf = "\n".join(wfs.values())
    has_no_scripts = grep(all_wf, r"--no-scripts")
    has_no_plugins = grep(all_wf, r"--no-plugins")
    has_prefer_dist = grep(all_wf, r"--prefer-dist")
    has_no_interaction = grep(all_wf, r"COMPOSER_NO_INTERACTION")
    has_audit = grep(all_wf, r"composer audit")
    has_install_not_update = grep(all_wf, r"composer install") and not grep(all_wf, r"composer update")
    findings["ci"] = {
        "no_scripts": has_no_scripts,
        "no_plugins": has_no_plugins,
        "prefer_dist": has_prefer_dist,
        "no_interaction": has_no_interaction,
        "composer_audit": has_audit,
        "install_not_update": has_install_not_update,
        "status": status(has_no_scripts and has_no_plugins and has_audit and has_no_interaction),
    }

    return findings


def audit_ruby(root):
    r = Path(root)
    findings = {}

    lock_exists = (r / "Gemfile.lock").exists()
    findings["lockfile"] = {
        "file": "Gemfile.lock" if lock_exists else None,
        "status": status(lock_exists),
        "gitignored": is_gitignored(root, "Gemfile.lock"),
    }

    # Exact pins in Gemfile
    gemfile = read(r / "Gemfile")
    loose = []
    for line in gemfile.splitlines():
        # Match gem declarations with version constraints
        m = re.match(r"""\s*gem\s+['"]([^'"]+)['"]\s*,\s*['"]([^'"]+)['"]""", line)
        if m:
            ver = m.group(2)
            if re.search(r"[~>]|>=|!=", ver):
                loose.append(f"{m.group(1)}: {ver}")
    findings["exact_pins"] = {
        "status": status(len(loose) == 0),
        "loose": loose[:20],
        "loose_count": len(loose),
    }

    # Ruby version pinning
    has_ruby_directive = grep(gemfile, r"^\s*ruby\s+['\"]", re.MULTILINE)
    has_ruby_version_file = (r / ".ruby-version").exists()
    findings["ruby_version"] = {
        "gemfile_directive": has_ruby_directive,
        "ruby_version_file": has_ruby_version_file,
        "status": status(has_ruby_directive or has_ruby_version_file),
    }

    # CI patterns
    wfs = workflow_files(root)
    all_wf = "\n".join(wfs.values())
    has_frozen = grep(all_wf, r"BUNDLE_FROZEN|bundle config.*frozen")
    has_audit = grep(all_wf, r"bundle audit|bundler-audit")
    has_install_not_update = grep(all_wf, r"bundle install") and not grep(all_wf, r"bundle update")
    findings["ci"] = {
        "bundle_frozen": has_frozen,
        "bundle_audit": has_audit,
        "install_not_update": has_install_not_update,
        "status": status(has_frozen and has_audit),
    }

    return findings


def audit_terraform(root):
    r = Path(root)
    findings = {}

    # Find all root modules (directories containing .tf files)
    tf_files = list(r.rglob("*.tf"))
    tf_dirs = list({f.parent for f in tf_files})

    # Lockfile per root module
    lockfile_status = {}
    for d in tf_dirs:
        lf = d / ".terraform.lock.hcl"
        rel = str(d.relative_to(r)) if d != r else "."
        lockfile_status[rel] = {
            "present": lf.exists(),
            "gitignored": is_gitignored(root, ".terraform.lock.hcl"),
        }
    findings["lockfile"] = {
        "modules": lockfile_status,
        "status": status(all(v["present"] for v in lockfile_status.values())),
    }

    # Version pins in .tf files
    loose_providers = []
    for tf in tf_files:
        content = read(tf)
        # Find version constraints in required_providers that aren't exact
        for m in re.finditer(r'version\s*=\s*"([^"]+)"', content):
            ver = m.group(1)
            if not re.match(r"^\s*=\s*\d", ver):
                loose_providers.append(f"{tf.name}: {ver}")
    findings["exact_pins"] = {
        "status": status(len(loose_providers) == 0),
        "loose": loose_providers[:20],
        "loose_count": len(loose_providers),
    }

    # Detect cli (terraform vs tofu)
    wfs = workflow_files(root)
    all_wf = "\n".join(wfs.values())
    uses_tofu = grep(all_wf, r"\btofu\b") or any(
        grep(read(r / f), r"opentofu") for f in [".tool-versions", ".terraform-version"] if (r / f).exists()
    )
    findings["cli"] = "tofu" if uses_tofu else "terraform"

    # -lockfile=readonly
    has_readonly = grep(all_wf, r"-lockfile=readonly")
    findings["lockfile_readonly"] = {
        "status": status(has_readonly),
        "found": has_readonly,
    }

    # OpenTofu specifics
    if uses_tofu:
        has_encryption = any(grep(read(tf), r"encryption\s*\{") for tf in tf_files)
        findings["opentofu"] = {
            "state_encryption": has_encryption,
            "status": status(has_encryption),
        }

    return findings


# ---------------------------------------------------------------------------
# JVM audits — Maven and Gradle are detected and audited separately because
# they have distinct Dependabot ecosystem keys and entirely different finding
# shapes. The user-facing skill documentation refers to both under the "JVM"
# umbrella.
# ---------------------------------------------------------------------------


def audit_maven(root):
    r = Path(root)
    findings = {}

    pom = read(r / "pom.xml")
    findings["pom_xml"] = {"present": bool(pom)}

    # Detect loose / mutable version constraints in <version> elements
    loose = []
    for m in re.finditer(r"<version>([^<]+)</version>", pom):
        ver = m.group(1).strip()
        # Skip property placeholders (${...}) — they're resolved elsewhere
        if ver.startswith("${"):
            continue
        bad = False
        # Ranges
        if ver.startswith("[") or ver.startswith("("):
            bad = True
        # Dynamic keywords
        if ver in ("LATEST", "RELEASE"):
            bad = True
        # SNAPSHOTs (mutable)
        if ver.endswith("-SNAPSHOT") or "SNAPSHOT" in ver:
            bad = True
        if bad:
            loose.append(ver)
    findings["exact_pins"] = {
        "status": status(len(loose) == 0),
        "loose": loose[:20],
        "loose_count": len(loose),
    }

    # maven-enforcer-plugin with the canonical hardening rules
    has_enforcer = "maven-enforcer-plugin" in pom
    ban_dynamic = bool(re.search(r"<banDynamicVersions\s*/?>", pom))
    require_plugin_versions = bool(re.search(r"<requirePluginVersions\b", pom))
    require_release_deps = bool(re.search(r"<requireReleaseDeps\b", pom))
    dependency_convergence = bool(re.search(r"<dependencyConvergence\s*/?>", pom))
    rules_present = sum(
        [ban_dynamic, require_plugin_versions, require_release_deps, dependency_convergence]
    )
    findings["enforcer_plugin"] = {
        "present": has_enforcer,
        "ban_dynamic_versions": ban_dynamic,
        "require_plugin_versions": require_plugin_versions,
        "require_release_deps": require_release_deps,
        "dependency_convergence": dependency_convergence,
        "status": status(has_enforcer and rules_present >= 2),
    }

    # Checksum policy — look for <checksumPolicy>fail</checksumPolicy> in pom or
    # for --strict-checksums / -C in CI workflows.
    wfs = workflow_files(root)
    all_wf = "\n".join(wfs.values())
    strict_in_pom = "fail" in re.findall(
        r"<checksumPolicy>([^<]+)</checksumPolicy>", pom
    )
    strict_in_ci = grep(all_wf, r"--strict-checksums|\s-C\b")
    findings["strict_checksums"] = {
        "in_pom": strict_in_pom,
        "in_ci": strict_in_ci,
        "status": status(strict_in_pom or strict_in_ci),
    }

    # SCA scanner — at least one of OWASP Dependency-Check, CycloneDX, OSS Index
    has_dependency_check = "dependency-check-maven" in pom
    has_cyclonedx = "cyclonedx-maven-plugin" in pom
    has_ossindex = "ossindex-maven-plugin" in pom
    findings["sca_scanner"] = {
        "owasp_dependency_check": has_dependency_check,
        "cyclonedx": has_cyclonedx,
        "ossindex": has_ossindex,
        "status": status(has_dependency_check or has_cyclonedx or has_ossindex),
    }

    # CI invokes maven with --batch-mode (deterministic, fail-fast)
    has_batch_mode = grep(all_wf, r"--batch-mode|\s-B\b")
    findings["ci"] = {
        "batch_mode": has_batch_mode,
        "strict_checksums": strict_in_ci,
        "status": status(has_batch_mode and (strict_in_pom or strict_in_ci)),
    }

    return findings


def audit_gradle(root):
    r = Path(root)
    findings = {}

    # Gather all build script content
    build_files = []
    for name in ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"):
        if (r / name).exists():
            build_files.append(r / name)
    build_files += [p for p in r.rglob("build.gradle") if p not in build_files]
    build_files += [p for p in r.rglob("build.gradle.kts") if p not in build_files]
    build_content = "\n".join(read(p) for p in build_files)

    findings["build_files"] = [str(p.relative_to(r)) for p in build_files][:20]

    # Detect dynamic versions in dependency strings
    loose = []
    # "group:name:1.+" / "group:name:latest.release" / "group:name:[1.0,2.0)"
    for m in re.finditer(r'["\']([\w.\-]+):([\w.\-]+):([^"\']+)["\']', build_content):
        ver = m.group(3)
        if (
            "+" in ver
            or "latest" in ver.lower()
            or ver.startswith("[")
            or ver.startswith("(")
            or "SNAPSHOT" in ver
        ):
            loose.append(f"{m.group(1)}:{m.group(2)}:{ver}")
    findings["exact_pins"] = {
        "status": status(len(loose) == 0),
        "loose": loose[:20],
        "loose_count": len(loose),
    }

    # Dependency locking
    has_locking_block = grep(build_content, r"dependencyLocking\s*\{")
    lock_all = grep(build_content, r"lockAllConfigurations\s*\(")
    strict_mode = grep(build_content, r"LockMode\.STRICT|lockMode\.set\(\s*LockMode\.STRICT")
    lockfiles = list(r.rglob("gradle.lockfile"))
    findings["dependency_locking"] = {
        "configured": has_locking_block,
        "lock_all_configurations": lock_all,
        "strict_mode": strict_mode,
        "lockfile_count": len(lockfiles),
        "status": status(has_locking_block and lock_all and bool(lockfiles)),
    }

    # Dependency verification (gradle/verification-metadata.xml)
    vm = r / "gradle" / "verification-metadata.xml"
    vm_content = read(vm)
    verify_metadata = "verify-metadata>true" in vm_content
    verify_signatures = "verify-signatures>true" in vm_content
    findings["dependency_verification"] = {
        "file_present": vm.exists(),
        "verify_metadata": verify_metadata,
        "verify_signatures": verify_signatures,
        "status": status(vm.exists() and verify_metadata),
    }

    # Gradle Wrapper SHA pinning
    wrapper_props = read(r / "gradle" / "wrapper" / "gradle-wrapper.properties")
    has_sha = bool(re.search(r"^distributionSha256Sum\s*=", wrapper_props, re.MULTILINE))
    findings["wrapper"] = {
        "properties_present": bool(wrapper_props),
        "distribution_sha256": has_sha,
        "status": status(bool(wrapper_props) and has_sha),
    }

    # Repository control
    fail_on_project_repos = grep(build_content, r"FAIL_ON_PROJECT_REPOS")
    uses_maven_local = grep(build_content, r"mavenLocal\s*\(")
    uses_jcenter = grep(build_content, r"jcenter\s*\(")
    findings["repository_control"] = {
        "fail_on_project_repos": fail_on_project_repos,
        "uses_mavenLocal": uses_maven_local,
        "uses_jcenter": uses_jcenter,
        "status": status(
            fail_on_project_repos and not uses_maven_local and not uses_jcenter
        ),
    }

    # Reproducible resolution (rejects dynamic/changing/mutable)
    rejects_dynamic = grep(build_content, r"failOnNonReproducibleResolution|failOnDynamicVersions")
    findings["reject_dynamic"] = {
        "status": status(rejects_dynamic),
        "configured": rejects_dynamic,
    }

    # SCA plugin
    has_dependency_check = "org.owasp.dependencycheck" in build_content
    has_cyclonedx = "org.cyclonedx.bom" in build_content
    has_snyk = "io.snyk.gradle.plugin" in build_content
    findings["sca_scanner"] = {
        "owasp_dependency_check": has_dependency_check,
        "cyclonedx": has_cyclonedx,
        "snyk": has_snyk,
        "status": status(has_dependency_check or has_cyclonedx or has_snyk),
    }

    # CI uses ./gradlew (not system gradle) and --no-daemon
    wfs = workflow_files(root)
    all_wf = "\n".join(wfs.values())
    uses_wrapper = grep(all_wf, r"\./gradlew\b")
    uses_no_daemon = grep(all_wf, r"--no-daemon")
    # Flag if --write-locks or --write-verification-metadata appears in CI (must
    # be local-only)
    writes_locks_in_ci = grep(all_wf, r"--write-locks|--write-verification-metadata")
    findings["ci"] = {
        "uses_wrapper": uses_wrapper,
        "no_daemon": uses_no_daemon,
        "writes_locks_in_ci": writes_locks_in_ci,
        "status": status(uses_wrapper and not writes_locks_in_ci),
    }

    return findings


# ---------------------------------------------------------------------------
# Dependabot audit
# ---------------------------------------------------------------------------

ECOSYSTEM_KEYS = {
    "nodejs": "npm",
    "python": "pip",
    "go": "gomod",
    "rust": "cargo",
    "php": "composer",
    "ruby": "bundler",
    "terraform": "terraform",
    "maven": "maven",
    "gradle": "gradle",
}


def audit_dependabot(root, detected_ecosystems):
    r = Path(root)
    dep_file = r / ".github" / "dependabot.yml"
    if not dep_file.exists():
        dep_file = r / ".github" / "dependabot.yaml"

    if not dep_file.exists():
        return {
            "file": None,
            "status": "missing",
            "ecosystems": {eco: "missing" for eco in detected_ecosystems},
        }

    content = read(dep_file)
    findings = {"file": ".github/dependabot.yml"}

    eco_findings = {}
    for eco in detected_ecosystems:
        key = ECOSYSTEM_KEYS.get(eco, eco)
        present = grep(content, rf'package-ecosystem:\s*["\']?{re.escape(key)}["\']?')
        if present:
            # Check for cooldown block — look for cooldown: within ~10 lines of this ecosystem entry
            # Simple heuristic: split on package-ecosystem entries and check the relevant block
            blocks = re.split(r"- package-ecosystem:", content)
            has_cooldown = False
            cooldown_days = None
            for block in blocks:
                if re.search(rf'["\']?{re.escape(key)}["\']?', block):
                    has_cooldown = grep(block, r"cooldown:")
                    m = re.search(r"default-days:\s*(\d+)", block)
                    cooldown_days = int(m.group(1)) if m else None
                    break
            eco_findings[eco] = {
                "status": "pass" if has_cooldown else "warn",
                "ecosystem_key": key,
                "cooldown_configured": has_cooldown,
                "cooldown_default_days": cooldown_days,
            }
            if eco == "terraform":
                eco_findings[eco]["known_bug"] = (
                    "Dependabot cooldown may not be respected for terraform providers (issue #13715)"
                )
            if eco == "gradle":
                # Gradle Wrapper version is a separate Dependabot ecosystem;
                # surface it as a sub-finding so the LLM can flag if missing.
                wrapper_present = grep(
                    content, r'package-ecosystem:\s*["\']?gradle-wrapper["\']?'
                )
                eco_findings[eco]["gradle_wrapper_ecosystem"] = (
                    "pass" if wrapper_present else "missing"
                )
        else:
            eco_findings[eco] = {"status": "missing", "ecosystem_key": key}

    findings["ecosystems"] = eco_findings
    findings["status"] = status(all(v["status"] == "pass" for v in eco_findings.values()))
    return findings


# ---------------------------------------------------------------------------
# Harden-Runner audit
# ---------------------------------------------------------------------------


def audit_harden_runner(root):
    wfs = workflow_files(root)
    if not wfs:
        return {"status": "no_workflows", "workflows": {}}

    results = {}
    for name, content in wfs.items():
        has_hr = grep(content, r"harden-runner")
        egress = find_value(content, r"egress-policy:\s*(\S+)")
        disable_sudo = grep(content, r"disable-sudo:\s*true")
        has_endpoints = grep(content, r"allowed-endpoints")

        if not has_hr:
            wf_status = "fail"
        elif egress == "audit":
            wf_status = "warn"
        elif egress == "block":
            wf_status = "pass"
        else:
            wf_status = "warn"

        results[name] = {
            "harden_runner_present": has_hr,
            "egress_policy": egress,
            "disable_sudo": disable_sudo,
            "allowed_endpoints": has_endpoints,
            "status": wf_status,
        }

    overall = (
        "pass"
        if all(v["status"] == "pass" for v in results.values())
        else "warn"
        if any(v["harden_runner_present"] for v in results.values())
        else "fail"
    )

    return {"status": overall, "workflows": results}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Harden-packages audit data collector")
    parser.add_argument("--path", default=".", help="Path to repository root")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(json.dumps({"error": f"Path not found: {root}"}))
        sys.exit(1)

    detected = detect_ecosystems(root)

    report = {
        "repo": root,
        "ecosystems_detected": detected,
    }

    audit_map = {
        "nodejs": audit_nodejs,
        "python": audit_python,
        "go": audit_go,
        "rust": audit_rust,
        "php": audit_php,
        "ruby": audit_ruby,
        "terraform": audit_terraform,
        "maven": audit_maven,
        "gradle": audit_gradle,
    }

    for eco in detected:
        if eco in audit_map:
            try:
                report[eco] = audit_map[eco](root)
            except Exception as e:
                report[eco] = {"error": str(e)}

    report["dependabot"] = audit_dependabot(root, detected)
    report["harden_runner"] = audit_harden_runner(root)

    indent = 2 if args.pretty else None
    print(json.dumps(report, indent=indent))


if __name__ == "__main__":
    main()
