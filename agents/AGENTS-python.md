# Agent Instructions: Python Dependency Management

This file contains mandatory guidelines for managing dependencies in this Python project. Follow these rules whenever adding, updating, or removing packages, or modifying CI configuration.

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
- uses: step-security/harden-runner@v2
  with:
    egress-policy: block
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      pypi.org:443
      files.pythonhosted.org:443
```

## What Requires Human Review

The following changes must not be made autonomously and require explicit human approval before proceeding:

- Adding a new dependency with no prior entry in the lockfile
- Upgrading a major version
- Disabling or removing `exclude-newer` from `[tool.uv]`
- Removing `require-hashes` or `verify-hashes`
- Modifying `.github/dependabot.yml` cooldown values downward
- Removing or modifying Harden-Runner from a workflow
