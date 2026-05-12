<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Coverage-guided fuzz harnesses in [`fuzz/`](fuzz/) using Atheris (libFuzzer for Python). Two harnesses cover every parser and helper. Hash-pinned in [`fuzz/requirements.txt`](fuzz/requirements.txt) and [`fuzz/requirements.in`](fuzz/requirements.in). Documented in [`fuzz/README.md`](fuzz/README.md).
- New scheduled workflow [`.github/workflows/fuzz.yml`](.github/workflows/fuzz.yml) runs each Atheris harness for 3 minutes weekly (Monday 07:17 UTC) and on `workflow_dispatch`. Crashes upload as artifacts and fail the run. Pinned to `ubuntu-24.04` + Python 3.11 (Atheris wheel constraint).

### Fixed

- Scorecard workflow now passes a fine-grained `SCORECARD_TOKEN` to `ossf/scorecard-action` so the `Branch-Protection` check can read the classic branch-protection API. Without this the entire run failed with `some github tokens can't read classic branch protection rules`. Token requires only `Administration: Read-only` scope on this repo. Documented in [docs/github-actions.md](docs/github-actions.md), the harden-packages skill audit checklist, and AGENTS-github-actions.md.
- Documentation correction: previous releases stated that Hypothesis property-based tests satisfy OpenSSF Scorecard's `Fuzzing` check for Python. **They do not** — Scorecard's Python detector matches `import atheris` only (Hypothesis is recognised for Erlang / Haskell / Elixir / Gleam, but not Python). Corrected in `docs/github-actions.md`, `skills/harden-packages/SKILL.md`, `agents/AGENTS-github-actions.md`, and `SECURITY.md`.

## [0.1.0] - 2026-05-12

Initial tagged release. The project has been developed openly on `main` since its first commit; this release establishes a stable baseline that downstream consumers (humans, AI coding assistants, and CI integrations) can pin to.

### Added — Per-ecosystem hardening recommendations

Reference docs under [`docs/`](docs/) covering exact-version pinning, lockfile commits, hash verification, minimum release age (cooldown), CI install commands, and audit tooling for:

- **Node.js** (npm, pnpm, yarn, bun) — [`docs/nodejs.md`](docs/nodejs.md)
- **Python** (pip, uv) — [`docs/python.md`](docs/python.md)
- **Go** modules — [`docs/go.md`](docs/go.md)
- **Rust / Cargo** — [`docs/rust.md`](docs/rust.md)
- **PHP / Composer** — [`docs/php.md`](docs/php.md)
- **Ruby / Bundler** — [`docs/ruby.md`](docs/ruby.md)
- **JVM** (Maven, Gradle — Java and Kotlin) — [`docs/jvm.md`](docs/jvm.md)
- **Terraform / OpenTofu** — [`docs/terraform.md`](docs/terraform.md)
- **Docker** — [`docs/docker.md`](docs/docker.md)
- **Helm** — [`docs/helm.md`](docs/helm.md)

### Added — Cross-cutting controls

- **GitHub Actions** hardening — [`docs/github-actions.md`](docs/github-actions.md): SHA pinning with `# vX.Y.Z` comments, runner image pinning (`ubuntu-24.04`), least-privilege `permissions: {}` with per-job grants and inline justifications, expression-injection prevention, OIDC, CODEOWNERS, `persist-credentials: false`, workflow concurrency, [zizmor](https://github.com/woodruffw/zizmor) static analysis, [CodeQL](https://docs.github.com/en/code-security/code-scanning) SAST, fuzzing, [`actions/dependency-review-action`](https://github.com/actions/dependency-review-action) on PRs, [OpenSSF Scorecard](https://github.com/ossf/scorecard-action), and `SECURITY.md` + private vulnerability reporting.
- **Dependabot** configuration patterns — [`docs/dependabot.md`](docs/dependabot.md): rolling cooldowns (`"7 days"`), per-ecosystem grouping, `github-actions` ecosystem caveats.
- **Harden-Runner** runtime egress control — [`docs/harden-runner.md`](docs/harden-runner.md): `block` mode with explicit `allowed-endpoints`; documented `audit`-mode exceptions (Scorecard, CodeQL).

### Added — `harden-packages` skill

- [`skills/harden-packages/SKILL.md`](skills/harden-packages/SKILL.md): an LLM-callable runbook for auditing and remediating any of the supported ecosystems in a target repository.
- [`skills/harden-packages/audit.py`](skills/harden-packages/audit.py): a Python CLI that emits structured JSON findings per ecosystem. Inputs: `--path` (defaults to `.`), `--pretty`. Outputs: a top-level JSON object keyed by detected ecosystem, with per-control `status` (`ok` / `fail` / `warn`), evidence, and remediation hints. Defensive parsing — fuzz-tested against malformed JSON / TOML inputs.

### Added — `AGENTS-*` files

Per-ecosystem rules for AI coding assistants operating on user repositories — [`agents/`](agents/): `nodejs`, `python`, `go`, `rust`, `php`, `ruby`, `jvm`, `terraform`, `docker`, `helm`, `github-actions`. Each documents what changes require explicit human review.

### Added — This repository's own security posture

- All required CI status checks on `main`: REUSE, ruff, pytest (3.10 + 3.12), markdown lint, link check, zizmor, dependency review, CodeQL (python + actions).
- Branch protection enforcing the above with linear history, conversation resolution, and no force-push.
- Dependabot enabled for `github-actions`, `uv`, and `npm` ecosystems with 7-day rolling cooldown.
- Property-based fuzz tests in [`tests/test_fuzz.py`](tests/test_fuzz.py) using Hypothesis (15 tests, 10 ecosystems covered).
- [`SECURITY.md`](SECURITY.md) with private vulnerability reporting enabled.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) covering required checks, coding standards, and the propagation checklist for new controls.
- OpenSSF Scorecard workflow, weekly + on push to `main`.
- Python toolchain managed by `uv` with `[dependency-groups].dev` (PEP 735) and a hash-verified `uv.lock`.
- Node.js dev dependencies (markdownlint) hash-verified via committed `package-lock.json`; CI uses `npm ci --ignore-scripts`.

### Security

No publicly known runtime vulnerabilities have been reported against this project at the time of this release.

### Known trade-offs

Documented in [`SECURITY.md`](SECURITY.md):

- Single-maintainer policy — Scorecard `Code-Review` check is intentionally not satisfied.
- `Maintained` Scorecard check is time-based and will resolve once the repository is 90 days old.
- OpenSSF Best Practices badge: **Passing** tier awarded (project 12822).

[Unreleased]: https://github.com/jordanconway/package-manager-hardening/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jordanconway/package-manager-hardening/releases/tag/v0.1.0
