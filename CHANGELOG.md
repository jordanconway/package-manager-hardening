<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-06-10

Fourth tagged release. Major theme: the audit becomes a product — a reusable GitHub Action any repository can adopt as a CI check — hardened by fixes from its first real-world runs. Plus three new cross-cutting docs (transitive coverage, Renovate, lockfile integrity) and a new mandatory package-identity rule for AI agents.

### Added

- **Reusable hardening-audit GitHub Action** ([`action.yml`](action.yml) at the repo root, PR #51). Any repository can now run the audit as a CI check: `uses: jordanconway/package-manager-hardening@<commit-sha>` after checkout. Inputs: `path` (default `"."`), `warn-only` (default `"false"`). Outputs: `json-path` / `report-path` in the runner temp directory. Both underlying scripts are Python-stdlib-only, so the action installs nothing and adds no egress requirements beyond checkout. Documented in the README Quick start ("For CI") and [docs/skill.md](docs/skill.md#running-the-audit-in-ci-no-llm-required); a vendored-snippet alternative is documented for policies that forbid third-party actions. **This release tag is the first whose commit contains the action** — pin it by resolving the tag's commit SHA.
- New [`skills/harden-packages/report.py`](skills/harden-packages/report.py) (PR #51): renders audit.py JSON as a markdown findings table with per-finding remediation hints and doc links, and exits non-zero on any `fail`/`missing` finding (the CI gate). `warn` and `n/a` never gate. A "Warnings explained" section derives a reason for every ⚠️ from the finding's own data — audit-mode Harden-Runner workflows cite the documented CodeQL/Scorecard exceptions, cooldown-less Dependabot entries explain the missing soak time, and findings carrying an explicit `note` field surface it verbatim. 37 unit tests.
- New self-audit workflow [`.github/workflows/self-audit.yml`](.github/workflows/self-audit.yml) (PR #51): dogfoods the action via `uses: ./` on every PR, push to `main`, and weekly — any hardening regression in this repo now fails CI with the fix proposed in the job summary.
- New [`docs/transitive.md`](docs/transitive.md) (PR #45): which controls reach transitive dependencies, the update-window gap and its mitigations, the Go module proxy note, and a 15-ecosystem × 3-control summary matrix. Linked from the README intro.
- New [`docs/renovate.md`](docs/renovate.md) (PR #48): Renovate's `minimumReleaseAge` as the PR-level cooldown for every ecosystem the transitive matrix marks ❌ for native age gates (Maven, Gradle, Go, Composer, Bundler, NuGet, Helm, Terraform). Includes `internalChecksFilter: "strict"`, per-manager scoping, a Dependabot comparison table, and limitations.
- New [`docs/lockfile-integrity.md`](docs/lockfile-integrity.md) (PR #49): the lockfile-tampering / `resolved`-URL-injection attack class, a per-format exposure table (URL-embedding lockfiles vs registry-derived and transparency-log formats), and five mitigations — `lockfile-lint` in CI, `npm audit signatures`, Harden-Runner egress block as the runtime backstop, review discipline (CODEOWNERS on lockfiles), and format choice. Propagated to docs/nodejs.md, AGENTS-nodejs.md, and the SKILL.md checklist.
- New mandatory **"Never Guess" package-identity sections in all 12 `agents/AGENTS-*.md` files** (PR #50), parallel to the existing hash rule: verify the exact package name/coordinate/namespace against the registry in the current session before adding it — typosquatting and slopsquatting (names language models tend to invent) are actively exploited. Each section is tailored to its ecosystem's trust anchors (Maven groupId domain verification, NuGet reserved prefixes, Go module paths as repo addresses, Docker/Helm/Terraform publisher badges, GitHub Actions owner verification). Matching bullet in SKILL.md Important notes.
- New [`.npmrc`](.npmrc) (PR #46): this repo now dogfoods its own docs/nodejs.md template (`save-exact`, `minimum-release-age=10080`, `audit`, `fund`) — closing the one genuine `fail` its own audit reported against it.
- `npm audit signatures` guidance in docs/nodejs.md, AGENTS-nodejs.md, and the SKILL.md checklist (PR #47): registry signature + provenance attestation verification for the full tree, complementing lockfile hashes (a tampered lockfile entry carries a matching hash for the substituted artifact; only signature verification catches it).

### Fixed

- Real-world audit fixes from running the action against `lfreleng-actions/dependamerge` and `lfreleng-actions/lftools-uv` (PR #52):
  - Dependabot `uv` ecosystem entries now satisfy the python check (`ECOSYSTEM_ALT_KEYS`); previously uv-first repos with 7-day cooldowns were reported as "python missing".
  - `authors` / `maintainers` inline tables in `[project]` are no longer parsed as package specs (the `", email = "` artifact); the exact_pins parser now tracks dependency arrays explicitly and handles extras brackets (`"requests[socks]>=2"`).
  - `ci_frozen_install` is three-state: `fail` only on an actual unfrozen install command (listed in `unfrozen_in`), `pass` on frozen installs, `warn` with an explanatory note when installs are delegated to reusable/composite actions that file-based scanning cannot see into.
  - Quoted YAML values normalised: `egress-policy: 'block'` was misclassified as `warn`; `disable-sudo: 'true'` was not detected.
- docs/nodejs.md showed `npm install --foreground-scripts` as the provenance verification command; corrected to `npm audit signatures` (PR #47).
- audit.py no longer flags `requires-python = ">=3.10,<3.15"` as a loose dependency pin — it is an interpreter constraint, and bounding it is the recommended configuration (PR #46).
- docs/dependabot.md claimed Dependabot cooldown supports Helm; Dependabot does not update Helm chart dependencies at all (now consistent with the README matrix) (PR #48).

## [0.3.0] - 2026-06-08

Third tagged release. Adds complete .NET / NuGet supply-chain hardening coverage — the most widely used ecosystem not previously documented — and routine dependency maintenance.

### Added

- New `.NET / NuGet` ecosystem coverage across all layers:
  - [`docs/dotnet.md`](docs/dotnet.md): user-facing guide covering `packages.lock.json` opt-in (`RestorePackagesWithLockFile`), `--locked-mode` CI enforcement, bare-vs-bracket version pinning, Central Package Management (`Directory.Packages.props`), Package Source Mapping (`nuget.config`), `dotnet list package --vulnerable --include-transitive` as a CI gate, `global.json` SDK pinning, Dependabot config, and Harden-Runner endpoints.
  - [`agents/AGENTS-dotnet.md`](agents/AGENTS-dotnet.md): mandatory AI agent rules — hash verification, 7-day cooldown, lockfile opt-in, exact-pin requirements, and a human-review checklist.
  - [`tests/test_audit_dotnet.py`](tests/test_audit_dotnet.py): 26 unit tests covering all six `audit_dotnet()` checks (lockfile, lock-file opt-in, exact pins, Central Package Management, Package Source Mapping, CI patterns). Total suite: 278 tests.
  - `skills/harden-packages/audit.py`: `detect_ecosystems()` gains `.csproj` / `.fsproj` / `.vbproj` detection; new `audit_dotnet()` function with six checks; `ECOSYSTEM_KEYS["dotnet"] = "nuget"`.
  - `skills/harden-packages/SKILL.md`: nine interpretation notes, config templates (Directory.Build.props, nuget.config, CI commands, Dependabot entry, Harden-Runner endpoints), and a manual-checklist section.
  - `README.md`: `.NET` row added to the ecosystem table, minimum-release-age matrix, and version-constraint support table; quick-start `curl` command; six NuGet reference links.

### Changed

- GitHub Actions pins bumped across all four workflow files:
  - `actions/checkout`: v6.0.2 → v6.0.3 (PR #43)
  - `astral-sh/setup-uv`: v8.1.0 → v8.2.0 (PR #43)
  - `github/codeql-action` (init / analyze / upload-sarif): v4.35.5 → v4.36.2 (PRs #40, #43)
  - `step-security/harden-runner`: v2.19.3 → v2.19.4 (PR #40)
  - `lycheeverse/lychee-action`: comment sharpened from `# v2` → `# v2.8.0`; SHA unchanged (PR #43)
- Dev dependency `hypothesis` bumped 6.152.4 → 6.155.1 (Dependabot PR #41).

## [0.2.0] - 2026-06-01

Second tagged release. Major theme: closing two gaps in the AI-agent workflow — fabricated hashes when pinning, and unsafe auto-apply of badging-related work that needs human follow-through. Plus accumulated fuzzing, branch-protection, and badging infrastructure that landed on `main` between 0.1.0 and now.

### Added

- New companion script [`skills/harden-packages/verify_hash.py`](skills/harden-packages/verify_hash.py): a single-file, dependency-free CLI that resolves cryptographic hashes from authoritative upstream sources so AI agents using the skill never have to fabricate them. Subcommands cover every ecosystem the skill audits: `gh-action`, `git-ref`, `oci`, `pypi`, `npm`, `crate`, `gem`, `packagist`, `gradle-dist`, `maven`, `tf-provider`, `go-module`. Default output is a bare hash on stdout (shell-friendly); `--json` adds metadata. Exit codes: `0` success, `1` upstream lookup failed, `2` usage error, `3` required external tool missing. Tested with 35 unit tests in [`tests/test_verify_hash.py`](tests/test_verify_hash.py) — all upstream calls are mocked so the suite stays offline.
- New `## Hash Verification: Never Fabricate` section in every `agents/AGENTS-*.md` file (11 files: docker, github-actions, go, helm, jvm, nodejs, php, python, ruby, rust, terraform). Each section states the rule (never invent / guess / autocomplete a hash), points at `verify_hash.py` as the preferred verification path when the `harden-packages` skill is loaded, and lists a short ecosystem-specific manual fallback for repos that adopt only the AGENTS file. Closes the gap where prior guidance assumed lockfile-generated hashes but said nothing about ad-hoc SHA / digest pinning (`actions/checkout@<sha>`, `FROM node:20@sha256:...`, `go install pkg@<sha>`, etc.).
- New `## Companion tool: verify_hash.py` section in [`skills/harden-packages/SKILL.md`](skills/harden-packages/SKILL.md) so an agent loading the skill discovers the helper alongside `audit.py` without having to read the AGENTS files first.
- New `## Step 5 (opt-in): OpenSSF badging and Scorecard setup` section in `SKILL.md` documenting the trigger phrases the agent listens for ("set up Scorecard", "add OpenSSF badges", "do the badging", etc.) and the three sub-flows: 5a Scorecard (plan check → PAT walk-through → repo settings → branch protection → workflow file → first-run verify → badge addition), 5b Best Practices Passing (~100-question self-assessment, user attests personally), 5c OSPS Baseline (~25 controls).
- OpenSSF Open Source Project Security (OSPS) Baseline badge added to the README. Self-assessment completed at <https://www.bestpractices.dev/projects/12822>: 23 controls Met, 2 N/A, 0 Unmet across the AC / BR / DO / GV / LE / QA / VM domains. The Baseline self-assessment is independent of the Best Practices Passing badge already held; both link to the same project (12822).
- Coverage-guided fuzz harnesses in [`fuzz/`](fuzz/) using Atheris (libFuzzer for Python). Two harnesses cover every parser and helper. Hash-pinned in [`fuzz/requirements.txt`](fuzz/requirements.txt) and [`fuzz/requirements.in`](fuzz/requirements.in). Documented in [`fuzz/README.md`](fuzz/README.md).
- New scheduled workflow [`.github/workflows/fuzz.yml`](.github/workflows/fuzz.yml) runs each Atheris harness for 3 minutes weekly (Monday 07:17 UTC) and on `workflow_dispatch`. Crashes upload as artifacts and fail the run. Pinned to `ubuntu-24.04` + Python 3.11 (Atheris wheel constraint).
- [`fuzz/corpus/fuzz_audit_helpers/README.md`](fuzz/corpus/fuzz_audit_helpers/README.md) documenting every binary input in the corpus (currently one: `crash-find_value-no-group`, 4 bytes). Records hex bytes, base64, the bug each input triggered, the fix, and the unit-test regression that pins the same bytes in source. Satisfies OpenSSF Baseline `OSPS-QA-05.02` ("no unreviewable binary artifacts") for the corpus directory — the files have to stay raw bytes on disk for libFuzzer to replay them, but every byte is now documented and cross-referenced.
- `fuzz/README.md`: pointer to the per-harness corpus READMEs and the requirement to document every new corpus entry with hex bytes + bug + fix + regression test.

### Changed

- **Default fix flow is now hands-off for the user.** The skill no longer auto-applies OpenSSF badging-related work — Scorecard workflow, OpenSSF Best Practices Passing badge, OpenSSF OSPS Baseline badge, README badge additions for any of the above, branch-protection mutations on the default branch, or repo-admin setting flips (`allow_auto_merge`, `dependabot_security_updates`, PVR, secret creation). These items still appear in the audit report (marked *(opt-in)*) but are deferred to the new Step 5 (see Added) that runs only when the user explicitly opts in. Rationale: every deferred item requires a token the user must generate, an external account at <https://www.bestpractices.dev/>, or an admin-level mutation that can lock the user out if misconfigured — none of which an AI agent can complete safely on its own. The default profile remains aggressive about everything the agent *can* finish unattended (lockfile + package-manager config, Dependabot, harden-runner, zizmor, dependency-review, runner image pinning, action SHA pinning, CodeQL, fuzz, `SECURITY.md` file content).
- `skills/harden-packages/SKILL.md`: added an explicit *"Default profile: what gets auto-applied vs deferred"* subsection at the top of Step 4 listing each bucket (apply by default / defer to Step 5 / flag for human review per item). The misleading earlier note that grouped dependency-review + Scorecard + SECURITY.md as a single *"CI hardening pack"* is split: dependency-review and SECURITY.md stay in the default flow; Scorecard moves to the opt-in step with the prerequisites it actually depends on.
- Branch protection on `main` tightened to maximise Scorecard's `Branch-Protection` check score on a solo project:
  - `enforce_admins: true` — owner is subject to the same rules (was `false`)
  - `required_pull_request_reviews` set with `required_approving_review_count: 0` — PR flow is now required (no direct push to `main`) but no approver is required (GitHub forbids self-approval; requiring one would block every merge)
  - `dismiss_stale_reviews: true`, `require_last_push_approval: true` — no-ops at count=0 but tick Scorecard boxes and auto-tighten when a second maintainer joins
  - `require_code_owner_reviews: false` — explicitly kept off; would block all merges on a solo project. Documented as a known-acceptable trade-off in `SECURITY.md`.
  - `required_conversation_resolution: true`, `required_linear_history: true` — unchanged from before but explicitly tracked.
  - Self-merge with `gh pr merge --auto --squash --delete-branch` continues to work; verified by merging PR #27.
- Pattern documented in `skills/harden-packages/SKILL.md` ("OpenSSF Scorecard" audit checklist) as the recommended solo-project branch protection config.
- `SECURITY.md`: expanded the `Code-Review` known trade-off; added `Branch-Protection — codeowners review not required` and `Branch-Protection — last push approval is disabled` sub-entries.
- Repo setting `allow_auto_merge` flipped to `true` so `gh pr merge --auto --squash --delete-branch` works (otherwise GraphQL refuses with `Auto merge is not allowed for this repository`).

### Fixed

- Scorecard workflow now passes a fine-grained `SCORECARD_TOKEN` to `ossf/scorecard-action` so the `Branch-Protection` check can read the classic branch-protection API. Without this the entire run failed with `some github tokens can't read classic branch protection rules`. Token requires only `Administration: Read-only` scope on this repo. Documented in [docs/github-actions.md](docs/github-actions.md), the harden-packages skill audit checklist, and AGENTS-github-actions.md.
- Documentation correction: previous releases stated that Hypothesis property-based tests satisfy OpenSSF Scorecard's `Fuzzing` check for Python. **They do not** — Scorecard's Python detector matches `import atheris` only (Hypothesis is recognised for Erlang / Haskell / Elixir / Gleam, but not Python). Corrected in `docs/github-actions.md`, `skills/harden-packages/SKILL.md`, `agents/AGENTS-github-actions.md`, and `SECURITY.md`.
- Test assertion in `tests/test_verify_hash.py` for the OpenTofu registry URL now parses the URL and checks `scheme` + `hostname` directly instead of substring matching the hostname, addressing CodeQL `py/incomplete-url-substring-sanitization`.

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

[Unreleased]: https://github.com/jordanconway/package-manager-hardening/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/jordanconway/package-manager-hardening/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/jordanconway/package-manager-hardening/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/jordanconway/package-manager-hardening/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jordanconway/package-manager-hardening/releases/tag/v0.1.0
