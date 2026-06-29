<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Python Ecosystem

## pip

**Configuration files:** `pip.conf` (Unix: `~/.config/pip/pip.conf`, Windows: `%APPDATA%\pip\pip.ini`), `requirements.txt`, `pyproject.toml` (via build backends)

### Lockfile / Pinning

pip has no native lockfile. Use `pip-compile` (from `pip-tools`) to generate a fully resolved, hash-pinned `requirements.txt`:

```bash
pip install pip-tools
pip-compile pyproject.toml --generate-hashes --output-file requirements.lock
pip install -r requirements.lock
```

For direct installs, pin exact versions with hashes for maximum integrity:

```text
# requirements.txt
requests==2.31.0 \
    --hash=sha256:58cd2187423839... \
    --hash=sha256:942c5a758f98d...
```

Install with hash enforcement:

```bash
pip install --require-hashes -r requirements.txt
```

### Registry / Index Configuration

```ini
# pip.conf
[global]
index-url = https://your-pypi-mirror.example.com/simple/
extra-index-url = https://pypi.org/simple/
trusted-host = your-pypi-mirror.example.com
```

Or per-invocation:

```bash
pip install mypackage \
  --index-url https://your-registry.example.com/simple/ \
  --extra-index-url https://pypi.org/simple/
```

### Security: Upload-Time Filtering (pip ≥ 26.0)

pip 26.0 (January 2026) added `--uploaded-prior-to`, which restricts resolution to package versions uploaded before a given datetime (absolute ISO 8601 timestamps only):

```bash
# Only consider packages uploaded before this date
pip install -r requirements.txt \
  --uploaded-prior-to "2026-01-15T00:00:00Z"
```

> **Limitation:** `--uploaded-prior-to` accepts absolute timestamps only, not relative durations like "7 days ago." This makes it better suited as a reproducibility/snapshot tool than a rolling security cooldown. An open issue tracks adding relative duration support. For a sliding cooldown window, use uv instead.

### Security: Disabling Network Access

```bash
pip install --no-index --find-links=/path/to/local/cache mypackage
```

Or enforce no-network in `pip.conf`:

```ini
[global]
no-index = true
find-links = /path/to/local/wheels
```

### Dependency Auditing

```bash
pip install pip-audit
pip-audit                              # audit installed packages
pip-audit -r requirements.txt         # audit a requirements file
pip-audit --fix                        # auto-upgrade vulnerable packages
```

### CI Recommended Configuration

```bash
pip install --require-hashes -r requirements.lock
pip-audit -r requirements.lock --audit-level=moderate
```

---

## uv

**Configuration files:** `pyproject.toml` (under `[tool.uv]`), `uv.toml`, `uv.lock`

uv is a fast Python package and project manager from Astral. It replaces pip, pip-tools, virtualenv, and Poetry for most use cases.

### Lockfile

uv generates `uv.lock` — a universal, cross-platform lockfile with full transitive resolution. Always commit it.

```bash
uv sync                     # install from lockfile (creates if absent)
uv sync --frozen            # CI: fail if lockfile is out of date
uv lock                     # regenerate lockfile without installing
uv lock --check             # verify lockfile is up to date (CI check)
```

### Version Pinning

In `pyproject.toml`, specify exact versions using `==`:

```toml
[project]
dependencies = [
  "requests==2.31.0",
  "fastapi==0.110.0",
]
```

For development dependencies, prefer PEP 735 dependency groups (supported by uv since 0.5.x) over the older uv-specific `[tool.uv].dev-dependencies` form:

```toml
[dependency-groups]
dev = [
  "pytest==8.1.0",
  "ruff==0.4.0",
]
```

Install with `uv sync --group dev` (or `--all-groups`). Dependabot's `uv` ecosystem reads `[dependency-groups]` and will open update PRs for entries declared there — inline `pip install x==y` lines in workflow files are invisible to Dependabot.

### Registry / Index Configuration

```toml
# pyproject.toml
[tool.uv]
index-url = "https://your-pypi-mirror.example.com/simple/"
extra-index-url = ["https://pypi.org/simple/"]

# Or define named indexes with priority
[[tool.uv.index]]
name = "internal"
url = "https://your-pypi-mirror.example.com/simple/"
priority = "first"

[[tool.uv.index]]
name = "pypi"
url = "https://pypi.org/simple/"
priority = "supplemental"
```

Authentication:

```toml
# pyproject.toml
[tool.uv]
keyring-provider = "subprocess"   # use system keyring for credentials
```

Or via environment variables:

