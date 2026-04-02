# Package Manager Configuration Reference

A comprehensive reference for configuring npm, pnpm, Yarn, Bun, pip, uv, Go modules, and Cargo — covering lockfiles, version pinning, registry configuration, security hardening, and CI/CD usage.

---

## Using the AGENTS.md Files

This repository includes ready-made `AGENTS.md` files for each supported stack. These files are read by Claude Code and compatible AI coding assistants when they work inside a repository, giving the agent standing instructions on how to handle dependencies safely — enforcing version pinning, cooldown windows, audit requirements, and CI configuration.

### Available files

| File | Use for |
|------|---------|
| [`AGENTS-nodejs.md`](./AGENTS-nodejs.md) | Projects using npm, pnpm, Yarn, or Bun |
| [`AGENTS-python.md`](./AGENTS-python.md) | Projects using pip/pip-tools or uv |
| [`AGENTS-go.md`](./AGENTS-go.md) | Go module projects |
| [`AGENTS-rust.md`](./AGENTS-rust.md) | Rust/Cargo projects |
| [`AGENTS-terraform.md`](./AGENTS-terraform.md) | Terraform or OpenTofu projects |

### Installation

Copy the appropriate file to the root of your repository and rename it `AGENTS.md`:

```bash
# Node.js project
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/AGENTS-nodejs.md

# Python project
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/AGENTS-python.md

# Go project
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/AGENTS-go.md

# Rust project
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/AGENTS-rust.md

# Terraform / OpenTofu project
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/AGENTS-terraform.md
```

Or clone and copy manually:

```bash
git clone https://github.com/jordanconway/package-manager-hardening
cp package-manager-hardening/AGENTS-nodejs.md your-project/AGENTS.md
```

### Customisation

After copying, open the file and:

1. **Node.js only:** remove the package manager options that don't apply — the file has a `<!-- npm | pnpm | yarn | bun -->` comment near the top indicating which to keep.
2. **Terraform / OpenTofu only:** remove the tool indicator comment at the top (`<!-- terraform | opentofu -->`) and keep only the relevant tool name.
3. Update the Harden-Runner `allowed-endpoints` list to match your project's actual network requirements — the provided list is a safe starting point, not a complete allowlist.
4. Adjust cooldown values if your project has specific requirements (valid range: 1–90 days for Dependabot).
5. **Go only:** update the `GOPRIVATE` / `GONOSUMDB` values to match your organisation's internal module paths.

### Monorepos with multiple stacks

For a monorepo containing multiple ecosystems, place a stack-specific `AGENTS.md` in the relevant subdirectory alongside the package manager config file for that language:

```
/                        ← root AGENTS.md (general project context)
├── services/api/        ← AGENTS.md (Node.js rules)
├── services/worker/     ← AGENTS.md (Python rules)
└── tools/cli/           ← AGENTS.md (Go rules)
```

Claude Code reads `AGENTS.md` files from the repo root and from the current working directory, so subdirectory files apply automatically when the agent is working within that directory.

---

## Using the harden-packages Skill

