<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Node.js Ecosystem

## npm

**Configuration files:** `.npmrc` (per-project or global at `~/.npmrc`), `package.json`

### Lockfile

npm generates `package-lock.json` on install. Commit this file to source control. In CI, always use `npm ci` instead of `npm install` — it installs strictly from the lockfile and fails if the lockfile is out of sync with `package.json`.

> **The lockfile itself is an attack surface.** A malicious PR can edit a `resolved` URL to point at an attacker-controlled artifact, with a matching `integrity` hash — and `npm ci` will faithfully install it. See [Lockfile Integrity](lockfile-integrity.md) for the attack and mitigations (`lockfile-lint`, `npm audit signatures`, egress control).

```bash
npm ci                   # strict lockfile install (CI)
npm install              # resolves and updates lockfile
```

> **`npm install --frozen-lockfile` is not an npm flag.** It belongs to pnpm, Yarn Classic and Bun. npm 10 ignores it silently, npm 11 warns and still rewrites `package-lock.json`, and npm 12 rejects it. `npm ci` is the only npm command that fails on a lockfile mismatch.

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
# Block packages published within the last 7 days.
# The value is a number of DAYS.
min-release-age=7
```

> **The key is `min-release-age`, in days.** `minimum-release-age` is pnpm 10's `.npmrc` spelling (in minutes) and is not an npm setting: npm warns `Unknown project config "minimum-release-age"` and applies no gate. Do not carry a minutes value across either — `min-release-age=10080` is a 27-year window. Verify with `npm config get min-release-age`.
>
> **Choose `min-release-age` *or* a Dependabot `npm` cooldown — not both.** They are the same release-age control at different layers, and the resolver-level one has no security-update exception, so combining them blocks Dependabot's automated security updates. For most repositories, prefer the Dependabot cooldown and omit `min-release-age`; use the resolver-level gate only when you need transitive/local-install coverage. See [Cooldown: resolver-level vs Dependabot](dependabot.md#cooldown-resolver-level-vs-dependabot--pick-one).

### Security: Audit and Signatures

```bash
npm audit                      # check for known vulnerabilities
npm audit fix                  # auto-fix where possible
npm audit --audit-level=high   # fail CI only on high/critical

# Verify registry signatures and provenance attestations for every
# package in the tree (direct and transitive). Fails if any installed
# artifact has a missing or invalid signature, or if a package that
# publishes provenance has an attestation that doesn't verify.
npm audit signatures
```

`npm audit signatures` complements the lockfile's integrity hashes: the lockfile proves the artifact didn't change since it was locked, while signature verification proves the artifact is the one the registry actually published. A tampered lockfile entry pointing at a look-alike artifact passes hash verification (the hash was recorded from the tampered artifact) but fails signature verification. Run it in CI after `npm ci`.

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
min-release-age=7
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
minimumReleaseAge: 10080   # minutes (7 days)

# Common values (in minutes):
# 1 day   =  1440
# 3 days  =  4320
# 7 days  = 10080
# 14 days = 20160
```

> **The value is a bare number of minutes.** Duration strings such as `"7 days"` are not supported: depending on the pnpm version they are a parse error (pnpm 12), break every install, or leave the gate ineffective. pnpm 11 and later default to `1440` (1 day) when the setting is absent.

Per-package exclusions (pnpm ≥ 10.16):

```yaml
minimumReleaseAge: 10080
minimumReleaseAgeExclude:
  - typescript          # always allow latest TypeScript
  - "@myorg/*"          # exclude internal packages
```

### Security: Trust Policy (pnpm ≥ 10.21)

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

Skip the trust-policy check (not the release-age check) for versions published long ago (pnpm ≥ 10.27). Like `minimumReleaseAge`, the value is a number of minutes:

```yaml
trustPolicy: no-downgrade
trustPolicyIgnoreAfter: 525600   # minutes (1 year)
```

### Security: Build Script Control

pnpm v10 no longer runs lifecycle scripts (postinstall, etc.) from dependencies by default unless explicitly allowed. Configure which packages may run build scripts with `allowBuilds` (pnpm ≥ 10.26):

```yaml
# pnpm-workspace.yaml
allowBuilds:
  esbuild: true
  "@prisma/engines": true
  node-gyp: true
  some-suspicious-package: false   # reviewed and denied
```

> **pnpm 11 removed `onlyBuiltDependencies` and `ignoredBuiltDependencies`** in favour of `allowBuilds`. On pnpm 11 and later the old keys are ignored, and because `strictDepBuilds` now defaults to `true`, an install with an unreviewed build script fails with `ERR_PNPM_IGNORED_BUILDS`. `allowBuilds` works on pnpm 10.26 and later, so prefer it everywhere; only pnpm older than 10.26 still needs the old keys.

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
minimumReleaseAge: 10080   # minutes (7 days)
trustPolicy: no-downgrade
allowBuilds:
  esbuild: true
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
npmMinimalAgeGate: 10080   # value is in minutes

# Common values (in minutes):
# 1 day   =  1440
# 3 days  =  4320
# 7 days  = 10080
# 14 days = 20160
```

> **A bare number is minutes, not seconds.** `604800` is a 420-day gate: installs still succeed, but Yarn quietly resolves to versions more than a year old. Yarn ≥ 4.11 also accepts duration strings (`"7d"`, `"1w"`); the bare number works on every release from 4.10. `audit.py` reports a bare value above `43200` (30 days) as `suspect_value` and downgrades the cooldown check to a warning; write a deliberately long gate as a duration string (`"60d"`).

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
npmMinimalAgeGate: 10080   # minutes (7 days)
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
minimumReleaseAge = 604800   # seconds (7 days)

# Common values (in seconds):
# 1 day   =   86400
# 3 days  =  259200
# 7 days  =  604800
# 14 days = 1209600
```

> **Use a number of seconds.** Bun 1.3.0 through 1.4.3 reject a string value (`Expected number of seconds for minimumReleaseAge`), which fails every `bun install`. Duration strings such as `"7d"` are only accepted from Bun 1.4.4.

### Security: Lifecycle Scripts

By default Bun does not run lifecycle scripts for dependencies, **except** for a built-in list of several hundred default-trusted packages. Your own project's scripts always run. There are two controls, and they live in different files.

Replace the default trust list with an explicit allowlist in `package.json`:

```json
{
  "trustedDependencies": ["esbuild", "@prisma/engines"]
}
```

Defining `trustedDependencies` replaces Bun's default list rather than extending it, so only the packages you name may run scripts. Set it to `[]` to trust none.

Or disable every lifecycle script, including your own project's and those of trusted packages:

```toml
# bunfig.toml
[install]
ignoreScripts = true
```

> **`lifecycleScripts` and `[install.trustedDependencies]` are not bunfig settings.** Bun ignores both without warning. The script switch is `ignoreScripts`, and `trustedDependencies` is only read from `package.json`. With `ignoreScripts = true`, the allowlist has no effect.

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
minimumReleaseAge = 604800   # seconds (7 days)
```

```json
// package.json — replaces Bun's default trusted list
{
  "trustedDependencies": ["esbuild", "turbo"]
}
```

```bash
bun install --frozen-lockfile
```

---
