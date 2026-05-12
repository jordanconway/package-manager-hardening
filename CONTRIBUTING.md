<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Contributing

Thanks for your interest in `package-manager-hardening`. This document covers how to file issues, propose changes, and what every pull request must satisfy before it can land.

## Reporting issues

- **Bugs and feature requests**: open a GitHub issue at <https://github.com/jordanconway/package-manager-hardening/issues>.
- **Security vulnerabilities**: do **not** open a public issue. Use the private vulnerability reporting flow described in [SECURITY.md](SECURITY.md).

When filing a bug, please include the affected ecosystem (Node.js, Python, Go, Rust, PHP, Ruby, Maven, Gradle, Terraform, GitHub Actions), the relevant snippet of the manifest or workflow file, and the expected vs. actual behaviour.

## Proposing changes

All changes go through pull requests. The single-maintainer policy is documented in [SECURITY.md](SECURITY.md#known-scorecard-trade-offs); contributors should expect their PRs to be reviewed and merged by the maintainer (the maintainer also merges their own PRs once CI is green).

### Before opening a PR

1. Fork the repository and create a topic branch off `main`.
2. Make your changes.
3. Run the local checks below — every required status check must pass before a PR can be merged.
4. Update or add documentation, recommendations, and tests for any new behaviour.
5. Add SPDX/REUSE annotations to every new file.

### Branch and commit conventions

- Use a descriptive branch name with a kebab-case prefix: `docs/...`, `ci/...`, `fix/...`, `feat/...`, `chore/...`.
- Write commit messages in the imperative mood. The first line is a short summary; the body explains the *why*.
- Keep commits focused. If a PR touches multiple concerns, split it.

## What every PR must satisfy

The following status checks are required on `main` and run automatically on every PR:

| Check | What it does |
|---|---|
| **REUSE compliance** | Every file must carry SPDX-FileCopyrightText and SPDX-License-Identifier (either inline or via [`REUSE.toml`](REUSE.toml)). |
| **Python lint (ruff)** | `audit.py` and the test suite must pass `ruff check`. |
| **Python tests (py3.10 / py3.12)** | Full `pytest` suite, including the Hypothesis fuzz tests in [`tests/test_fuzz.py`](tests/test_fuzz.py), must pass on both supported Python versions. |
| **Markdown lint** | All `*.md` files must pass `markdownlint-cli2` per [`.markdownlint-cli2.yaml`](.markdownlint-cli2.yaml). |
| **Link check** | All links in Markdown files must resolve. |
| **GitHub Actions security (zizmor)** | All workflow files must pass `zizmor --min-severity=medium`. |
| **Dependency review** | New dependencies must not introduce high-severity advisories or denied licenses (GPL/AGPL family). |
| **CodeQL analysis (python / actions)** | SAST must be clean for both languages. |

You can run most of these locally:

```bash
# Python: install dev deps from the locked groups, then test/lint
uv sync --frozen --group dev
uv run pytest -q
uv run ruff check

# REUSE
uv tool run reuse lint

# Markdown
npm ci --ignore-scripts
npx markdownlint-cli2 "**/*.md"

# Workflow static analysis
uv tool run zizmor==1.24.1 .
```

## Coding standards

### Python

- Target Python 3.10+ syntax.
- Pass `ruff check` with the rules configured in [`pyproject.toml`](pyproject.toml).
- New helpers in `audit.py` must be defensive against malformed input (the fuzz tests will catch crashes on adversarial JSON / TOML / YAML). Coerce parsed-JSON results to the expected type before calling `.get` / `.items`.
- Add a corresponding test in `tests/`. For new parsers, add a Hypothesis property test to `tests/test_fuzz.py` asserting the parser does not raise on arbitrary input.

### GitHub Actions workflows

- **Pin every action to a full commit SHA** with a trailing `# vX.Y.Z` comment. Mutable refs (`@v4`, `@main`) are rejected by review.
- Every workflow declares `permissions: {}` at workflow level with explicit per-job grants. Each grant carries an inline `# why` comment to satisfy zizmor's `undocumented-permissions` rule.
- Set `persist-credentials: false` on every `actions/checkout` step.
- Set a `concurrency` group on every workflow.
- Use Harden-Runner with `egress-policy: block` and an explicit `allowed-endpoints` list wherever practical. Document any `audit`-mode exception inline (Scorecard and CodeQL are the only current exceptions, with reasons).
- Pin the runner image to a specific Ubuntu version (`ubuntu-24.04`), not `ubuntu-latest`.

### Recommendations and documentation

- Recommendations must be **widely and easily implementable** with zero proxy / registry / self-hosted infrastructure. GitHub-native and SaaS-tool-native solutions are preferred.
- When proposing a new control, update **all** of:
  - The relevant `docs/<ecosystem>.md` (the user-facing how-to)
  - [`skills/harden-packages/SKILL.md`](skills/harden-packages/SKILL.md) (the LLM-callable audit checklist)
  - The matching `agents/AGENTS-<topic>.md` (rules for AI coding assistants operating on user repos)
  - [`README.md`](README.md) summary table when adding a new category
  - [`audit.py`](skills/harden-packages/audit.py) if the control is auditable

### Dependencies and lockfiles

- Python dev dependencies live in `pyproject.toml` under `[dependency-groups].dev` and are locked in `uv.lock`. Update with `uv lock` and commit both files.
- Node.js dev dependencies live in `package.json` and are locked in `package-lock.json`. Use `npm install <pkg>@<version>` then commit both. CI installs with `npm ci --ignore-scripts` from the lockfile.
- GitHub Actions are managed by Dependabot in [`.github/dependabot.yml`](.github/dependabot.yml) with a 7-day rolling cooldown.

### Licensing

This project is MIT-licensed. By submitting a PR you agree your contribution is licensed under MIT.

Every new file must declare its license. For files that support comments, add a header:

```text
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
```

For files without comment syntax (JSON, lockfiles, binary), add an entry to [`REUSE.toml`](REUSE.toml).

## Code of conduct

Be respectful, be specific, assume good faith. Personal attacks, harassment, or discriminatory language will result in the issue / PR being closed without further engagement.

## Questions

Open a discussion-style issue at <https://github.com/jordanconway/package-manager-hardening/issues> with the label `question` (or no label is fine).
