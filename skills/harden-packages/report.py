# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""
report.py — render audit.py findings as a markdown report with a CI gate.

Reads the JSON emitted by audit.py and writes a GitHub-flavoured markdown
summary to stdout (suitable for $GITHUB_STEP_SUMMARY). Exits non-zero when
any check reports "fail" or "missing", so it can gate a CI job. Statuses of
"warn" (e.g. documented audit-mode Harden-Runner exceptions) and "n/a" never
fail the gate.

Usage:
    python audit.py --path . | python report.py
    python report.py audit.json
    python report.py audit.json --warn-only   # report, but always exit 0

Like audit.py, this script is dependency-free (stdlib only) so it can run in
CI without installing anything.
"""

import json
import sys

MARKERS = {
    "pass": "✅",
    "warn": "⚠️",
    "fail": "❌",
    "missing": "❌",
}
NEUTRAL_MARKER = "⚪"  # n/a, unknown, no_workflows, anything unrecognised

FAILING = {"fail", "missing"}

# Where to send the reader for each top-level section. Checks under an
# ecosystem inherit its doc; cross-cutting sections have their own.
SECTION_DOCS = {
    "nodejs": "docs/nodejs.md",
    "python": "docs/python.md",
    "go": "docs/go.md",
    "rust": "docs/rust.md",
    "php": "docs/php.md",
    "ruby": "docs/ruby.md",
    "dotnet": "docs/dotnet.md",
    "terraform": "docs/terraform.md",
    "maven": "docs/jvm.md",
    "gradle": "docs/jvm.md",
    "dependabot": "docs/dependabot.md",
    "harden_runner": "docs/harden-runner.md",
}

# One-line remediation hints keyed by the check name (last path segment that
# isn't a per-item key like a workflow filename). Generic on purpose — the
# full config templates live in SKILL.md and the per-ecosystem docs.
HINTS = {
    "lockfile": "Commit the lockfile and enforce it in CI with the strict install command.",
    "lock_file_opt_in": "Enable RestorePackagesWithLockFile in Directory.Build.props, restore, commit the lockfile.",
    "exact_pins": "Replace range/floating constraints with exact version pins.",
    "minimum_release_age": "Configure the package manager's minimum release age (7 days recommended).",
    "uv_config": "Set exclude-newer in [tool.uv] and require-hashes/verify-hashes in [tool.uv.pip].",
    "build_script_control": "Restrict which packages may run install scripts (allowlist).",
    "ci_frozen_install": "Use the frozen/locked install command in CI.",
    "ci": "Align CI install and audit commands with the recommended configuration.",
    "ruby_version": "Pin the interpreter via a ruby directive in Gemfile or a .ruby-version file.",
    "central_package_management": "Adopt Directory.Packages.props with ManagePackageVersionsCentrally.",
    "source_mapping": "Add <packageSourceMapping> to nuget.config to prevent dependency confusion.",
    "enforcer_plugin": "Configure maven-enforcer-plugin with banDynamicVersions et al.",
    "strict_checksums": "Set <checksumPolicy>fail</checksumPolicy> or pass --strict-checksums in CI.",
    "sca_scanner": "Wire an SCA scanner (Dependency-Check / CycloneDX / OSS Index) into the build.",
    "dependency_locking": "Enable dependencyLocking with LockMode.STRICT and commit gradle.lockfile.",
    "dependency_verification": "Commit gradle/verification-metadata.xml with verify-metadata=true.",
    "wrapper": "Add distributionSha256Sum to gradle-wrapper.properties.",
    "repository_control": "Set FAIL_ON_PROJECT_REPOS; remove mavenLocal()/jcenter().",
    "reject_dynamic": "Configure failOnNonReproducibleResolution() or failOnDynamicVersions().",
    "dependabot": "Add the missing ecosystem entry with a cooldown block to .github/dependabot.yml.",
    "harden_runner": "Add step-security/harden-runner as the first step of every workflow.",
}


def walk(node, path):
    """Yield (dotted_path, status, node) for every dict carrying a string status."""
    if not isinstance(node, dict):
        return
    status = node.get("status")
    if isinstance(status, str):
        yield ".".join(path), status, node
    if "error" in node and isinstance(node.get("error"), str):
        yield ".".join(path + ["error"]), "fail", node
    for key, value in node.items():
        if key == "status":
            continue
        if isinstance(value, dict):
            yield from walk(value, path + [key])


def warn_reason(path, node):
    """Explain why a specific check is a warning, from the finding's own data."""
    # An explicit note from audit.py is authoritative.
    note = node.get("note")
    if isinstance(note, str) and note:
        return note

    segments = path.split(".")

    if segments[0] == "harden_runner":
        if len(segments) >= 3 and segments[1] == "workflows":
            if node.get("egress_policy") == "audit":
                return (
                    "Harden-Runner runs in `audit` mode — outbound connections are logged but not blocked. "
                    "Review the audit log and switch to `egress-policy: block` with an `allowed-endpoints` "
                    "allowlist. (CodeQL and Scorecard workflows are documented exceptions: both contact "
                    "endpoint sets too dynamic to allowlist and must stay in audit mode.)"
                )
            if node.get("harden_runner_present"):
                return (
                    "Harden-Runner is present but its `egress-policy` was not recognised — "
                    "set it explicitly to `block` (or `audit` while building an allowlist)."
                )
            return "Harden-Runner status could not be determined for this workflow."
        workflows = node.get("workflows")
        if isinstance(workflows, dict) and workflows:
            passing = sum(1 for w in workflows.values() if isinstance(w, dict) and w.get("status") == "pass")
            return (
                f"{passing} of {len(workflows)} workflows enforce `egress-policy: block`; "
                "the rest run in audit mode or lack Harden-Runner — see the per-workflow rows."
            )
        return "Harden-Runner coverage is incomplete — see the per-workflow rows."

    if segments[0] == "dependabot" and node.get("cooldown_configured") is False:
        return (
            "The ecosystem has a dependabot.yml entry but no `cooldown:` block — update PRs are "
            "raised immediately on release, with no soak time for the community to catch a "
            "compromised version."
        )

    return "Configured, but not at the strictest recommended setting — see the linked doc."