This repository also includes a [Cowork](https://claude.ai) / [Claude Code](https://claude.ai/claude-code) skill that actively audits a repository's package manager configuration and applies fixes interactively. Where the `AGENTS.md` files give an AI agent *standing instructions* to follow as it works, the skill is something you invoke on demand to get an immediate audit report and remediation.

### What it does

When invoked, the skill will:

1. **Detect** which ecosystems are present (Node.js, Python, Go, Rust, Terraform/OpenTofu) and which CI workflows exist
2. **Audit** each ecosystem against the hardening checklist, marking each item ✅ / ⚠️ / ❌
3. **Report** findings with a prioritised list of what poses the most supply chain risk
4. **Fix** gaps interactively — it will ask before writing any files, and you can approve all fixes or pick and choose

### Installation

The skill lives in `skills/harden-packages/` in this repo. Copy it into your Claude skills directory:

```bash
# Claude Code (default skills location)
cp -r skills/harden-packages ~/.claude/skills/

# Or clone the repo and copy
git clone https://github.com/jordanconway/package-manager-hardening
cp -r package-manager-hardening/skills/harden-packages ~/.claude/skills/
```

Verify it's available by checking your skills list in Claude Code:

```bash
claude skills list
```

### Usage

Once installed, open a repository in Claude Code or Cowork and say any of the following — the skill will trigger automatically:

- `harden my repo`
- `audit my package manager config`
- `check my dependencies for supply chain issues`
- `set up Dependabot and Harden-Runner`
- `are my packages safe?`
- `apply package manager hardening`

You can also be specific about scope:

- `audit just the Python dependencies`
- `check if my GitHub Actions workflows have Harden-Runner configured`
- `set up Dependabot cooldowns for this pnpm project`

### What it checks

The skill audits all of the following, where applicable to the detected stack:

| Area | Checks |
|------|--------|
| Lockfiles | Present and committed, not gitignored |
| Version pinning | Exact versions, no `^` / `~` / `>=` / `~>` ranges |
| Minimum release age | Native client config (npm, pnpm, yarn, bun, uv) |
| Build script control | pnpm `onlyBuiltDependencies`, Bun `lifecycleScripts` |
| CI install commands | Frozen/locked install flags enforced |
| Terraform lockfile | `.terraform.lock.hcl` committed, multi-platform hashes, `-lockfile=readonly` in CI |
| Dependabot | Cooldown blocks present for each ecosystem (Terraform cooldown bug flagged) |
| Harden-Runner | Present in all workflows, `block` vs `audit` mode, `allowed-endpoints` |
| Vulnerability scanning | `cargo audit`, `govulncheck`, `pip-audit` in CI |

### Notes

- The skill never downgrades an existing security setting — if you already have a stricter cooldown than the recommended 7 days, it leaves it alone.
- It starts Harden-Runner additions in `audit` mode, not `block`. Switching to block requires reviewing egress logs first, and the skill will explain how.
- It will not change version numbers in package manifests without explicit instruction — pinning existing ranges is a breaking change that deserves separate review.

---

## Table of Contents

- [Node.js Ecosystem](#nodejs-ecosystem)
  - [npm](#npm)
  - [pnpm](#pnpm)
  - [Yarn](#yarn)
  - [Bun](#bun)
- [Python Ecosystem](#python-ecosystem)
  - [pip](#pip)
  - [uv](#uv)
- [Go Modules](#go-modules)
- [Cargo (Rust)](#cargo-rust)
- [Infrastructure as Code](#infrastructure-as-code)
  - [Terraform](#terraform)
  - [OpenTofu](#opentofu)
- [Cross-Cutting Considerations](#cross-cutting-considerations)
  - [Dependabot Integration](#dependabot-integration)
  - [Harden-Runner: Runtime CI Hardening](#harden-runner-runtime-ci-hardening)
  - [Native Minimum Release Age Support Matrix](#native-minimum-release-age-support-matrix)
  - [Version Constraint Support](#version-constraint-support)
- [Reference Links](#reference-links)
- [AGENTS.md Files](#using-the-agentsmd-files)
  - [Node.js](./AGENTS-nodejs.md)
  - [Python](./AGENTS-python.md)
  - [Go](./AGENTS-go.md)
  - [Rust](./AGENTS-rust.md)
  - [Terraform / OpenTofu](./AGENTS-terraform.md)
- [harden-packages Skill](#using-the-harden-packages-skill)

---

## Node.js Ecosystem

### npm

**Configuration files:** `.npmrc` (per-project or global at `~/.npmrc`), `package.json`

#### Lockfile

npm generates `package-lock.json` on install. Commit this file to source control. In CI, always use `npm ci` instead of `npm install` — it installs strictly from the lockfile and fails if the lockfile is out of sync with `package.json`.

```bash
npm ci                   # strict lockfile install (CI)
npm install              # resolves and updates lockfile
npm install --frozen-lockfile  # alias: fails if lockfile would change
```

#### Version Pinning

Use exact versions in `package.json` to prevent silent drift. Remove `^` and `~` prefixes.

```json
{
  "dependencies": {
    "express": "4.18.2",
    "lodash": "4.17.21"
  }
}
```

To pin all dependencies when generating a lockfile:

```bash
npm install --save-exact
```

Set exact as the default in `.npmrc`:

```ini
save-exact=true
```

#### Registry Configuration

```ini
# .npmrc

# Use a private/proxy registry
registry=https://your-registry.example.com/

# Scope-specific registry (packages under @myorg only)
@myorg:registry=https://npm.pkg.github.com/

# Authentication for a registry
//your-registry.example.com/:_authToken=${NPM_TOKEN}

# GitHub Packages auth
//npm.pkg.github.com/:_authToken=${GITHUB_TOKEN}
```

#### Security: Minimum Release Age (npm ≥ 11.10.0)

npm 11.10.0 (February 2026) added native support for blocking packages published within a configurable window. Set in `.npmrc`:

```ini
# Block packages published within the last 7 days
minimum-release-age=10080

# Common values (in minutes):
# 1 day    =  1440
# 3 days   =  4320
# 7 days   = 10080
# 14 days  = 20160
```

> **Note:** As of initial release, npm's `minimum-release-age` does not support per-package exclusions. An open issue tracks adding this capability for cases where urgent security patches need to bypass the delay.

#### Security: Audit and Signatures

```bash
npm audit                      # check for known vulnerabilities
npm audit fix                  # auto-fix where possible
npm audit --audit-level=high   # fail CI only on high/critical

# Verify package provenance (requires registry support)
npm install --foreground-scripts
```

#### Workspace / Monorepo

```json
// package.json (root)
{
  "workspaces": ["packages/*", "apps/*"]
}
```

```bash
npm install                   # installs all workspace dependencies
npm run build --workspaces    # run script in all workspaces
npm run test -w packages/api  # run in a specific workspace
```

#### CI Recommended Configuration

```ini
# .npmrc (committed to repo)
save-exact=true
minimum-release-age=10080
audit=true
fund=false
```

```bash
# CI install command
npm ci --ignore-scripts   # disable postinstall scripts for extra safety
npm audit --audit-level=moderate
```

---

### pnpm

**Configuration files:** `pnpm-workspace.yaml`, `.npmrc`, `package.json`

#### Lockfile

pnpm generates `pnpm-lock.yaml`. Always commit it. In CI use `--frozen-lockfile`:

```bash
pnpm install --frozen-lockfile
```

#### Version Pinning

Same `package.json` semantics as npm. Set exact pinning in `.npmrc`:

```ini
save-exact=true
```

#### Registry Configuration

```ini
# .npmrc
registry=https://your-registry.example.com/
@myorg:registry=https://npm.pkg.github.com/
//npm.pkg.github.com/:_authToken=${GITHUB_TOKEN}
```

#### Security: Minimum Release Age (pnpm ≥ 10.16)

pnpm introduced `minimumReleaseAge` in v10.16 (September 2025), configurable in `pnpm-workspace.yaml`:

```yaml
# pnpm-workspace.yaml
minimumReleaseAge: "7 days"
```

Supported units: `minutes`, `hours`, `days`, `weeks`. Calendar units (months, years) are not supported.

Per-package exclusions (pnpm ≥ 10.22):

```yaml
minimumReleaseAge: "7 days"
minimumReleaseAgeExclude:
  - typescript          # always allow latest TypeScript
  - "@myorg/*"          # exclude internal packages
```

Ignore the age check for older, well-established packages (pnpm ≥ 10.27):

```yaml
minimumReleaseAge: "7 days"
trustPolicyIgnoreAfter: "1 year"   # skip check for packages >1yr old
```

#### Security: Trust Policy (pnpm ≥ 10.0)

`trustPolicy` guards against supply chain attacks that downgrade package trust indicators (e.g., a package that previously had provenance attestation loses it):

```yaml
# pnpm-workspace.yaml
trustPolicy: no-downgrade
```

With `no-downgrade`, pnpm refuses to install a version of a package that has *fewer* trust indicators than a previously installed version. This is distinct from `minimumReleaseAge` — it's about trust regression, not publication age.

Per-package exclusions from trust policy:

```yaml
trustPolicy: no-downgrade
trustPolicyExclude:
  - some-legacy-package   # known to lack provenance
```

#### Security: Build Script Control

pnpm v10 no longer runs lifecycle scripts (postinstall, etc.) from dependencies by default unless explicitly allowed. Configure which packages may run build scripts:

```yaml
# pnpm-workspace.yaml
onlyBuiltDependencies:
  - esbuild
  - "@prisma/engines"
  - node-gyp
```

Or deny specific packages from running scripts:

```yaml
ignoredBuiltDependencies:
  - some-suspicious-package
```

#### Workspace / Monorepo

```yaml
# pnpm-workspace.yaml
packages:
  - "packages/*"
  - "apps/*"
  - "!**/__tests__/**"
```

```bash
pnpm install                         # install all workspaces
pnpm --filter @myorg/api run build   # run in specific package
pnpm -r run test                     # run in all packages recursively
```

#### CI Recommended Configuration

```yaml
# pnpm-workspace.yaml
minimumReleaseAge: "7 days"
trustPolicy: no-downgrade
onlyBuiltDependencies:
  - esbuild
```

```bash
pnpm install --frozen-lockfile
pnpm audit --audit-level=moderate
```

---

### Yarn

**Configuration files:** `.yarnrc.yml`, `package.json`

Yarn has two major release lines with different configuration formats:

- **Yarn Classic (v1):** uses `.yarnrc` (legacy, not recommended for new projects)
- **Yarn Berry (v2+):** uses `.yarnrc.yml` (all examples below are Berry)

#### Lockfile

Yarn generates `yarn.lock`. Commit it. In CI:

```bash
yarn install --immutable          # Berry: fail if lockfile would change
yarn install --frozen-lockfile    # Classic equivalent
```

#### Version Pinning

Standard `package.json` exact versioning applies. Set default in `.yarnrc.yml`:

```yaml
defaultSemverRangePrefix: ""   # installs exact versions by default (no ^ or ~)
```

#### Registry Configuration

```yaml
# .yarnrc.yml
npmRegistryServer: "https://your-registry.example.com/"

npmScopes:
  myorg:
    npmRegistryServer: "https://npm.pkg.github.com/"
    npmAuthToken: "${GITHUB_TOKEN}"

npmAuthToken: "${NPM_TOKEN}"
```

#### Security: Release Age Gate (Yarn ≥ 4.10.0)

Yarn 4.10.0 (September 2025) added `npmMinimalAgeGate`, a per-package minimum publication age enforced during `yarn add` and `yarn install`:

```yaml
# .yarnrc.yml

# Block any package version published within the last 7 days
npmMinimalAgeGate: 604800   # value is in seconds

# Common values (in seconds):
# 1 day   =   86400
# 3 days  =  259200
# 7 days  =  604800
# 14 days = 1209600
```

#### Security: Node Linker and PnP

Yarn Berry defaults to Plug'n'Play (PnP), which avoids `node_modules` and provides stricter dependency isolation:

```yaml
# .yarnrc.yml
nodeLinker: pnp          # default: Plug'n'Play (strictest)
nodeLinker: node-modules # fallback for compatibility
nodeLinker: pnpm         # use pnpm-style node_modules layout
```

#### Workspace / Monorepo

```json
// package.json (root)
{
  "workspaces": ["packages/*", "apps/*"]
}
```

```bash
yarn workspaces foreach run build   # run in all workspaces
yarn workspace @myorg/api run test  # run in specific workspace
```

#### CI Recommended Configuration

```yaml
# .yarnrc.yml
npmMinimalAgeGate: 604800   # 7 days
defaultSemverRangePrefix: ""
enableTelemetry: false
```

```bash
yarn install --immutable
yarn npm audit
```

---

### Bun

**Configuration files:** `bunfig.toml`, `package.json`

#### Lockfile

Bun generates `bun.lock` (text format). Commit it. In CI:

```bash
bun install --frozen-lockfile
```

#### Version Pinning

Standard `package.json` exact versioning. Set default in `bunfig.toml`:

```toml
[install]
exact = true   # save exact versions by default
```

#### Registry Configuration

```toml
# bunfig.toml
[install]
registry = "https://your-registry.example.com/"

[install.scopes]
"@myorg" = { registry = "https://npm.pkg.github.com/", token = "$GITHUB_TOKEN" }
```

#### Security: Minimum Release Age (Bun ≥ 1.3)

Bun 1.3 (October 2025) added `minimumReleaseAge` in `bunfig.toml`:

```toml
# bunfig.toml
[install]
minimumReleaseAge = "7d"

# Supported suffixes: m (minutes), h (hours), d (days), w (weeks)
# Examples:
# "24h"  = 1 day
# "3d"   = 3 days
# "1w"   = 7 days
```

#### Security: Lifecycle Scripts

```toml
# bunfig.toml
[install]
lifecycleScripts = false   # disable all postinstall/build scripts globally
```

Or allowlist specific packages that need to run scripts:

```toml
[install.trustedDependencies]
packages = ["esbuild", "@prisma/engines"]
```

#### Workspace / Monorepo

```json
// package.json (root)
{
  "workspaces": ["packages/*", "apps/*"]
}
```

```bash
bun install                   # installs all workspace deps
bun run --filter '*' build    # run in all workspaces
```

#### CI Recommended Configuration

```toml
# bunfig.toml
[install]
exact = true
minimumReleaseAge = "7d"
lifecycleScripts = false

[install.trustedDependencies]
packages = ["esbuild", "turbo"]
```

```bash
bun install --frozen-lockfile
```

---

## Python Ecosystem

### pip

**Configuration files:** `pip.conf` (Unix: `~/.config/pip/pip.conf`, Windows: `%APPDATA%\pip\pip.ini`), `requirements.txt`, `pyproject.toml` (via build backends)

#### Lockfile / Pinning

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

#### Registry / Index Configuration

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

#### Security: Upload-Time Filtering (pip ≥ 26.0)

pip 26.0 (January 2026) added `--uploaded-prior-to`, which restricts resolution to package versions uploaded before a given datetime (absolute ISO 8601 timestamps only):

```bash
# Only consider packages uploaded before this date
pip install -r requirements.txt \
  --uploaded-prior-to "2026-01-15T00:00:00Z"
```

> **Limitation:** `--uploaded-prior-to` accepts absolute timestamps only, not relative durations like "7 days ago." This makes it better suited as a reproducibility/snapshot tool than a rolling security cooldown. An open issue tracks adding relative duration support. For a sliding cooldown window, use uv instead.

#### Security: Disabling Network Access

```bash
pip install --no-index --find-links=/path/to/local/cache mypackage
```

Or enforce no-network in `pip.conf`:

```ini
[global]
no-index = true
find-links = /path/to/local/wheels
```

#### Dependency Auditing

```bash
pip install pip-audit
pip-audit                              # audit installed packages
pip-audit -r requirements.txt         # audit a requirements file
pip-audit --fix                        # auto-upgrade vulnerable packages
```

#### CI Recommended Configuration

```bash
pip install --require-hashes -r requirements.lock
pip-audit -r requirements.lock --audit-level=moderate
```

---

### uv

**Configuration files:** `pyproject.toml` (under `[tool.uv]`), `uv.toml`, `uv.lock`

uv is a fast Python package and project manager from Astral. It replaces pip, pip-tools, virtualenv, and Poetry for most use cases.

#### Lockfile

uv generates `uv.lock` — a universal, cross-platform lockfile with full transitive resolution. Always commit it.

```bash
uv sync                     # install from lockfile (creates if absent)
uv sync --frozen            # CI: fail if lockfile is out of date
uv lock                     # regenerate lockfile without installing
uv lock --check             # verify lockfile is up to date (CI check)
```

#### Version Pinning

In `pyproject.toml`, specify exact versions using `==`:

```toml
[project]
dependencies = [
  "requests==2.31.0",
  "fastapi==0.110.0",
]
```

For development dependencies:

```toml
[tool.uv]
dev-dependencies = [
  "pytest==8.1.0",
  "ruff==0.4.0",
]
```

#### Registry / Index Configuration

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

#### Security: Minimum Release Age / Cooldown (uv ≥ 0.9.17)

uv 0.9.17 (December 2025) added relative duration support to `exclude-newer`, enabling a rolling cooldown window. Set in `pyproject.toml`:

```toml
# pyproject.toml
[tool.uv]
exclude-newer = "7 days"

# Supported units: minutes, hours, days, weeks
# Examples: "24 hours", "3 days", "1 week"
```

This causes uv to ignore any package version published within the last 7 days when resolving dependencies.

Per-package overrides (allow a specific package to bypass the cooldown):

```toml
[tool.uv]
exclude-newer = "7 days"

[[tool.uv.package-overrides]]
name = "critical-security-fix"
exclude-newer = "0 days"   # bypass cooldown for this package
```

> **Known issue:** When `exclude-newer` is set to a relative duration, uv resolves it to an absolute timestamp and writes that timestamp into `uv.lock`. This can cause merge conflicts when multiple branches upgrade different packages. Tracked upstream at [astral-sh/uv#18708](https://github.com/astral-sh/uv/issues/18708).

#### Security: Hash Verification

```toml
# pyproject.toml
[tool.uv]
require-hashes = true        # all dependencies must have hash entries in lockfile
verify-hashes = true         # verify hashes at install time (default: true)
```

#### Security: Disabling Build Scripts

```toml
# pyproject.toml
[tool.uv]
no-build = true              # never build from source; wheels only
no-binary = ["somepackage"]  # force source build for specific package
```

#### Workspace / Monorepo

```toml
# pyproject.toml (workspace root)
[tool.uv.workspace]
members = ["packages/*", "services/*"]
```

```bash
uv sync --all-packages    # install all workspace packages
uv run --package myapi pytest  # run in specific workspace member
```

#### CI Recommended Configuration

```toml
# pyproject.toml
[tool.uv]
exclude-newer = "7 days"
require-hashes = true
```

```bash
uv sync --frozen
uv run pip-audit   # or: uvx pip-audit
```

---

## Go Modules

**Configuration files:** `go.mod`, `go.sum`, environment variables (set in shell profile or CI)

Go's module system is built into the `go` toolchain — there is no separate package manager to install.

#### go.mod and go.sum

`go.mod` declares the module path and all direct dependencies with minimum version requirements. `go.sum` records cryptographic hashes for all direct and transitive dependencies. Both files must be committed to source control.

```
// go.mod
module github.com/myorg/myapp

go 1.22

require (
    github.com/gin-gonic/gin v1.9.1
    github.com/jackc/pgx/v5 v5.5.4
)

require (
    // indirect dependencies managed automatically
    github.com/bytedance/sonic v1.11.2 // indirect
)
```

```bash
go mod tidy              # add missing, remove unused dependencies
go mod verify            # verify module hashes against go.sum
go mod download          # download all modules to local cache
```

#### Version Pinning

Dependency versions in `go.mod` are exact — Go uses Minimum Version Selection (MVS), which always resolves to the *minimum* version satisfying all constraints, never a newer one. This makes Go's resolution deterministic without needing a separate lockfile.

To pin to a specific version:

```bash
go get github.com/gin-gonic/gin@v1.9.1
```

To update a specific dependency:

```bash
go get -u github.com/gin-gonic/gin@latest   # update to latest
go get github.com/gin-gonic/gin@v1.10.0     # update to specific version
```

#### Checksum Database (GOSUMDB)

Go verifies all module downloads against `sum.golang.org` by default. This provides cryptographic integrity guarantees without requiring a lockfile.

```bash
# Disable checksum database (not recommended)
GONOSUMDB="github.com/my-private-repo/*"

# Use a custom checksum database
GOSUMDB="sum.golang.org"

# Bypass sum check entirely (use with caution)
GONOSUMCHECK="github.com/internal/*"
```

#### Module Proxy Configuration

By default, Go downloads modules through `proxy.golang.org`. Configure alternatives via `GOPROXY`:

```bash
# Default: try proxy, fall back to direct
GOPROXY="https://proxy.golang.org,direct"

# Private mirror or GOPROXY-compatible proxy
GOPROXY="https://your-proxy.example.com,direct"

# Disable proxy (fetch direct from VCS)
GOPROXY="direct"

# Offline mode only (use local cache)
GOPROXY="off"
```

Exclude specific modules from the proxy (e.g., private repos):

```bash
GOPRIVATE="github.com/myorg/*,gitlab.mycompany.com/*"
```

`GOPRIVATE` automatically sets both `GONOSUMDB` and `GONOPROXY` for the matched patterns.

#### Security: No Native Minimum Release Age

Go has no native time-delay or cooldown mechanism. The best available options are:

- **Dependabot `cooldown`:** Prevents automated dependency PRs from adopting versions published within a configurable window. Security update PRs automatically bypass the cooldown. Does not gate manual `go get` invocations.
- **Explicit version pinning in go.mod:** Never use `@latest` in production workflows; always pin explicit versions.
- **GONOSUMDB + private proxy:** Route Go module fetches through a controlled proxy where new versions can be reviewed before becoming available.

#### Vendoring

For air-gapped environments or extra reproducibility, vendor all dependencies:

```bash
go mod vendor                    # copy all dependencies into ./vendor/
go build -mod=vendor ./...       # build using only vendored modules
go test -mod=vendor ./...        # test using only vendored modules
```

In CI, enforce vendor directory is up to date:

```bash
go mod vendor
git diff --exit-code vendor/     # fail if vendor/ was modified
```

#### CI Recommended Configuration

```bash
# go.env or CI environment
GOPROXY="https://proxy.golang.org,direct"
GOPRIVATE="github.com/myorg/*"
GONOSUMDB="github.com/myorg/*"

# CI commands
go mod verify
go mod tidy
git diff --exit-code go.mod go.sum   # fail if go.mod/go.sum was modified
```

---

## Cargo (Rust)

**Configuration files:** `Cargo.toml`, `Cargo.lock`, `.cargo/config.toml`

#### Cargo.lock

Cargo always generates `Cargo.lock` for workspace/binary crates. **Always commit `Cargo.lock` for applications and binaries.** For libraries, the convention is to not commit it (so downstream users get fresh resolution), though committing it for internal libraries is reasonable.

```bash
cargo build                   # generates/updates Cargo.lock
cargo update                  # update all dependencies to latest compatible
cargo update --precise 1.0.1 -p serde  # update one dep to an exact version
```

In CI, use `--locked` to fail if `Cargo.lock` is out of sync with `Cargo.toml`:

```bash
cargo build --locked
cargo test --locked
```

#### Version Pinning

In `Cargo.toml`, use exact version requirements with `=`:

```toml
[dependencies]
serde = { version = "=1.0.196", features = ["derive"] }
tokio = { version = "=1.36.0", features = ["full"] }
reqwest = { version = "=0.11.27", features = ["json", "rustls-tls"] }
```

To update a single dependency to a precise version without accepting any semver-compatible alternatives:

```bash
cargo update --precise 1.0.197 -p serde
```

#### Registry Configuration

```toml
# .cargo/config.toml

[registry]
default = "my-registry"   # override default registry (default: crates.io)

[registries.my-registry]
index = "sparse+https://your-registry.example.com/index/"
# or git index:
# index = "https://your-registry.example.com/git/index"

[registries.crates-io]
token = "your-crates-io-token"   # or use CARGO_REGISTRY_TOKEN env var

[registries.my-registry]
token = "${MY_REGISTRY_TOKEN}"
```

Authentication via environment variables:

```bash
CARGO_REGISTRY_TOKEN="your-crates-io-token"
CARGO_REGISTRIES_MY_REGISTRY_TOKEN="your-internal-token"
```

#### Source Replacement

Source replacement redirects all fetches of one registry to another — useful for routing through an internal mirror without changing `Cargo.toml` files:

```toml
# .cargo/config.toml

[source.crates-io]
replace-with = "internal-mirror"

[source.internal-mirror]
registry = "sparse+https://your-mirror.example.com/index/"
```

All crates.io fetches now go through your mirror. Individual crate `Cargo.toml` files do not need to change.

#### Security: Minimum Release Age via cargo-cooldown

Cargo has no native cooldown feature. The `cargo-cooldown` crate (community tool, September 2025) wraps Cargo and enforces a configurable cooldown window before freshly published crates can enter your dependency graph:

```bash
cargo install cargo-cooldown

# Enforce a 7-day cooldown on all dependency resolution
cargo cooldown --days 7 build
cargo cooldown --days 7 test

# Or set a default cooldown in config
```

```toml
# .cargo/config.toml
[cooldown]
days = 7
```

> **Note:** `cargo-cooldown` is a community wrapper, not a native Cargo feature. Crates.io added a `pubtime` field to the registry index (providing publication timestamps) which enables this tooling, but native cooldown support in Cargo itself is not yet available.

#### Security: Cargo Audit

```bash
cargo install cargo-audit
cargo audit                           # audit Cargo.lock against RustSec advisory DB
cargo audit --deny warnings           # fail on any advisory (including informational)
cargo audit fix                       # attempt to auto-upgrade vulnerable dependencies
```

For CI integration:

```bash
cargo audit --json | jq '.vulnerabilities.found'
```

#### Security: Dependency Features and Build Scripts

Restrict unnecessary features to reduce attack surface:

```toml
[dependencies]
openssl = { version = "=0.10.64", features = [], default-features = false }
```

Disable build scripts for a specific dependency (use with caution — may break packages that require them):

```toml
# Cargo.toml
[patch.crates-io]
some-package = { path = "../patched-some-package" }
```

To audit which packages run build scripts:

```bash
cargo build --build-plan 2>/dev/null | jq '.invocations[].program'
```

#### Offline Mode

```bash
cargo build --offline    # use only locally cached crates
cargo fetch              # pre-fetch all dependencies (useful in CI setup step)
```

```toml
# .cargo/config.toml
[net]
offline = true   # always run offline
```

#### Workspace / Monorepo

```toml
# Cargo.toml (workspace root)
[workspace]
members = ["crates/*", "services/*"]
resolver = "2"   # use Cargo's v2 feature resolver (recommended)

[workspace.dependencies]
# Declare shared dependency versions once
serde = { version = "=1.0.196", features = ["derive"] }
tokio = { version = "=1.36.0", features = ["full"] }
```

Individual crates inherit from workspace:

```toml
# crates/mylib/Cargo.toml
[dependencies]
serde = { workspace = true }
tokio = { workspace = true }
```

```bash
cargo build --workspace          # build all workspace members
cargo test --workspace --locked  # test all members with lockfile
cargo update -p serde            # update one dep across entire workspace
```

#### CI Recommended Configuration

```toml
# .cargo/config.toml
[net]
retry = 3

[build]
jobs = 4   # parallelism
```

```bash
# CI commands
cargo fetch --locked
cargo build --locked --release
cargo test --locked
cargo audit --deny warnings
```

---

## Infrastructure as Code

Terraform and OpenTofu manage cloud infrastructure via *providers* (plugins that talk to APIs) and *modules* (reusable configuration bundles). Both are distributed through registries rather than language-specific package indexes, but the supply chain risks are similar: a compromised provider or module version can exfiltrate credentials, modify infrastructure state, or create backdoors.

### Terraform

**Configuration files:** `*.tf` files, `.terraform.lock.hcl`, `.terraformrc`

#### Lockfile

Terraform generates `.terraform.lock.hcl` on `terraform init`. Always commit it — it records exact provider versions and multi-platform cryptographic hashes, providing strong integrity guarantees.

```bash
terraform init              # creates/updates .terraform.lock.hcl
terraform init -upgrade     # re-resolves within constraints and updates lock
```

The lock file stores two hash schemes per provider:
- `zh:` — hash of the zip archive (populated from registry metadata on first init)
- `h1:` — hash of the extracted binary (added when actually installed on a platform)

For teams working across multiple OS/arch combinations, pre-populate hashes for all target platforms before committing:

```bash
# Pre-populate hashes for all platforms your team and CI use
terraform providers lock \
  -platform=linux_amd64 \
  -platform=linux_arm64 \
  -platform=darwin_amd64 \
  -platform=darwin_arm64 \
  -platform=windows_amd64
```

This prevents lock file churn from developers on different architectures each adding their platform's hashes.

#### Version Pinning

Terraform supports several version constraint operators in `required_providers` and module `version` arguments:

| Operator | Behaviour | Example |
|---|---|---|
| `=` | Exact version — use for maximum security | `= 5.31.0` |
| `~>` | Pessimistic — allows only rightmost component to increment | `~> 5.31.0` (patch only), `~> 5.31` (minor+patch) |
| `>=` | Minimum — any version at or above | `>= 5.0` |
| `>=, <` | Range — bounded minimum + maximum | `>= 5.0, < 6.0` |

For supply chain hardening, use `=` (exact) for providers in root modules. The `~>` operator is a reasonable compromise for modules that are consumed by others (where pinning too tightly creates friction for downstream users), but exact pinning is always safer for deployed infrastructure.

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.31.0"    # exact — recommended for root modules
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6.0"    # patch-only — acceptable for well-maintained providers
    }
  }
}
```

#### Security: No Native Minimum Release Age

Neither Terraform nor OpenTofu has a native cooldown or minimum release age mechanism. The best available options are:

- **Exact version pinning (`=`):** The strongest control — a provider version can only enter your infrastructure by an explicit change to `*.tf` files, which goes through code review.
- **Dependabot with cooldown:** See the caveat below — the cooldown feature has a known bug for Terraform providers.
- **Private registry mirror:** Route provider fetches through a controlled mirror where new versions can be reviewed before they become available.

#### Provider Signing

Providers installed from the Terraform Registry are signed with GPG keys. Terraform verifies these signatures during `terraform init`. Providers signed by HashiCorp or verified partners carry a trust chain; community providers are self-signed.

The lock file's hash values are derived from the signed package, so a tampered provider binary will produce a hash mismatch and fail to install. This is a strong integrity control, but it operates on trust-on-every-use from the registry's public key — a registry compromise would affect all downloads.

#### CI Configuration

```hcl
# Use -lockfile=readonly in CI to prevent accidental lock file updates
terraform init -lockfile=readonly
terraform plan
terraform apply
```

```ini
# .terraformrc — configure a network mirror for air-gapped or controlled environments
provider_installation {
  network_mirror {
    url     = "https://your-mirror.example.com/providers/"
    include = ["registry.terraform.io/*/*"]
  }
}
```

#### Dependabot

`.github/dependabot.yml` supports Terraform via the `terraform` ecosystem:

```yaml
version: 2
updates:
  - package-ecosystem: "terraform"
    directory: "/"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 7
      semver-major-days: 30
```

> **Known issue:** Dependabot's `cooldown` setting has a [documented bug for Terraform providers](https://github.com/dependabot/dependabot-core/issues/13715) — despite respecting the cooldown when selecting a version, it then re-runs `terraform lock` which upgrades to the latest available version. The cooldown constraint is effectively ignored for providers. Module updates (Git-sourced) are not affected. Exact pinning (`=`) in `required_providers` is the more reliable control until this is fixed.

#### Harden-Runner

```yaml
- uses: step-security/harden-runner@v2
  with:
    egress-policy: block
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      registry.terraform.io:443
      releases.hashicorp.com:443
      checkpoint-api.hashicorp.com:443
```

Add your cloud provider API endpoints (e.g. `*.amazonaws.com:443`) as needed for plan/apply steps.

---

### OpenTofu

**Configuration files:** `*.tf` or `*.tofu` files, `.terraform.lock.hcl`, `.tofurc`

OpenTofu is the open-source fork of Terraform maintained by the Linux Foundation. Its dependency management is largely identical to Terraform's, with a few meaningful differences.

#### What's the same

- `.terraform.lock.hcl` format — same file, same structure, same hash schemes (`h1:`, `zh:`)
- Version constraint syntax — `=`, `~>`, `>=`, `>=, <` work identically
- `tofu providers lock` for multi-platform hash pre-population (same flags as `terraform providers lock`)
- `-lockfile=readonly` flag in CI
- Dependabot support (added December 2025 via the `terraform` ecosystem — `.tofu` files are detected automatically)

#### What's different

**Registry and signing keys:** OpenTofu uses its own registry (`registry.opentofu.org`) with independent GPG signing keys. If you migrate a project from Terraform to OpenTofu, your `.terraform.lock.hcl` hashes will need to be regenerated — the same provider version will produce different hashes because the signing keys differ.

**Dependabot compatibility:** OpenTofu v1.8+ introduced early variable evaluation, which breaks Dependabot's version parsing. Projects on OpenTofu v1.8 or later may see Dependabot failures until this is resolved upstream.

**State encryption:** OpenTofu 1.7+ includes native client-side state encryption, reducing reliance on backend-level controls (e.g. S3 server-side encryption). This is not directly a provider/module supply chain feature, but it limits the blast radius of a compromised provider that attempts to exfiltrate state.

**SBOM support:** Under active development (RFC #2494) — OpenTofu's registry will support SBOM artifacts and provider attestations. Not yet available.

#### CI Recommended Configuration

```bash
# OpenTofu CI — mirrors Terraform best practices
tofu init -lockfile=readonly
tofu providers lock \
  -platform=linux_amd64 \
  -platform=darwin_arm64
tofu plan
```

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "terraform"   # covers both .tf and .tofu files
    directory: "/"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 7
      semver-major-days: 30
```

> **Note:** Apply the same Dependabot provider cooldown caveat from the Terraform section — the bug affects OpenTofu equally. Exact version pinning remains the more reliable control.

---

## Cross-Cutting Considerations

### Dependabot Integration

[Dependabot](https://docs.github.com/en/code-security/dependabot) is built into GitHub and supports a `cooldown` block across all package ecosystems covered in this document. It provides a consistent, PR-level holdback without requiring any additional tooling.

Configure cooldowns in `.github/dependabot.yml`. Each `updates` entry can have its own `cooldown` block with per-semver-level granularity:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30  # extra caution on breaking changes
      semver-minor-days: 7
      semver-patch-days: 3

  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7

  - package-ecosystem: "gomod"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30

  - package-ecosystem: "cargo"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
```

Per-package overrides using `include` and `exclude`:

```yaml
    cooldown:
      default-days: 7
      exclude:
        - dependency-name: "critical-security-dep"  # bypass cooldown for this package
      include:
        - dependency-name: "very-active-package"
          days: 14                                  # stricter cooldown for specific package
```

**Key behaviours to note:**

- Cooldown values must be between 1 and 90 days.
- **Security update PRs automatically bypass the cooldown** — a CVE-triggered Dependabot PR is never delayed, regardless of `cooldown` settings.
- Cooldown only gates automated version update PRs. A developer running `npm install foo` or `go get` locally bypasses it entirely.
- Supported for all ecosystems including npm, pip, gomod, cargo, NuGet, Helm, and more.

### Harden-Runner: Runtime CI Hardening

[Harden-Runner](https://github.com/step-security/harden-runner) is a GitHub Actions security agent that monitors and optionally blocks network egress, file integrity changes, and process activity on the runner during a workflow job. It operates at a different layer than version pinning and Dependabot cooldowns — those prevent malicious packages from entering your dependency graph, while Harden-Runner prevents malicious packages that *do* enter from exfiltrating secrets or calling home during `npm install`, `pip sync`, `go mod download`, or `cargo fetch`.

It is free for open source repositories.

#### Recommended Rollout: Audit First, Then Block

Start every new workflow in `audit` mode to observe what outbound connections are actually made during a normal build. After a week or two of clean runs, review the generated policy in the [StepSecurity portal](https://app.stepsecurity.io) and switch to `block` mode with an explicit allowlist.

```yaml
# .github/workflows/ci.yml
steps:
  - uses: step-security/harden-runner@v2
    with:
      egress-policy: audit   # start here; switch to 'block' once allowlist is stable
      disable-sudo: true     # prevent privilege escalation on the runner
```

#### Block Mode with Explicit Allowlists

Once the egress policy is stable, switch to `block` and enumerate only the endpoints your build actually needs. Examples per ecosystem:

**Node.js (npm / pnpm / yarn / bun):**

```yaml
- uses: step-security/harden-runner@v2
  with:
    egress-policy: block
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      registry.npmjs.org:443
      npm.pkg.github.com:443
```

**Python (pip / uv):**

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

**Go:**

```yaml
- uses: step-security/harden-runner@v2
  with:
    egress-policy: block
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      proxy.golang.org:443
      sum.golang.org:443
      storage.googleapis.com:443
```

**Cargo (Rust):**

```yaml
- uses: step-security/harden-runner@v2
  with:
    egress-policy: block
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      crates.io:443
      index.crates.io:443
      static.crates.io:443
```

#### Notes on Configuration

- `disable-sudo: true` prevents a compromised build step from escalating privileges to install persistent tooling on the runner. Safe for most workflows; disable only if your build genuinely requires sudo.
- The `allowed-endpoints` list is additive — add only what your build legitimately contacts. Any unlisted outbound connection is dropped in block mode, and an alert is raised.
- For private registries or GitHub Enterprise, add your registry hostname to the allowlist alongside the public endpoints.
- If using GitHub-hosted runners across multiple OSes, note that Harden-Runner supports Linux, macOS, and Windows runners with a unified policy view in the portal.
- The StepSecurity portal (`app.stepsecurity.io`) can auto-generate an `allowed-endpoints` policy from audit mode logs, which is the recommended way to build the initial allowlist rather than writing it by hand.

---

### Native Minimum Release Age Support Matrix

| Package Manager        | Native Support | Since        | Config Key                  | Relative Duration |
|------------------------|---------------|--------------|------------------------------|-------------------|
| pnpm                   | ✅ Yes         | v10.16 (Sep 2025) | `minimumReleaseAge`     | ✅ Yes            |
| Yarn Berry             | ✅ Yes         | v4.10 (Sep 2025)  | `npmMinimalAgeGate`     | ✅ Yes (seconds)  |
| Bun                    | ✅ Yes         | v1.3 (Oct 2025)   | `minimumReleaseAge`     | ✅ Yes            |
| npm                    | ✅ Yes         | v11.10 (Feb 2026) | `minimum-release-age`   | ✅ Yes (minutes)  |
| uv                     | ✅ Yes         | v0.9.17 (Dec 2025)| `exclude-newer`         | ✅ Yes            |
| pip                    | ⚠️ Partial    | v26.0 (Jan 2026)  | `--uploaded-prior-to`   | ❌ Absolute only  |
| Cargo                  | ❌ No         | —            | (use `cargo-cooldown`)       | —                 |
| Go modules             | ❌ No         | —            | (use Dependabot or proxy)    | —                 |
| Terraform / OpenTofu   | ❌ No         | —            | (use exact `=` pins + Dependabot²) | —          |

---

### Version Constraint Support

Loose version constraints are one of the most common vectors for supply chain attacks. When a manifest allows a range (`^1.0.0`, `>=1.0.0`, `~=1.0`), any newly published version matching that range can be silently pulled in — particularly during fresh installs, dependency updates, or CI runs that don't enforce a lockfile. A compromised maintainer account publishing `1.0.1` with malicious code will satisfy `^1.0.0` in every consuming project that doesn't pin exactly.

The lockfile provides a partial mitigation — it pins exact resolved versions — but it only protects you when it is actively enforced (e.g. `npm ci`, `uv sync --frozen`). A developer running a bare `npm install` or `pip install -r requirements.txt` against a loose manifest will re-resolve within the allowed range and can pull in a version the lockfile never saw.

| Package Manager | Default Constraint | Loose Syntax (avoid) | Exact Syntax (use) | Lockfile pins exact? | Enforce exact via |
|---|---|---|---|---|---|
| npm | `^` (minor+patch) | `^1.0.0` `~1.0.0` `>=1.0.0` `*` | `1.0.0` | ✅ Yes — `npm ci` enforces it | `save-exact=true` in `.npmrc` |
| pnpm | `^` (minor+patch) | `^1.0.0` `~1.0.0` `>=1.0.0` | `1.0.0` | ✅ Yes — `--frozen-lockfile` | `save-exact=true` in `.npmrc` |
| Yarn Berry | `^` (minor+patch) | `^1.0.0` `~1.0.0` `>=1.0.0` | `1.0.0` | ✅ Yes — `--immutable` | `defaultSemverRangePrefix: ""` in `.yarnrc.yml` |
| Bun | `^` (minor+patch) | `^1.0.0` `~1.0.0` `>=1.0.0` | `1.0.0` | ✅ Yes — `--frozen-lockfile` | `exact = true` in `bunfig.toml` |
| pip | None (user-specified) | `>=1.0.0` `~=1.0.0` `!=1.0.0` | `==1.0.0` | ❌ No native lockfile | `pip-compile --generate-hashes`; always use `==` |
| uv | None (user-specified) | `>=1.0.0` `~=1.0.0` | `==1.0.0` | ✅ Yes — `uv sync --frozen` | `require-hashes = true` in `[tool.uv]` |
| Go modules | MVS minimum¹ | `@latest` `@master` | `@v1.9.1` | ✅ Yes — `go.sum` hashes | Never use `@latest`; always specify a tagged version |
| Cargo | `^` (caret, implicit) | `1.0.0` `^1.0.0` `~1.0.0` `>=1.0.0` | `=1.0.0` | ✅ Yes — `--locked` | Use `=` prefix explicitly in `Cargo.toml` |
| Terraform / OpenTofu | `~>` (patch-only by default²) | `~> 5.0` `>= 5.0` `>= 5.0, < 6.0` | `= 5.31.0` | ✅ Yes — `.terraform.lock.hcl`; `-lockfile=readonly` | Use `= X.Y.Z` in `required_providers`; run `terraform providers lock` for multi-platform hashes |

**¹ Go's Minimum Version Selection (MVS)** works differently from other package managers. A `require` directive specifies the *minimum acceptable version*, and Go always resolves to that exact version (never newer) unless you explicitly run `go get -u`. This makes Go more conservative by default — it will not silently adopt new versions without an explicit developer action. However, `go get -u` and `go get @latest` bypass this safety and should be avoided in favour of pinning explicit tagged versions.

**² Terraform / OpenTofu `~>` semantics:** The pessimistic constraint `~> 5.0` allows any `5.x` release (equivalent to `>= 5.0, < 6.0`), while `~> 5.31.0` allows only `5.31.x` patch releases. Neither form is as restrictive as exact pinning. Unlike other ecosystems there is also no native cooldown — the `.terraform.lock.hcl` lockfile records hashes of the resolved version but does not prevent automatic adoption of new versions when `terraform init -upgrade` is run or when Dependabot opens a PR. Exact pinning with `= 5.31.0` is the only reliable defence. Note: Dependabot cooldown for the `terraform` ecosystem is affected by a known bug (GitHub issue [#13715](https://github.com/dependabot/dependabot-core/issues/13715)) that may prevent provider updates from respecting cooldown days — use exact pinning as the primary control.

**Key observation:** For Node.js tools, Cargo, and uv, the lockfile is a strong control *only when actively enforced*. If CI runs `npm install` instead of `npm ci`, or if a developer installs a new dependency on a workstation without committing the updated lockfile, the loose constraint in the manifest becomes the effective policy. Exact pinning in the manifest eliminates this residual risk regardless of how install commands are invoked.

---

## Reference Links

- [npm Documentation](https://docs.npmjs.com/)
- [pnpm Supply Chain Security](https://pnpm.io/supply-chain-security)
- [pnpm Settings Reference](https://pnpm.io/settings)
- [Yarn Berry Configuration](https://yarnpkg.com/configuration/yarnrc)
- [Bun Configuration](https://bun.sh/docs/runtime/bunfig)
- [pip Documentation](https://pip.pypa.io/en/stable/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [Go Modules Reference](https://go.dev/ref/mod)
- [Cargo Configuration Reference](https://doc.rust-lang.org/cargo/reference/config.html)
- [Cargo Source Replacement](https://doc.rust-lang.org/cargo/reference/source-replacement.html)
- [Dependabot Options Reference](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
- [Dependabot Cooldown Announcement](https://github.blog/changelog/2025-07-01-dependabot-supports-configuration-of-a-minimum-package-age/)
- [Harden-Runner on GitHub](https://github.com/step-security/harden-runner)
- [Harden-Runner Documentation](https://docs.stepsecurity.io/harden-runner)
- [Harden-Runner on GitHub Marketplace](https://github.com/marketplace/actions/harden-runner)
- [cargo-cooldown](https://crates.io/crates/cargo-cooldown)
- [Terraform Provider Requirements](https://developer.hashicorp.com/terraform/language/providers/requirements)
- [Terraform Dependency Lock File](https://developer.hashicorp.com/terraform/language/files/dependency-lock)
- [Terraform Version Constraints](https://developer.hashicorp.com/terraform/language/expressions/version-constraints)
- [OpenTofu Provider Requirements](https://opentofu.org/docs/language/providers/requirements/)
- [OpenTofu Dependency Lock File](https://opentofu.org/docs/language/files/dependency-lock/)
- [OpenTofu vs Terraform Differences](https://opentofu.org/docs/intro/migration/)
- [Dependabot Terraform Ecosystem Docs](https://docs.github.com/en/code-security/dependabot/ecosystems-supported-by-dependabot/supported-package-ecosystems#terraform)
- [Package Managers Need to Cool Down (Andrew Nesbitt)](https://nesbitt.io/2026/03/04/package-managers-need-to-cool-down.html)
