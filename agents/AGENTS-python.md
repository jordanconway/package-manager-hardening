<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Agent Instructions: Python Dependency Management

This file contains mandatory guidelines for managing dependencies in this Python project. Follow these rules whenever adding, updating, or removing packages, or modifying CI configuration.

## Hash Verification: Never Fabricate

**AI agents must never invent, guess, autocomplete, or extrapolate a `--hash=sha256:...` value, a `uv.lock` hash, a `poetry.lock` hash, or any other cryptographic hash.** A fabricated hash either fails `pip install --require-hashes` (best case) or silently pins to the wrong wheel/sdist if it accidentally matches.

All Python dependency hashes must be produced by the resolver itself — run `pip-compile --generate-hashes`, `uv lock`, `uv pip compile --generate-hashes`, or `poetry lock` and commit the resulting lockfile. Do not hand-edit `--hash=` lines or `hashes:` blocks.

To confirm a specific artifact's hash:

**Preferred:** if the `harden-packages` skill is available, use its helper:

```bash
python {SKILL_DIR}/verify_hash.py pypi <pkg> <version>            # all artifacts
python {SKILL_DIR}/verify_hash.py pypi <pkg> <version> --wheel    # wheels only
python {SKILL_DIR}/verify_hash.py pypi <pkg> <version> --sdist    # sdist only
```

**Fallback:** `curl -fsSL https://pypi.org/pypi/<pkg>/<version>/json | jq -r '.urls[] | "\(.digests.sha256)  \(.filename)"'`.

If you cannot verify a hash with any of the above, **stop and ask the user**. Do not insert a placeholder or a "likely correct" value.

## Package Names: Never Guess

**AI agents must never add a dependency whose exact name they have not verified against PyPI in the current session.** Typosquatting and slopsquatting — attackers registering names that language models tend to invent — are actively exploited vectors on PyPI. A guessed name either fails to resolve or resolves to a malicious look-alike.

Before adding any new package:

1. Verify the exact name and confirm it is the package you intend: `curl -fsSL https://pypi.org/pypi/<package>/json | jq '{name: .info.name, summary: .info.summary, urls: .info.project_urls}'` — the summary and linked repository must match the stated purpose. Note that PyPI normalises names (`-`, `_`, and `.` are interchangeable), so similar-looking names can be distinct packages.
2. Treat as red flags: a very recent first release, a name one or two characters off a popular package (`request` vs `requests`), a missing or unrelated repository link, and import-name-vs-package-name guesses (the import `yaml` is the package `PyYAML`, not `yaml`).

If the lookup is ambiguous or the package cannot be confidently identified, **stop and ask the user** — do not choose between similar names on intuition.

## Package Manager

This project uses: <!-- uv | pip+pip-tools — delete as appropriate -->

## Dependency Rules

**Always pin exact versions.** Use `==` for all dependencies. Never use `>=`, `~=`, or unpinned entries.

```toml
# correct (pyproject.toml)
dependencies = [
  "requests==2.31.0",
  "fastapi==0.110.0",
]

# incorrect — do not use
dependencies = [
  "requests>=2.31.0",
  "fastapi~=0.110",
]
```

**Never add a package version published within the last 7 days.** Check the upload date on PyPI before adding any new dependency. If a version was uploaded less than 7 days ago, defer the addition until the cooldown has elapsed.

**Always commit the lockfile.** `uv.lock` or the compiled `requirements.lock` must be committed. Never add these files to `.gitignore`.

## Configuration to Verify

When modifying dependency configuration, verify the following are in place:

**For uv** (`pyproject.toml`):

```toml
[tool.uv]
exclude-newer = "7 days"
require-hashes = true
verify-hashes = true
```

> **Known issue with uv:** Setting `exclude-newer` to a relative duration writes a resolved timestamp into `uv.lock`, which can cause merge conflicts when multiple branches upgrade different packages. This is a known upstream issue ([astral-sh/uv#18708](https://github.com/astral-sh/uv/issues/18708)). Rebase or merge `uv.lock` carefully when conflicts occur.

**For pip + pip-tools:**

Compile with hashes and install with hash enforcement:

```bash
pip-compile pyproject.toml --generate-hashes --output-file requirements.lock
pip install --require-hashes -r requirements.lock
```

## CI Install Commands

Use the strict install form — never install without a lockfile in CI:

```bash
# uv
uv sync --frozen

# pip
pip install --require-hashes -r requirements.lock
```

## Security Audit

Run a vulnerability audit whenever dependencies change:

```bash
# uv
uvx pip-audit

# pip
pip-audit -r requirements.lock --audit-level=moderate
```

If the audit reports vulnerabilities, do not merge the change until they are resolved or explicitly acknowledged with a documented justification.

## CI Configuration

### Dependabot

`.github/dependabot.yml` must include a cooldown for this ecosystem. If the file does not exist or lacks a cooldown block, add it:

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30
      semver-minor-days: 7
      semver-patch-days: 3
```

Security update PRs from Dependabot bypass the cooldown automatically and should be reviewed and merged promptly.

### Harden-Runner

Every GitHub Actions workflow that installs dependencies must include `step-security/harden-runner` as its first step. New workflows must not be added without it.

Start in `audit` mode for new workflows, then tighten to `block` once the egress policy is stable:

```yaml
- uses: step-security/harden-runner@6c3c2f2c1c457b00c10c4848d6f5491db3b629df # v2
  with:
    egress-policy: block
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      pypi.org:443
      files.pythonhosted.org:443
      astral.sh:443
      release-assets.githubusercontent.com:443
      raw.githubusercontent.com:443
```

The last three endpoints are required only when `astral-sh/setup-uv` runs:

- `astral.sh` — managed Python downloads.
- `release-assets.githubusercontent.com` — modern GitHub release-asset CDN (the uv binary). The older `github-production-release-asset-2e65be.s3.amazonaws.com` is deprecated and will fail with `ECONNREFUSED` in `block` mode.
- `raw.githubusercontent.com` — **v8+ only**. `setup-uv` v8 fetches its version manifest from `https://raw.githubusercontent.com/astral-sh/versions/main/v1/uv.ndjson`; v6.x did not need this endpoint, so a Dependabot bump from v6 → v8 will fail until it is added.

## What Requires Human Review

The following changes must not be made autonomously and require explicit human approval before proceeding:

- Adding a new dependency with no prior entry in the lockfile
- Upgrading a major version
- Disabling or removing `exclude-newer` from `[tool.uv]`
- Removing `require-hashes` or `verify-hashes` from `[tool.uv.pip]`
- Modifying `.github/dependabot.yml` cooldown values downward
- Removing or modifying Harden-Runner from a workflow
