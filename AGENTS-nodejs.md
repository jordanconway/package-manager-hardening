# Agent Instructions: Node.js Dependency Management

This file contains mandatory guidelines for managing dependencies in this Node.js project. Follow these rules whenever adding, updating, or removing packages, or modifying CI configuration.

## Package Manager

This project uses: <!-- npm | pnpm | yarn | bun — delete as appropriate -->

## Dependency Rules

**Always pin exact versions.** Never use `^` or `~` prefixes in `package.json`. Every dependency and devDependency must specify an exact version string.

```json
// correct
"express": "4.18.2"

// incorrect — do not use
"express": "^4.18.2"
"express": "~4.18.2"
```

**Never add a package that was published within the last 7 days.** Check the publication date on the registry before adding any new dependency. If a package was published less than 7 days ago, defer the addition until the cooldown has elapsed.

**Always commit the lockfile.** `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, or `bun.lock` must be committed. Never add lockfiles to `.gitignore`.

**Never run install commands that bypass the lockfile in CI.** Use the strict install command for this project's package manager:

- npm: `npm ci`
- pnpm: `pnpm install --frozen-lockfile`
- Yarn Berry: `yarn install --immutable`
- Bun: `bun install --frozen-lockfile`

## Configuration to Verify

When modifying dependency configuration, verify the following are in place:

**For npm** (`.npmrc`):
```ini
save-exact=true
minimum-release-age=10080
audit=true
fund=false
```

**For pnpm** (`pnpm-workspace.yaml`):
```yaml
minimumReleaseAge: "7 days"
trustPolicy: no-downgrade
onlyBuiltDependencies:
  # list only packages that legitimately need build scripts
```

**For Yarn Berry** (`.yarnrc.yml`):
```yaml
defaultSemverRangePrefix: ""
npmMinimalAgeGate: 604800
```

**For Bun** (`bunfig.toml`):
```toml
[install]
exact = true
minimumReleaseAge = "7d"
lifecycleScripts = false
```

## Security Audit

Run a vulnerability audit whenever dependencies change:

```bash
# npm / pnpm / yarn / bun
npm audit --audit-level=moderate
pnpm audit --audit-level=moderate
yarn npm audit
```

If the audit reports vulnerabilities, do not merge the change until they are resolved or explicitly acknowledged with a documented justification.

## CI Configuration

### Dependabot

`.github/dependabot.yml` must include a cooldown for this ecosystem. If the file does not exist or lacks a cooldown block, add it:

```yaml
version: 2
updates:
  - package-ecosystem: "npm"
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
      registry.npmjs.org:443
```

Add `npm.pkg.github.com:443` to `allowed-endpoints` if this project uses GitHub Packages.

## What Requires Human Review

The following changes must not be made autonomously and require explicit human approval before proceeding:

- Adding a new dependency with no prior version in the lockfile
- Upgrading a major version (`x.0.0` → `y.0.0`)
- Disabling or removing `minimum-release-age`, `minimumReleaseAge`, or `npmMinimalAgeGate`
- Adding a package to `onlyBuiltDependencies` or `trustedDependencies`
- Modifying `.github/dependabot.yml` cooldown values downward
- Removing or modifying Harden-Runner from a workflow
