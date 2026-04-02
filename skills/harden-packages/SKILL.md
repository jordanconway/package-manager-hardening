---
name: harden-packages
description: >
  Audit and harden package manager security configuration in a software repository.
  Use this skill whenever the user wants to: audit dependency security, check package
  manager hardening, apply supply chain security best practices, set up Dependabot
  cooldowns, configure Harden-Runner in GitHub Actions, pin dependency versions, add
  lockfiles, configure minimum release age, check for unpinned dependencies, or
  review CI/CD pipeline security. Also trigger when the user says things like "harden
  my repo", "check my dependencies", "is my package config secure?", "set up supply
  chain security", "add Dependabot", or "are my packages safe?". Works across Node.js
  (npm/pnpm/yarn/bun), Python (pip/uv), Go, Rust/Cargo, PHP/Composer, and Terraform/OpenTofu repos.
---

# Package Manager Hardening Skill

You are auditing and hardening a software repository's dependency management against
supply chain attack risk. Your job is to detect gaps, explain why each matters, and
— with the user's consent — fix them.

## Step 1: Detect the stack

Scan the repo to identify which ecosystems are present:

| Signal files | Ecosystem |
|---|---|
| `package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lock` | Node.js |
| `pyproject.toml`, `requirements.txt`, `uv.lock`, `requirements.lock` | Python |
| `go.mod`, `go.sum` | Go |
| `Cargo.toml`, `Cargo.lock` | Rust |
| `composer.json`, `composer.lock` | PHP / Composer |
| `*.tf` files containing `required_providers` or `terraform {` blocks | Terraform / OpenTofu |
| `.terraform.lock.hcl` | Terraform / OpenTofu |

Also check:
- `.github/dependabot.yml` — is Dependabot configured?
- `.github/workflows/*.yml` — are any CI workflows present? Is Harden-Runner present?
- For Terraform/OpenTofu: note whether the CLI is `terraform` or `tofu` (check workflow files and `.tool-versions` / `.terraform-version`)

## Step 2: Audit each ecosystem

For each detected ecosystem, check the items below. Track every finding as either
✅ (good), ⚠️ (present but misconfigured), or ❌ (missing).

### Node.js (npm / pnpm / yarn / bun)

**Lockfile**
- Is `package-lock.json` / `pnpm-lock.yaml` / `yarn.lock` / `bun.lock` present?
- Is it listed in `.gitignore`? (bad — it should be committed)

**Version pinning**
- Do `dependencies` and `devDependencies` in `package.json` use exact versions (no `^` or `~`)?

**Minimum release age**
- npm ≥ 11.10: is `minimum-release-age` set in `.npmrc`? (recommended: 10080 = 7 days)
- pnpm ≥ 10.16: is `minimumReleaseAge` set in `pnpm-workspace.yaml`? (recommended: `"7 days"`)
- pnpm ≥ 10.0: is `trustPolicy: no-downgrade` set in `pnpm-workspace.yaml`?
- Yarn Berry ≥ 4.10: is `npmMinimalAgeGate` set in `.yarnrc.yml`? (recommended: 604800)
- Bun ≥ 1.3: is `minimumReleaseAge` set in `bunfig.toml`? (recommended: `"7d"`)

**Build script control**
- pnpm: is `onlyBuiltDependencies` set (allowlist) or `ignoredBuiltDependencies` used?
- Bun: is `lifecycleScripts = false` set with an explicit `trustedDependencies` allowlist?

**CI install command**
- Does CI use the strict/frozen install command (`npm ci`, `pnpm install --frozen-lockfile`, `yarn install --immutable`, `bun install --frozen-lockfile`)?

### Python (pip / uv)

**Lockfile**
- uv: is `uv.lock` present and not gitignored?
- pip: is there a compiled `requirements.lock` (from pip-compile) with hashes?

**Version pinning**
- Are all entries in `pyproject.toml` / `requirements.txt` using `==` (not `>=`, `~=`, or unpinned)?

**Minimum release age / cooldown**
- uv ≥ 0.9.17: is `exclude-newer` set in `[tool.uv]`? (recommended: `"7 days"`)
- uv: are `require-hashes` and `verify-hashes` both `true` in `[tool.uv]`?

**CI install command**
- uv: does CI use `uv sync --frozen`?
- pip: does CI use `pip install --require-hashes -r requirements.lock`?

### Go

**go.mod and go.sum**
- Are both `go.mod` and `go.sum` present?
- Are they gitignored? (bad)

**Version pinning**
- Are all `require` entries in `go.mod` using explicit tagged versions (not `@latest` or `@master`)?

**Checksum database**
- Is `GONOSUMDB` or `GONOSUMCHECK` set to `*` (disabling sum checks for all modules)? (bad)
- Is `GOPRIVATE` / `GONOSUMDB` scoped only to internal/private modules?

**CI verification**
- Does CI run `go mod verify` and `go mod tidy` followed by a `git diff --exit-code go.mod go.sum` check?
- Does CI run `govulncheck ./...`?

### Rust / Cargo

