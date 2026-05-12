<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Security Policy

## Reporting a Vulnerability

If you believe you have found a security vulnerability in this repository, please report it through GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability) feature:

> [Report a vulnerability](https://github.com/jordanconway/package-manager-hardening/security/advisories/new)

This creates a private security advisory visible only to repository maintainers and to you, with a built-in workflow for coordinated disclosure, CVE assignment, and patch publication.

**Please do not report security vulnerabilities through public GitHub issues, pull requests, or discussions.**

## What to include

- A description of the issue and its security impact
- Steps to reproduce, ideally with a minimal example
- Affected versions / commit SHAs
- Any suggested mitigation or patch
- Whether you would like to be credited in the advisory

## Response expectations

This is a documentation and tooling repository — it does not run as a service and has no production deployment. The most likely classes of issue are:

- A flaw in the audit script (`skills/harden-packages/audit.py`) that causes it to under-report a real misconfiguration, falsely report a safe one, or be exploitable when run against an untrusted repo
- Bad advice in the documentation (e.g. an `allowed-endpoints` list that allows exfiltration, a recommended action SHA that turns out to be malicious)
- A vulnerability in this repo's own CI (workflow injection, secret exposure, etc.)

### Service-level commitments

| Stage | Target |
|---|---|
| Acknowledge receipt of report | within **7 days** |
| Initial assessment + severity triage | within **14 days** |
| Fix or documented mitigation — **critical** severity | within **30 days** of confirmation |
| Fix or documented mitigation — **high / medium** severity | within **60 days** of confirmation |
| Fix or documented mitigation — **low** severity | best-effort, typically next release |
| Public disclosure (after fix or coordinated date) | within **90 days** of report |

Severity follows [CVSS v3.1](https://www.first.org/cvss/v3-1/). Critical issues affecting downstream consumers (for example, malicious advice that has already been merged and adopted) will be triaged faster than the table indicates.

If you do not receive an acknowledgement within 7 days, please open a public issue saying "I sent a private report on `<date>` and have not heard back" — do not include vulnerability details in the public issue.

## Scope

In scope:

- This repository's source, documentation, and CI workflows
- The `harden-packages` skill files in `skills/harden-packages/`
- The `AGENTS-*.md` files in `agents/`

Out of scope:

- Vulnerabilities in third-party tools the docs reference (Dependabot, Harden-Runner, zizmor, uv, etc.) — please report those directly to the upstream projects
- Issues in user repositories that adopt these recommendations

## Security posture

This repository's posture is publicly visible:

- **OpenSSF Scorecard** — see the badge in [README.md](README.md). Score is updated weekly and on every push to `main` via [`.github/workflows/scorecard.yml`](.github/workflows/scorecard.yml).
- **CodeQL** — SAST runs on every push, every PR to `main`, and weekly. Findings appear in the Security tab.
- **Dependency review** — every PR is gated on `actions/dependency-review-action` (`fail-on-severity: high`, GPL/AGPL denylist).
- **zizmor** — every push and PR is gated on workflow static analysis at `--min-severity=medium`.
- **Harden-Runner** — every CI job runs under runtime egress control (`block` mode with explicit allowlists, or `audit` mode where `block` is impractical).
- **Secret scanning + push protection** — enabled on the repo.
- **Private vulnerability reporting** — enabled (this is what the link above uses).
- **Property-based fuzzing** — [`tests/test_fuzz.py`](tests/test_fuzz.py) uses Hypothesis to fuzz the audit-script parsers against adversarial inputs.

## Known Scorecard trade-offs

Two Scorecard checks are deliberately not satisfied for this repository, and the corresponding code-scanning alerts are dismissed as `won't fix`:

- **Code-Review** — Scorecard expects every changeset to be approved by a different person than the author. This repository follows a deliberate single-maintainer policy: the owner merges their own PRs and may push directly to `main`. Branch protection enforces required status checks, linear history, conversation resolution, and no force-push, but does **not** require a separate reviewer (`enforce_admins: false`, no `required_pull_request_reviews`). Contributors should expect their own PRs to land via the same flow once they have write access. If you would prefer multi-maintainer review for higher-risk changes, open an issue.
- **Maintained** — Scorecard penalises repositories younger than 90 days. This will resolve with time and is not actionable.

## OpenSSF Best Practices Badge

A Passing-tier self-certification at <https://www.bestpractices.dev/> is in progress. Once awarded, the badge will appear next to the Scorecard badge in [README.md](README.md). Scorecard's `CII-Best-Practices` check will report 0 until the badge is awarded; this is a known gap rather than a missing control.