def hint_for(path):
    segments = path.split(".")
    for segment in reversed(segments):
        if segment in HINTS:
            return HINTS[segment]
    return "See the linked doc for the recommended configuration."


def doc_for(path):
    top = path.split(".")[0]
    return SECTION_DOCS.get(top)


def render(report):
    """Return (markdown, failing_paths) for an audit.py report dict."""
    checks = []
    for top_key, value in report.items():
        if top_key in ("repo", "ecosystems_detected"):
            continue
        checks.extend(walk(value, [top_key]))

    lines = ["# Package hardening self-audit", ""]
    detected = report.get("ecosystems_detected")
    if isinstance(detected, list) and detected:
        lines.append(f"**Ecosystems detected:** {', '.join(str(e) for e in detected)}")
        lines.append("")

    lines.append("| Check | Status |")
    lines.append("|-------|--------|")
    for path, status, _node in checks:
        marker = MARKERS.get(status, NEUTRAL_MARKER)
        lines.append(f"| `{path}` | {marker} {status} |")
    lines.append("")

    failing = [(path, status) for path, status, _node in checks if status in FAILING]
    if failing:
        lines.append("## Recommended changes")
        lines.append("")
        for path, _status in failing:
            doc = doc_for(path)
            link = f" ([{doc}]({doc}))" if doc else ""
            lines.append(f"- `{path}` — {hint_for(path)}{link}")
        lines.append("")
    else:
        lines.append("No failing checks.")
        lines.append("")

    warnings = [(path, node) for path, status, node in checks if status == "warn"]
    if warnings:
        lines.append("## Warnings explained")
        lines.append("")
        lines.append("Warnings never fail this check — they mark documented exceptions or settings")
        lines.append("that could be tightened further.")
        lines.append("")
        for path, node in warnings:
            doc = doc_for(path)
            link = f" ([{doc}]({doc}))" if doc else ""
            lines.append(f"- `{path}` — {warn_reason(path, node)}{link}")
        lines.append("")

    return "\n".join(lines), [path for path, _ in failing]


def main():
    args = [a for a in sys.argv[1:] if a != "--warn-only"]
    warn_only = "--warn-only" in sys.argv[1:]

    try:
        if args:
            with open(args[0], encoding="utf-8") as f:
                report = json.load(f)
        else:
            report = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError) as e:
        print(f"report.py: cannot read audit JSON: {e}", file=sys.stderr)
        sys.exit(2)

    if not isinstance(report, dict):
        print("report.py: audit JSON must be an object", file=sys.stderr)
        sys.exit(2)

    markdown, failing = render(report)
    print(markdown)

    if failing and not warn_only:
        print(f"report.py: {len(failing)} failing check(s): {', '.join(failing)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
