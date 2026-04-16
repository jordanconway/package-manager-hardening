<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

<!-- markdownlint-disable MD003 -->
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
  (npm/pnpm/yarn/bun), Python (pip/uv), Go, Rust/Cargo, PHP/Composer, Ruby/Bundler, and Terraform/OpenTofu repos
---
<!-- markdownlint-enable MD003 -->

# Package Manager Hardening Skill

You are auditing and hardening a software repository's dependency management against
supply chain attack risk. Your job is to detect gaps, explain why each matters, and
— with the user's consent — fix them.

## Step 1: Run the audit script

Run `audit.py` from the repo root to collect all findings as structured JSON:

```bash
python {SKILL_DIR}/audit.py --path .
```

Where `{SKILL_DIR}` is the directory containing this SKILL.md file (e.g. `skills/harden-packages`).

The script performs all file-based checks — ecosystem detection, lockfile presence,
version constraint analysis, CI config scanning, Dependabot and Harden-Runner
inspection — and emits a single JSON object. No manual file reading is needed for
the audit phase.

**If the script fails or is unavailable**, fall back to reading files directly using
the checklist in the [Reference: Manual Audit Checklist](#reference-manual-audit-checklist)
section below.

## Step 2: Interpret findings

Read the JSON output. The top-level keys are:

- `ecosystems_detected` — list of ecosystems found (nodejs, python, go, rust, php, ruby, terraform)
- One key per ecosystem (e.g. `nodejs`, `python`) with nested findings
- `dependabot` — per-ecosystem Dependabot configuration status
- `harden_runner` — per-workflow Harden-Runner status

Each check has a `status` field: `"pass"`, `"warn"`, `"fail"`, or `"missing"`.

**Interpretation notes:**

- `nodejs.exact_pins.unpinned` — list of `dependencies`/`devDependencies` using `^`, `~`, or ranges. Any entry here is a real finding.
- `nodejs.minimum_release_age.status: fail` — no cooldown configured for the detected manager. Recommend adding it.
- `rust.exact_pins.loose` — Cargo entries without `=` prefix. Flag each one.
- `terraform.exact_pins.loose` — provider version constraints that aren't `= X.Y.Z`. Flag each one and note this requires human approval to change.
- `dependabot.ecosystems.<eco>.status: warn` — ecosystem is in dependabot.yml but has no `cooldown:` block.
- `dependabot.ecosystems.<eco>.status: missing` — ecosystem not in dependabot.yml at all.
- `harden_runner.workflows.<name>.egress_policy: audit` — runner is present but in audit mode, not block. Flag as ⚠️.
- `harden_runner.workflows.<name>.harden_runner_present: false` — missing entirely. Flag as ❌.
- `terraform.known_bug` — always flag: Dependabot cooldown for terraform providers has a known bug; exact pinning is the primary control.

## Step 3: Report findings

Present a structured audit report grouped by ecosystem. Use ✅ / ⚠️ / ❌ markers. After the per-ecosystem checklists, give a short prioritised summary: what poses the most supply chain risk right now, and what's quick to fix vs requires more thought.

Only report on items that are actually wrong or missing — don't enumerate every passing check.

Example report structure:

```text
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
5. Ruby CI — add `BUNDLE_FROZEN=true` and `bundle audit check` to CI workflow
6. Terraform `*.tf` — tighten `~>` / `>=` constraints to `=` exact pins (**do not apply autonomously** — present proposed changes and require explicit human approval; changing constraints can cause `terraform init` to fail)
7. `.github/dependabot.yml` — add missing ecosystem entries with cooldown blocks
8. `.github/workflows/*.yml` — add or update harden-runner steps

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

**Ruby CI install:**

```bash
export BUNDLE_FROZEN=true
bundle install --jobs 4 --retry 3
bundle exec bundle-audit check --update
```

**Dependabot bundler ecosystem entry:**

```yaml
  - package-ecosystem: "bundler"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30
      semver-minor-days: 7
      semver-patch-days: 3
```

**Harden-Runner endpoints for Bundler:**

```yaml
      rubygems.org:443
      api.rubygems.org:443
      index.rubygems.org:443
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
- Ruby: `rubygems.org:443 api.rubygems.org:443 index.rubygems.org:443` (add `raw.githubusercontent.com:443` if `bundle audit update` runs in CI)
- Terraform: `registry.terraform.io:443 releases.hashicorp.com:443 checkpoint-api.hashicorp.com:443`
- OpenTofu: `registry.opentofu.org:443` (provider binary CDN endpoints vary by provider — discover via `audit` mode first)

## Important notes

- **Never downgrade security.** If a stricter setting is already in place (e.g., a longer cooldown than the recommended 7 days), leave it as-is and note it as ✅.
- **Don't touch version numbers in package manifests** unless the user explicitly asks. Pinning existing unpinned ranges is a breaking change that deserves separate review.
- **Harden-Runner egress-policy**: always start new additions in `audit` mode, not `block`. Switching to `block` requires the user to first review the audit logs and build a confirmed allowlist.
- **Flag items requiring human judgment** rather than silently skipping them — for example, if `onlyBuiltDependencies` is missing, list the packages that currently run build scripts and ask the user to confirm which should be allowed before writing the config.

---

## Reference: Manual Audit Checklist

Use this section only if `audit.py` cannot be run. It replicates what the script checks.

### Node.js (npm / pnpm / yarn / bun)

- Is `package-lock.json` / `pnpm-lock.yaml` / `yarn.lock` / `bun.lock` present and not gitignored?
- Do `dependencies` and `devDependencies` use exact versions (no `^` or `~`)?
- npm ≥ 11.10: is `minimum-release-age` set in `.npmrc`?
- pnpm ≥ 10.16: is `minimumReleaseAge` set in `pnpm-workspace.yaml`? Is `trustPolicy: no-downgrade` set?
- Yarn Berry ≥ 4.10: is `npmMinimalAgeGate` set in `.yarnrc.yml`?
- Bun ≥ 1.3: is `minimumReleaseAge` set in `bunfig.toml`?
- pnpm: is `onlyBuiltDependencies` (allowlist) or `ignoredBuiltDependencies` configured?
- Does CI use `npm ci` / `pnpm install --frozen-lockfile` / `yarn install --immutable` / `bun install --frozen-lockfile`?

### Python (pip / uv)

- uv: is `uv.lock` present and not gitignored? Are `exclude-newer`, `require-hashes`, `verify-hashes` set in `[tool.uv]`?
- pip: is there a `requirements.lock` with hashes (from `pip-compile --generate-hashes`)?
- Are all package specs using `==` (not `>=`, `~=`, or unpinned)?
- uv: does CI use `uv sync --frozen`? pip: `pip install --require-hashes`?

### Go

- Are `go.mod` and `go.sum` both present and not gitignored?
- Are all `require` entries using explicit tagged versions (not `@latest`, `@master`, `@main`)?
- Is `GONOSUMDB` scoped only to private modules (not `*`)?
- Does CI run `go mod verify` and `govulncheck ./...`?

### Rust / Cargo

- Is `Cargo.lock` present and not gitignored?
- Do `Cargo.toml` dependencies use `=` exact version syntax?
- Is `cargo-cooldown` configured in `.cargo/config.toml` with `[cooldown] days = 7`?
- Does CI use `--locked` on `cargo build`/`cargo test` and run `cargo audit --deny warnings`?

### PHP / Composer

- Is `composer.lock` present and not gitignored?
- Do all `require` entries use exact version strings (no `^`, `~`, `>=`, `*`)?
- Is Composer 2.7 or later in use?
- Does CI run `composer audit --locked`? Is `roave/security-advisories:dev-latest` a dev dependency?
- Does CI use `COMPOSER_NO_INTERACTION=1` and `--no-scripts --no-plugins --prefer-dist`?

### Ruby / Bundler

- Is `Gemfile.lock` present and not gitignored?
- Do all `gem` entries use exact versions (no `~>`, `>=`)?
- Is `BUNDLE_FROZEN=true` set in CI?
- Does CI run `bundle audit check`?
- Is a `ruby` directive in `Gemfile` or a `.ruby-version` file committed?

### Terraform / OpenTofu

- Is `.terraform.lock.hcl` present in each root module, not gitignored, with multi-platform `h1:` hashes?
- Do all `required_providers` blocks use `= X.Y.Z` exact constraints?
- Does CI use `terraform init -lockfile=readonly`?
- OpenTofu: is state encryption configured via `encryption {}` blocks?

### Dependabot

- Is `.github/dependabot.yml` present?
- For each detected ecosystem, is there an `updates` entry with a `cooldown` block?
- Terraform: note known cooldown bug (issue #13715) — exact pinning is the primary control.

### Harden-Runner

- Is `step-security/harden-runner@v2` the first step in every job that installs dependencies?
- Is `egress-policy` set to `block` (not `audit`)? Is `disable-sudo: true` set?
