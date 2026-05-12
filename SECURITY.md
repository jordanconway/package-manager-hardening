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

Maintainers will acknowledge reports within **7 days** and aim to publish a fix or mitigation within **30 days** of confirmation. Critical issues affecting downstream consumers (e.g. malicious advice that has already been merged) will be triaged faster.

## Scope

In scope:

- This repository's source, documentation, and CI workflows
- The `harden-packages` skill files in `skills/harden-packages/`
- The `AGENTS-*.md` files in `agents/`

Out of scope:

- Vulnerabilities in third-party tools the docs reference (Dependabot, Harden-Runner, zizmor, uv, etc.) — please report those directly to the upstream projects
- Issues in user repositories that adopt these recommendations
