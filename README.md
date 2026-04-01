# Package Manager Configuration Reference

A comprehensive reference for configuring npm, pnpm, Yarn, Bun, pip, uv, Go modules, and Cargo — covering lockfiles, version pinning, registry configuration, security hardening, and CI/CD usage.

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
- [cargo-cooldown](https://crates.io/crates/cargo-cooldown)
- [Package Managers Need to Cool Down (Andrew Nesbitt)](https://nesbitt.io/2026/03/04/package-managers-need-to-cool-down.html)
