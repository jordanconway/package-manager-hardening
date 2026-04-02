# Node.js Ecosystem


## npm

**Configuration files:** `.npmrc` (per-project or global at `~/.npmrc`), `package.json`

### Lockfile

npm generates `package-lock.json` on install. Commit this file to source control. In CI, always use `npm ci` instead of `npm install` — it installs strictly from the lockfile and fails if the lockfile is out of sync with `package.json`.

```bash
npm ci                   # strict lockfile install (CI)
npm install              # resolves and updates lockfile
npm install --frozen-lockfile  # alias: fails if lockfile would change
```

### Version Pinning

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

### Registry Configuration

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

### Security: Minimum Release Age (npm ≥ 11.10.0)

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

### Security: Audit and Signatures

```bash
npm audit                      # check for known vulnerabilities
npm audit fix                  # auto-fix where possible
npm audit --audit-level=high   # fail CI only on high/critical

# Verify package provenance (requires registry support)
npm install --foreground-scripts
```

### Workspace / Monorepo

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

### CI Recommended Configuration

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

## pnpm

**Configuration files:** `pnpm-workspace.yaml`, `.npmrc`, `package.json`

### Lockfile

pnpm generates `pnpm-lock.yaml`. Always commit it. In CI use `--frozen-lockfile`:

```bash
pnpm install --frozen-lockfile
```

### Version Pinning

Same `package.json` semantics as npm. Set exact pinning in `.npmrc`:

```ini
save-exact=true
```

### Registry Configuration

```ini
# .npmrc
registry=https://your-registry.example.com/
@myorg:registry=https://npm.pkg.github.com/
//npm.pkg.github.com/:_authToken=${GITHUB_TOKEN}
```

### Security: Minimum Release Age (pnpm ≥ 10.16)

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

### Security: Trust Policy (pnpm ≥ 10.0)

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

### Security: Build Script Control

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

### Workspace / Monorepo

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

### CI Recommended Configuration

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

## Yarn Classic

**Configuration files:** `.yarnrc`, `package.json`

Yarn Classic (v1) is the original Yarn release. It is in maintenance mode and not recommended for new projects — use Yarn Berry instead. Configuration lives in `.yarnrc` (not `.yarnrc.yml`).

### Lockfile

Yarn Classic generates `yarn.lock`. Commit it. In CI:

```bash
yarn install --frozen-lockfile    # fail if lockfile would change
```

### Version Pinning

Standard `package.json` exact versioning applies — remove `^` and `~` prefixes manually, as Classic has no built-in exact-pin flag.

### Registry Configuration

```ini
# .yarnrc
registry "https://your-registry.example.com/"
"@myorg:registry" "https://npm.pkg.github.com/"
```

---

## Yarn Berry

**Configuration files:** `.yarnrc.yml`, `package.json`

Yarn Berry (v2+) is the actively developed release line. All security features (`npmMinimalAgeGate`, PnP, scoped registry auth) are Berry-only. Configuration lives in `.yarnrc.yml`.

### Lockfile

Yarn Berry generates `yarn.lock`. Commit it. In CI:

```bash
yarn install --immutable   # fail if lockfile would change
```

### Version Pinning

Set exact pinning as the default in `.yarnrc.yml`:

```yaml
defaultSemverRangePrefix: ""   # installs exact versions by default (no ^ or ~)
```

### Registry Configuration

```yaml
# .yarnrc.yml
npmRegistryServer: "https://your-registry.example.com/"

npmScopes:
  myorg:
    npmRegistryServer: "https://npm.pkg.github.com/"
    npmAuthToken: "${GITHUB_TOKEN}"

npmAuthToken: "${NPM_TOKEN}"
```

### Security: Release Age Gate (Yarn ≥ 4.10.0)

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

### Security: Node Linker and PnP

Yarn Berry defaults to Plug'n'Play (PnP), which avoids `node_modules` and provides stricter dependency isolation:

```yaml
# .yarnrc.yml
nodeLinker: pnp          # default: Plug'n'Play (strictest)
nodeLinker: node-modules # fallback for compatibility
nodeLinker: pnpm         # use pnpm-style node_modules layout
```

### Workspace / Monorepo

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

### CI Recommended Configuration

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

## Bun

**Configuration files:** `bunfig.toml`, `package.json`

### Lockfile

Bun generates `bun.lock` (text format). Commit it. In CI:

```bash
bun install --frozen-lockfile
```

### Version Pinning

Standard `package.json` exact versioning. Set default in `bunfig.toml`:

```toml
[install]
exact = true   # save exact versions by default
```

### Registry Configuration

```toml
# bunfig.toml
[install]
registry = "https://your-registry.example.com/"

[install.scopes]
"@myorg" = { registry = "https://npm.pkg.github.com/", token = "$GITHUB_TOKEN" }
```

### Security: Minimum Release Age (Bun ≥ 1.3)

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

### Security: Lifecycle Scripts

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

### Workspace / Monorepo

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

### CI Recommended Configuration

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