```bash
UV_INDEX_URL=https://your-registry.example.com/simple/
UV_EXTRA_INDEX_URL=https://pypi.org/simple/
UV_HTTP_BASIC_MYREGISTRY_USERNAME=user
UV_HTTP_BASIC_MYREGISTRY_PASSWORD=$TOKEN
```

### Security: Minimum Release Age / Cooldown (uv ≥ 0.9.17)

uv 0.9.17 (December 2025) added relative duration support to `exclude-newer`, enabling a rolling cooldown window. Set in `pyproject.toml`:

```toml
# pyproject.toml
[tool.uv]
exclude-newer = "7 days"

# Supported units: minutes, hours, days, weeks
# Examples: "24 hours", "3 days", "1 week"
```

This causes uv to ignore any package version published within the last 7 days when resolving dependencies.

> **Choose `exclude-newer` *or* a Dependabot `uv`/`pip` cooldown — not both.** They enforce the same release-age control at different layers. Unlike Dependabot, `exclude-newer` has **no security-update exception**: a just-published CVE fix is filtered out during resolution, so a Dependabot security PR becomes unsatisfiable and needs a manual version-floor bump, a per-package cooldown exemption, and a lockfile regeneration. For most repositories, prefer the Dependabot cooldown (security fixes keep flowing automatically) and omit `exclude-newer`. Use `exclude-newer` only when you need full-graph/transitive or local-install coverage, and then do not also run a Dependabot cooldown for Python. See [Cooldown: resolver-level vs Dependabot](dependabot.md#cooldown-resolver-level-vs-dependabot--pick-one).

Per-package overrides (allow a specific package to bypass the cooldown):

```toml
[tool.uv]
exclude-newer = "7 days"

[[tool.uv.package-overrides]]
name = "critical-security-fix"
exclude-newer = "0 days"   # bypass cooldown for this package
```

> **Known issue:** When `exclude-newer` is set to a relative duration, uv resolves it to an absolute timestamp and writes that timestamp into `uv.lock`. This can cause merge conflicts when multiple branches upgrade different packages. Tracked upstream at [astral-sh/uv#18708](https://github.com/astral-sh/uv/issues/18708).

### Security: Hash Verification

When installing from `uv.lock` via `uv sync --frozen`, hash verification is **automatic and unconditional** — every wheel/sdist resolved from the lockfile is checked against the sha256 recorded at lock time. No additional flag is required, and the lockfile must be committed for this to work.

The `require-hashes` / `verify-hashes` knobs live under `[tool.uv.pip]` (not `[tool.uv]` — uv rejects them at the top level) and only apply to ad-hoc `uv pip install` invocations that bypass the project workflow:

```toml
# pyproject.toml
[tool.uv.pip]
require-hashes = true        # uv pip install: every dep must carry a hash
verify-hashes = true         # uv pip install: verify hashes at install time
```

### Security: Disabling Build Scripts

```toml
# pyproject.toml
[tool.uv]
no-build = true              # never build from source; wheels only
no-binary = ["somepackage"]  # force source build for specific package
```

### Workspace / Monorepo

```toml
# pyproject.toml (workspace root)
[tool.uv.workspace]
members = ["packages/*", "services/*"]
```

```bash
uv sync --all-packages    # install all workspace packages
uv run --package myapi pytest  # run in specific workspace member
```

### CI Recommended Configuration

```toml
# pyproject.toml
[tool.uv]
exclude-newer = "7 days"

[tool.uv.pip]
require-hashes = true
verify-hashes = true
```

In the workflow, install uv via the official action (SHA-pinned with the dereferenced annotated-tag commit, plus a `version:` pin so the runtime matches local development):

```yaml
- uses: astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e # v6.8.0
  with:
    version: "0.11.11"

- run: uv sync --frozen --group dev --python 3.12
- run: uv run pytest
```

Harden-Runner allowlist must include the uv binary download path:

```yaml
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

Notes:

- GitHub release downloads now redirect through `release-assets.githubusercontent.com`. Older guides that list `github-production-release-asset-2e65be.s3.amazonaws.com` are out of date.
- `raw.githubusercontent.com` is needed by `astral-sh/setup-uv` **v8+** only: v8 fetches its version manifest from `https://raw.githubusercontent.com/astral-sh/versions/main/v1/uv.ndjson`. v6.x baked the manifest into the action; workflows upgrading from v6 to v8 will fail until this endpoint is added.

Audit dependencies separately:

```bash
uv sync --frozen
uv run pip-audit   # or: uvx pip-audit
```

---