**Cargo.lock**
- Is `Cargo.lock` present?
- For a binary/application: is it committed (not gitignored)?

**Version pinning**
- Do `Cargo.toml` dependencies use `=` exact version syntax?

**Cooldown**
- Is `cargo-cooldown` configured in `.cargo/config.toml` with `[cooldown] days = 7`?

**CI**
- Does CI use `--locked` flag on `cargo build` and `cargo test`?
- Does CI run `cargo audit --deny warnings`?

### PHP / Composer

**Lockfile**
- Is `composer.lock` present and committed (not gitignored)?

**Version pinning**
- Do all `require` entries in `composer.json` use exact version strings (not `^`, `~`, `>=`, or `*`)?

**Composer version**
- Is Composer 2.7 or later in use? (Check workflow files or `composer --version`)

**Vulnerability auditing**
- Does CI run `composer audit --locked`?
- Is `roave/security-advisories:dev-latest` present as a dev dependency?

**Build script control**
- Does CI use `--no-scripts --no-plugins` with `composer install`?
- Does CI use `--prefer-dist`?

**CI install pattern**
- Is `COMPOSER_NO_INTERACTION=1` set in CI?
- Does CI use `composer install` (not `composer update`)?

### Terraform / OpenTofu

**Lockfile**
- Is `.terraform.lock.hcl` present in each root module directory?
- Is it gitignored? (bad — it must be committed)
- Does it contain entries for all platforms used in CI (check `h1:` hash entries per platform)?

**Version pinning**
- Do all `required_providers` blocks use exact `=` version constraints (not `~>`, `>=`, or open ranges)?
- Is `required_version` set for the CLI itself, and does it use `=` (not `~>` or `>=`)?
- Do all `module` source references that use a registry module pin to an exact `version = "= X.Y.Z"`?
- Do Git-sourced modules pin to a specific tag (not `ref=main` or `ref=master`)?

**Multi-platform hash pre-population**
- Does the lockfile contain `h1:` hashes for all platforms where `terraform init` runs (dev machines + CI)?
- If not, the team should run `terraform providers lock -platform=linux/amd64 -platform=darwin/arm64` (etc.) and commit the result.

**CLI lockfile enforcement**
- Does CI use `-lockfile=readonly` with `terraform init` / `tofu init`?

**OpenTofu-specific (if applicable)**
- Is the project on OpenTofu ≥ 1.8 if Dependabot is configured? (v1.8 is required for Dependabot support)
- Is state encryption configured via `encryption {}` blocks? (OpenTofu feature — flag if missing)

### Dependabot

For each detected ecosystem, check `.github/dependabot.yml`:
- Is there an `updates` entry for this ecosystem?
- Does it have a `cooldown` block with `default-days` ≥ 1?
- Are `semver-major-days` set higher than `semver-minor-days` and `semver-patch-days`?
- **Terraform note:** The `terraform` ecosystem has a known Dependabot bug ([#13715](https://github.com/dependabot/dependabot-core/issues/13715)) where provider cooldowns may not be respected. Flag this as ⚠️ even if a cooldown is configured, and recommend exact `=` pinning as the primary control.

### Harden-Runner

For each workflow file in `.github/workflows/`:
- Is `step-security/harden-runner@v2` the first step in every job that installs dependencies?
- Is `egress-policy` set to `block` (not just `audit`)?
- Is `disable-sudo: true` set?
- Is `allowed-endpoints` defined?

## Step 3: Report findings

Present a structured audit report grouped by ecosystem. For each item use the ✅ / ⚠️ / ❌ markers. After the checklist, give a short prioritised summary: what poses the most supply chain risk right now, and what's quick to fix vs requires more thought.

Keep the explanations grounded — don't list every possible issue for issues that are fine. Focus on what's actually wrong or missing.

Example report structure:

```
## Hardening Audit: [repo name]

### Stack detected
- Node.js (pnpm)
- Python (uv)
- CI: 2 workflow files

### Node.js (pnpm)
✅ pnpm-lock.yaml committed
✅ minimumReleaseAge: "7 days" set
❌ trustPolicy not set — a compromised version that drops provenance won't be blocked
⚠️ onlyBuiltDependencies not configured — all installed packages can run postinstall scripts

### Python (uv)
✅ uv.lock committed
✅ exclude-newer = "7 days"
❌ require-hashes not set — packages are not hash-verified on install

### Dependabot
✅ npm cooldown configured (7/30/7/3 days)
❌ pip ecosystem missing from dependabot.yml

### GitHub Actions
⚠️ ci.yml: harden-runner present but egress-policy is "audit", not "block"
❌ release.yml: harden-runner not present

### Priority fixes
1. Add harden-runner to release.yml — release workflows are high-value targets
2. Set egress-policy: block in ci.yml once allowlist is confirmed
3. Add require-hashes = true to [tool.uv]
4. Add pip entry to dependabot.yml
5. Set trustPolicy: no-downgrade in pnpm-workspace.yaml
```

## Step 4: Offer to fix

After the report, ask: "Would you like me to apply the fixes? I can handle all of them, or you can tell me which ones to skip."

If the user agrees (fully or partially), apply the fixes in this order — lower risk / non-breaking changes first:

1. `pnpm-workspace.yaml` / `.npmrc` / `.yarnrc.yml` / `bunfig.toml` — add missing cooldown / trust policy config
2. `pyproject.toml [tool.uv]` — add `exclude-newer`, `require-hashes`, `verify-hashes`
3. `.cargo/config.toml` — add `[cooldown]` block
4. `composer.json` — add `roave/security-advisories` dev dependency; tighten `^`/`~` pins to exact (flag for human review)
5. Terraform `*.tf` — tighten `~>` / `>=` constraints to `=` exact pins (flag for human review — this is a breaking change; do not apply autonomously, present the proposed changes and get explicit approval)
5. `.github/dependabot.yml` — add missing ecosystem entries with cooldown blocks
6. `.github/workflows/*.yml` — add or update harden-runner steps

**Terraform version-pinning caveat:** Changing `~>` to `=` in `required_providers` is functionally a breaking change that can cause `terraform init` to fail if the exact version isn't in the lockfile. Always present the proposed constraint changes and the matching `terraform providers lock` command as a unit, and require explicit human approval before applying.

For each file you modify, show a clear before/after diff and explain what changed and why.

### Config templates to apply

**pnpm-workspace.yaml additions:**
```yaml
minimumReleaseAge: "7 days"
trustPolicy: no-downgrade
```

**npm .npmrc additions:**
```ini
save-exact=true
minimum-release-age=10080
audit=true
fund=false
```

**Yarn .yarnrc.yml additions:**
```yaml
defaultSemverRangePrefix: ""
npmMinimalAgeGate: 604800
```

**Bun bunfig.toml additions:**
```toml
[install]
exact = true
minimumReleaseAge = "7d"
lifecycleScripts = false
```

**uv pyproject.toml additions:**
```toml
[tool.uv]
exclude-newer = "7 days"
require-hashes = true
verify-hashes = true
```

**Cargo .cargo/config.toml additions:**
```toml
[cooldown]
days = 7
```

**Dependabot cooldown block (per ecosystem):**
```yaml
cooldown:
  default-days: 7
  semver-major-days: 30
  semver-minor-days: 7
  semver-patch-days: 3
```

**Composer CI install:**
```bash
export COMPOSER_NO_INTERACTION=1
composer install --no-scripts --no-plugins --prefer-dist
composer audit --locked
```

**roave/security-advisories (add as dev dependency):**
```bash
composer require --dev roave/security-advisories:dev-latest
```

**Dependabot composer ecosystem entry:**
```yaml
  - package-ecosystem: "composer"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30
      semver-minor-days: 7
      semver-patch-days: 3
```

**Harden-Runner endpoints for Composer:**
```yaml
      packagist.org:443
      repo.packagist.org:443
```

**Terraform required_providers exact pinning:**
```hcl
terraform {
  required_version = "= 1.9.8"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.84.0"   # replace with current exact version
    }
  }
}
```

**Terraform CI init with lockfile enforcement:**
```bash
terraform init -input=false -lockfile=readonly
```

**Multi-platform provider lock (run locally, commit result):**
```bash
terraform providers lock \
  -platform=linux/amd64 \
  -platform=linux/arm64 \
  -platform=darwin/arm64 \
  -platform=darwin/amd64
```

**Dependabot terraform ecosystem entry:**
```yaml
  - package-ecosystem: "terraform"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30
      semver-minor-days: 7
      semver-patch-days: 3
```

**Harden-Runner step (start in audit mode; switch to block after confirming allowlist):**
```yaml
- uses: step-security/harden-runner@v2
  with:
    egress-policy: audit
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
```

Append the ecosystem-specific endpoints:
- Node.js: `registry.npmjs.org:443` (add `npm.pkg.github.com:443` if GitHub Packages used)
- Python: `pypi.org:443 files.pythonhosted.org:443`
- Go: `proxy.golang.org:443 sum.golang.org:443 storage.googleapis.com:443`
- Rust: `crates.io:443 index.crates.io:443 static.crates.io:443`
- PHP: `packagist.org:443 repo.packagist.org:443`
- Terraform: `registry.terraform.io:443 releases.hashicorp.com:443 checkpoint-api.hashicorp.com:443`
- OpenTofu: `registry.opentofu.org:443` (provider binary CDN endpoints vary by provider — discover via `audit` mode first)

## Important notes

- **Never downgrade security.** If a stricter setting is already in place (e.g., a longer cooldown than the recommended 7 days), leave it as-is and note it as ✅.
- **Don't touch version numbers in package manifests** unless the user explicitly asks. Pinning existing unpinned ranges is a breaking change that deserves separate review.
- **Harden-Runner egress-policy**: always start new additions in `audit` mode, not `block`. Switching to `block` requires the user to first review the audit logs and build a confirmed allowlist. Note this clearly.
- **Flag items requiring human judgment** rather than silently skipping them — for example, if `onlyBuiltDependencies` is missing, list the packages that currently run build scripts and ask the user to confirm which should be allowed before writing the config.
