---
name: harden-packages
description: >
  Audit and harden package manager security configuration in a software repository.
  Use this skill whenever the user wants to: audit dependency security, check package
  manager hardening, apply supply chain security best practices, set up Dependabot
  cooldowns, configure Harden-Runner in GitHub Actions, pin dependency versions, add
  lockfiles, configure minimum release age, check for unpinned dependencies, run
  zizmor static analysis on GitHub Actions workflows, or
  review CI/CD pipeline security. Also trigger when the user says things like "harden
  my repo", "check my dependencies", "is my package config secure?", "set up supply
  chain security", "add Dependabot", "run zizmor", or "are my packages safe?". Works
  across Node.js
  (npm/pnpm/yarn/bun), Python (pip/uv), Go, Rust/Cargo, PHP/Composer, Ruby/Bundler,
  JVM (Maven, Gradle — Java and Kotlin), and Terraform/OpenTofu repos
---

<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation
SPDX-License-Identifier: MIT
-->

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

- `ecosystems_detected` — list of ecosystems found (nodejs, python, go, rust, php, ruby, terraform, maven, gradle)
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
- `dependabot.ecosystems.github-actions` — only `default-days` is reliable here; `semver-*-days` keys often don't trigger because action tags aren't parsed as SemVer. Don't flag a missing `semver-*-days` for `github-actions` as a gap.
- `dependabot.ecosystems.<eco>.status: missing` — ecosystem not in dependabot.yml at all.
- `harden_runner.workflows.<name>.egress_policy: audit` — runner is present but in audit mode, not block. Flag as ⚠️.
- `harden_runner.workflows.<name>.harden_runner_present: false` — missing entirely. Flag as ❌.
- `terraform.known_bug` — always flag: Dependabot cooldown for terraform providers has a known bug; exact pinning is the primary control.
- `maven.exact_pins.loose` — pom.xml `<version>` entries that are ranges (`[1.2,2.0)`), `LATEST`, `RELEASE`, or `SNAPSHOT`. Every entry is a real finding. Property placeholders (`${...}`) are not flagged.
- `maven.enforcer_plugin.status: fail` — `maven-enforcer-plugin` is missing or has fewer than two of the canonical hardening rules (`banDynamicVersions`, `requirePluginVersions`, `requireReleaseDeps`, `dependencyConvergence`). Maven has no native lockfile; the enforcer plugin is the substitute.
- `maven.strict_checksums.status: fail` — neither `<checksumPolicy>fail</checksumPolicy>` nor `--strict-checksums` / `-C` on the CI invocation. Maven defaults to *warn*, not *fail*, on checksum mismatch.
- `maven.sca_scanner.status: fail` — no OWASP Dependency-Check, CycloneDX, or OSS Index plugin configured.
- `gradle.exact_pins.loose` — `build.gradle(.kts)` dependency strings with `+`, `latest.release`, ranges, or `SNAPSHOT`.
- `gradle.dependency_locking.status: fail` — `dependencyLocking { lockAllConfigurations() }` missing, not in `LockMode.STRICT`, or no `gradle.lockfile` committed.
- `gradle.dependency_verification.status: fail` — `gradle/verification-metadata.xml` missing or `verify-metadata` not set to true. This is the strongest artefact-integrity control on the JVM; recommend it whenever it's absent.
- `gradle.wrapper.status: fail` — `gradle-wrapper.properties` missing `distributionSha256Sum=` line. The Gradle Wrapper download is otherwise unverified.
- `gradle.repository_control` — flag any of: `FAIL_ON_PROJECT_REPOS` not set, `mavenLocal()` present (allows developer-local artefacts to substitute for Central), `jcenter()` present (unmaintained since 2024).
- `gradle.reject_dynamic.status: fail` — neither `failOnNonReproducibleResolution()` nor `failOnDynamicVersions()` configured.
- `gradle.ci.writes_locks_in_ci: true` — CI is running `--write-locks` or `--write-verification-metadata`. These are local-only operations; running them in CI defeats the controls. Always flag.
- `dependabot.ecosystems.gradle.gradle_wrapper_ecosystem: missing` — sub-finding: the Gradle Wrapper has its own Dependabot ecosystem (`gradle-wrapper`) separate from `gradle`, and is missing.

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
✅ uv.lock committed (hash verification is automatic with `uv sync --frozen`)
✅ exclude-newer = "7 days"
❌ [tool.uv.pip] require-hashes not set — ad-hoc `uv pip install` calls won't enforce hashes

### Dependabot
✅ npm cooldown configured (7/30/7/3 days)
❌ pip ecosystem missing from dependabot.yml

### GitHub Actions
⚠️ ci.yml: harden-runner present but egress-policy is "audit", not "block"
❌ release.yml: harden-runner not present
❌ No zizmor static analysis configured
⚠️ actions/checkout in ci.yml does not set persist-credentials: false (zizmor: artipacked × 3)
⚠️ ci.yml uses `runs-on: ubuntu-latest` (4 jobs) — should pin to `ubuntu-24.04`
❌ No `actions/dependency-review-action` job (PRs can introduce vulnerable deps unchecked)
❌ No OpenSSF Scorecard workflow
❌ No `SECURITY.md` and private vulnerability reporting is disabled

### Priority fixes
1. Add harden-runner to release.yml — release workflows are high-value targets
2. Add a zizmor job to CI; pin the version (`uvx zizmor==X.Y.Z`) and resolve current findings
3. Add `actions/dependency-review-action` as a PR-only required check (fail-on-severity: high, license denylist)
4. Add `ossf/scorecard-action` workflow (weekly + push to main) with SARIF upload + README badge
5. Add `SECURITY.md` linking to private vulnerability reporting; enable PVR in repo Settings
6. Pin runner images: `ubuntu-latest` → `ubuntu-24.04` across all jobs
7. Set egress-policy: block in ci.yml once allowlist is confirmed
8. Add require-hashes = true under [tool.uv.pip] (defensive, for ad-hoc `uv pip install`)
9. Add pip entry to dependabot.yml
10. Set trustPolicy: no-downgrade in pnpm-workspace.yaml
```

## Step 4: Offer to fix

After the report, ask: "Would you like me to apply the fixes? I can handle all of them, or you can tell me which ones to skip."

If the user agrees (fully or partially), apply the fixes in this order — lower risk / non-breaking changes first:

1. `pnpm-workspace.yaml` / `.npmrc` / `.yarnrc.yml` / `bunfig.toml` — add missing cooldown / trust policy config
2. `pyproject.toml` — add `[tool.uv] exclude-newer = "7 days"` and `[tool.uv.pip] require-hashes = true / verify-hashes = true`. (Hash verification of artefacts resolved against `uv.lock` is automatic via `uv sync --frozen` — these `[tool.uv.pip]` flags only protect ad-hoc `uv pip install` invocations.)
3. `.cargo/config.toml` — add `[cooldown]` block
4. `composer.json` — add `roave/security-advisories` dev dependency; tighten `^`/`~` pins to exact (flag for human review)
5. Ruby CI — add `BUNDLE_FROZEN=true` and `bundle audit check` to CI workflow
6. Terraform `*.tf` — tighten `~>` / `>=` constraints to `=` exact pins (**do not apply autonomously** — present proposed changes and require explicit human approval; changing constraints can cause `terraform init` to fail)
7. Maven `pom.xml` — add `maven-enforcer-plugin` with `banDynamicVersions` / `requirePluginVersions` / `requireReleaseDeps` / `dependencyConvergence`; set `<checksumPolicy>fail</checksumPolicy>` (**do not autonomously change `<version>` pins** — flag for human review, since tightening a transitive can break downstream consumers)
8. Gradle `build.gradle(.kts)` / `settings.gradle(.kts)` — add `dependencyLocking { lockAllConfigurations(); lockMode.set(LockMode.STRICT) }`, `failOnNonReproducibleResolution()`, and `RepositoriesMode.FAIL_ON_PROJECT_REPOS`; remove `mavenLocal()` and `jcenter()` (**flag — repository changes can break local development**). Generating `gradle.lockfile` and `gradle/verification-metadata.xml` requires running `./gradlew --write-locks` and `./gradlew --write-verification-metadata sha256,pgp help` locally — do not run these in CI, and do not run them autonomously; instruct the user to run them and commit the result.
9. `.github/dependabot.yml` — add missing ecosystem entries with cooldown blocks
10. `.github/workflows/*.yml` — add or update harden-runner steps

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
# Rolling 7-day cooldown — re-evaluated on every `uv lock`.
# Supported since uv 0.9.17 (Dec 2025).
exclude-newer = "7 days"

[tool.uv.pip]
# Defensive: enforce hashes for ad-hoc `uv pip install` calls.
# `uv sync --frozen` already enforces lockfile hashes automatically;
# these flags only affect the pip-compat surface.
require-hashes = true
verify-hashes = true
```

**Note on dev tooling:** declare ruff/pytest/etc. as a PEP 735 dependency group, not as inline `pip install` lines in CI — Dependabot (`package-ecosystem: "uv"`) cannot update what isn't in a manifest:

```toml
[dependency-groups]
dev = [
  "ruff==0.11.2",
  "pytest==8.3.5",
]
```

Then install in CI with `uv sync --frozen --group dev` and run via `uv run <tool>`.

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

**Dependabot cooldown for `github-actions` (special case):**

GitHub Actions tags (`v4`, `v4.1.2`, plus the SHA-pinned `# v4.1.2` comment workflow) are not always parsed as SemVer by Dependabot, so the `semver-*-days` keys do not reliably apply. Use only `default-days` for the `github-actions` ecosystem so the cooldown always takes effect:

```yaml
# Note: GitHub Actions tags (v4, v4.1.2) aren't always parsed as SemVer
# by Dependabot, so we rely on default-days which always applies.
cooldown:
  default-days: 7
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

**Maven enforcer plugin (add to `<build><plugins>` in pom.xml):**

```xml
<plugin>
  <groupId>org.apache.maven.plugins</groupId>
  <artifactId>maven-enforcer-plugin</artifactId>
  <version>3.5.0</version>
  <executions>
    <execution>
      <id>enforce</id>
      <goals><goal>enforce</goal></goals>
      <configuration>
        <rules>
          <banDynamicVersions/>
          <requirePluginVersions>
            <banLatest>true</banLatest>
            <banRelease>true</banRelease>
            <banSnapshots>true</banSnapshots>
          </requirePluginVersions>
          <requireReleaseDeps/>
          <dependencyConvergence/>
        </rules>
      </configuration>
    </execution>
  </executions>
</plugin>
```

**Maven strict checksums (settings.xml repository entry):**

```xml
<releases>
  <enabled>true</enabled>
  <checksumPolicy>fail</checksumPolicy>
</releases>
```

**Maven CI invocation:**

```bash
mvn --batch-mode --strict-checksums --fail-fast verify
mvn --batch-mode org.owasp:dependency-check-maven:check
```

**Dependabot maven ecosystem entry:**

```yaml
  - package-ecosystem: "maven"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30
      semver-minor-days: 7
      semver-patch-days: 3
```

**Gradle hardening block (root build.gradle.kts):**

```kotlin
allprojects {
    configurations.all {
        resolutionStrategy {
            failOnNonReproducibleResolution()
        }
    }
    dependencyLocking {
        lockAllConfigurations()
        lockMode.set(LockMode.STRICT)
    }
}
```

**Gradle repository control (settings.gradle.kts):**

```kotlin
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        mavenCentral()
        gradlePluginPortal()
    }
}
```

**Gradle generate lockfile and verification metadata (run locally, commit the result — never in CI):**

```bash
./gradlew dependencies --write-locks
./gradlew --write-verification-metadata sha256,pgp --export-keys help
```

**Gradle CI invocation:**

```bash
./gradlew --no-daemon --console=plain --stacktrace build
./gradlew --no-daemon dependencyCheckAnalyze
```

**Dependabot gradle + gradle-wrapper ecosystem entries:**

```yaml
  - package-ecosystem: "gradle"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30
      semver-minor-days: 7
      semver-patch-days: 3
  - package-ecosystem: "gradle-wrapper"
    directory: "/"
    schedule:
      interval: "weekly"
```

**Harden-Runner endpoints for Maven and Gradle:**

```yaml
      repo.maven.apache.org:443
      repo1.maven.org:443
      plugins.gradle.org:443
      services.gradle.org:443
      downloads.gradle.org:443
```

Add `nvd.nist.gov:443 services.nvd.nist.gov:443` if OWASP Dependency-Check runs in CI. Add `dl.google.com:443` for Android/Kotlin projects. Add private registry hostnames (Nexus, Artifactory, GitHub Packages) if used.

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
- uses: step-security/harden-runner@6c3c2f2c1c457b00c10c4848d6f5491db3b629df # v2
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
- Python: `pypi.org:443 files.pythonhosted.org:443` (add `astral.sh:443 release-assets.githubusercontent.com:443 raw.githubusercontent.com:443` if `astral-sh/setup-uv` is used — it downloads the uv binary from GitHub releases (which redirect to `release-assets.githubusercontent.com`, **not** the older `github-production-release-asset-2e65be.s3.amazonaws.com`), and on **v8+** also fetches its version manifest from `raw.githubusercontent.com/astral-sh/versions`. v6.x baked the manifest into the action and did not need `raw.githubusercontent.com`.)
- Go: `proxy.golang.org:443 sum.golang.org:443 storage.googleapis.com:443`
- Rust: `crates.io:443 index.crates.io:443 static.crates.io:443`
- PHP: `packagist.org:443 repo.packagist.org:443`
- Ruby: `rubygems.org:443 api.rubygems.org:443 index.rubygems.org:443` (add `raw.githubusercontent.com:443` if `bundle audit update` runs in CI)
- Maven / Gradle: `repo.maven.apache.org:443 repo1.maven.org:443 plugins.gradle.org:443 services.gradle.org:443 downloads.gradle.org:443` (add `nvd.nist.gov:443 services.nvd.nist.gov:443` if OWASP Dependency-Check runs; `dl.google.com:443` for Android/Kotlin)
- Terraform: `registry.terraform.io:443 releases.hashicorp.com:443 checkpoint-api.hashicorp.com:443`
- OpenTofu: `registry.opentofu.org:443` (provider binary CDN endpoints vary by provider — discover via `audit` mode first)

## Important notes

- **Never downgrade security.** If a stricter setting is already in place (e.g., a longer cooldown than the recommended 7 days), leave it as-is and note it as ✅.
- **Don't touch version numbers in package manifests** unless the user explicitly asks. Pinning existing unpinned ranges is a breaking change that deserves separate review.
- **Harden-Runner egress-policy**: always start new additions in `audit` mode, not `block`. Switching to `block` requires the user to first review the audit logs and build a confirmed allowlist.
- **Flag items requiring human judgment** rather than silently skipping them — for example, if `onlyBuiltDependencies` is missing, list the packages that currently run build scripts and ask the user to confirm which should be allowed before writing the config.
- **`go install` pinning**: never use `@latest`, `@master`, or `@main` in any `go install` invocation — in Makefiles, scripts, or CI workflows. Always use an explicit `@vX.Y.Z`. The go sum database provides hash verification but the version itself is still mutable without an explicit pin.
- **Go stdlib CVEs**: standard library vulnerabilities cannot be fixed by bumping a `require` entry — they require upgrading the `go` directive in `go.mod` to the patched Go release. When govulncheck reports stdlib findings, check the "Fixed in" version and update the `go` directive accordingly.
- **Go `go` directive format**: use the full patch version (`go 1.25.9`), not the bare minor (`go 1.25`) or base patch (`go 1.25.0`). `go mod tidy` preserves fully-specified patch versions but normalises `go 1.25` → `go 1.25.0`. govulncheck reads the `go` directive as the stdlib CVE baseline — `go 1.25.0` will surface all CVEs fixed in 1.25.1 through the latest patch. Do **not** split a patch-versioned `go` directive into `go 1.25` + `toolchain go1.25.9` on the assumption that the toolchain directive covers CVE exposure — it does not; only the `go` directive does.
- **Reusable workflow pinning**: job-level `uses:` entries that delegate to a reusable workflow (e.g., SLSA generators, shared org workflows) are mutable refs and must be SHA-pinned, just like step-level actions. They cannot receive harden-runner steps, so flag them separately.
- **zizmor in CI**: if the user wants to harden a GitHub Actions setup, recommend adding a `zizmor` job alongside Harden-Runner. They are complementary — Harden-Runner is runtime egress control, zizmor is static analysis of the workflow file itself. Pin the zizmor version (`uvx zizmor==X.Y.Z`) and run at `--min-severity=medium` (default persona) or `--persona=auditor --min-severity=low` (stricter).
- **dependency-review + Scorecard + SECURITY.md are all zero-infra GitHub-native controls**: when recommending GitHub Actions hardening, offer all three together as a single "CI hardening pack". They cost nothing, require no external accounts or self-hosting, and produce externally visible posture signal (Scorecard badge) plus a vulnerability-disclosure path (`SECURITY.md` + PVR).
- **Branch protection**: every new required-check job (zizmor, dependency-review, Scorecard) must be added to the repo's required status checks for the default branch, otherwise it can be merged around. Use `gh api -X PUT repos/<owner>/<repo>/branches/<branch>/protection` and update `required_status_checks.contexts`.

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

- uv: is `uv.lock` present and **not gitignored**? Is `exclude-newer` set in `[tool.uv]` (rolling duration like `"7 days"` preferred over a frozen timestamp)? Are `require-hashes` and `verify-hashes` set in `[tool.uv.pip]` (note: this is `[tool.uv.pip]`, not `[tool.uv]` — uv rejects them at the top level)? Hash verification against `uv.lock` is automatic via `uv sync --frozen` regardless. Are dev tools (ruff/pytest/etc.) declared in `[dependency-groups]` so Dependabot can update them, rather than inline `pip install x==y` in CI?
- pip: is there a `requirements.lock` with hashes (from `pip-compile --generate-hashes`)?
- Are all package specs using `==` (not `>=`, `~=`, or unpinned)?
- uv: does CI use `uv sync --frozen`? pip: `pip install --require-hashes`?

### Go

- Are `go.mod` and `go.sum` both present and not gitignored?
- Are all `require` entries using explicit tagged versions (not `@latest`, `@master`, `@main`)?
- Is `GONOSUMDB` scoped only to private modules (not `*`)?
- Does CI run `go mod verify` and `govulncheck ./...`?
- Does CI run `go mod verify` **before** `go build`? A tampered or stale module graph must be caught before the compiler touches any dependency.
- Does the `go mod tidy` diff check use `git diff --exit-code -- go.mod go.sum` (with the `--` pathspec separator)? Does it also run before `go build`?
- Is `GOTOOLCHAIN=local` set in CI? Without it, the go binary can silently auto-fetch a different toolchain at runtime even after `actions/setup-go` has installed the intended version.
- Does the `go` directive in `go.mod` include the full patch version (e.g., `go 1.25.9` not `go 1.25` or `go 1.25.0`)? **govulncheck reads the `go` directive — not `go env GOVERSION` — as the stdlib baseline for CVE analysis.** A bare `go 1.25.0` causes govulncheck to report all CVEs fixed in later patch releases as active, even if the installed toolchain is already patched.
- Are Makefile or script `go install` invocations pinned to explicit versions (not `@latest`, `@master`, `@main`)? `go install` with `@latest` is the same supply-chain risk as an unpinned GitHub Action — the only difference is that the go sum database verifies the hash, but the version itself is still mutable.
- Does CI install tools via `make <target>` that the job doesn't actually use? If so, extract only the needed commands rather than running the full target (e.g., don't run a `deps` target that installs a linter when the job never calls `make lint`).

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

### JVM (Maven / Gradle — Java / Kotlin)

**Maven (`pom.xml` present):**

- Do all `<version>` entries use exact, immutable values? Flag any range (`[1.2,2.0)`, `(1.2,)`), `LATEST`, `RELEASE`, or `SNAPSHOT`.
- Is every plugin pinned in `<build><pluginManagement>` with an explicit `<version>`?
- Is `maven-enforcer-plugin` configured with at least two of: `banDynamicVersions`, `requirePluginVersions`, `requireReleaseDeps`, `dependencyConvergence`?
- Is the checksum policy `fail` — either via `<checksumPolicy>fail</checksumPolicy>` in a repository definition or via `--strict-checksums` / `-C` on every CI Maven invocation?
- Is at least one SCA scanner (`dependency-check-maven`, `cyclonedx-maven-plugin`, or `ossindex-maven-plugin`) wired into the build?
- Does CI pass `--batch-mode` and `--fail-fast`?
- Is `.mvn/extensions.xml` reviewed? Extensions load before any POM is parsed and run JVM code on the build host.

**Gradle (`build.gradle` or `build.gradle.kts` present):**

- Are all dependency coordinates exact? Flag any `+`, `latest.release`, range (`[1.0,2.0)`), or `SNAPSHOT`.
- Is `dependencyLocking { lockAllConfigurations(); lockMode.set(LockMode.STRICT) }` configured at the root and is `gradle.lockfile` committed for every project module?
- Is `gradle/verification-metadata.xml` committed, with `<verify-metadata>true</verify-metadata>` and ideally `<verify-signatures>true</verify-signatures>`?
- Does `gradle/wrapper/gradle-wrapper.properties` include a `distributionSha256Sum=` line?
- In `settings.gradle(.kts)`, is `repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)` set?
- Is `mavenLocal()` or `jcenter()` referenced anywhere? Both are red flags.
- Is `failOnNonReproducibleResolution()` (or `failOnDynamicVersions()` + `failOnChangingVersions()`) configured on every configuration?
- Does CI invoke `./gradlew` (not a system `gradle`) and pass `--no-daemon`?
- Does CI ever run `--write-locks` or `--write-verification-metadata`? If so, that defeats the controls and must be removed.
- Is at least one SCA plugin (`org.owasp.dependencycheck`, `org.cyclonedx.bom`, or Snyk) configured?

**Dependabot ecosystems for JVM projects:**

- Maven: `package-ecosystem: "maven"` with cooldown.
- Gradle: `package-ecosystem: "gradle"` with cooldown, **plus** `package-ecosystem: "gradle-wrapper"` (a separate ecosystem that updates the Wrapper version itself).

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

- Is `step-security/harden-runner` (SHA-pinned, e.g. `@6c3c2f2c1c457b00c10c4848d6f5491db3b629df # v2`) the first step in every job that installs dependencies? Flag any `@v2` / `@v3` / `@main` references — actions must be SHA-pinned to a 40-char commit, with a `# vX.Y.Z` trailing comment.
- Is `egress-policy` set to `block` (not `audit`)? Is `disable-sudo: true` set?
- Are job-level `uses:` entries (reusable workflows) SHA-pinned? These are mutable refs just like step-level `uses:` but **cannot receive harden-runner steps** — the entire job is delegated to the reusable workflow. Flag unpinned reusable workflow refs separately from the harden-runner audit.

### Workflow static analysis (zizmor)

[`zizmor`](https://docs.zizmor.sh) is the canonical static analyser for GitHub Actions workflows. It catches issues the file-based checks above can't reach — template injection, missing `persist-credentials: false`, missing workflow `concurrency:`, dangerous triggers (`pull_request_target` with checkout-of-head), secrets exposed to forks, mutable reusable-workflow refs, etc.

- Is there a `zizmor` job in CI? Flag as ❌ if missing.
- Is the zizmor version pinned (e.g. `uvx zizmor==1.24.1`)? Flag bare `uvx zizmor` as ⚠️.
- Is `--min-severity` set to at least `medium` (default) or `low` (preferred, with `--persona=auditor`)?
- When recommending or adding zizmor, run it locally first: `uvx zizmor --persona=auditor .`. Report each finding and offer to fix; do not auto-suppress findings.
- Common findings to know:
  - **`artipacked`** (medium): `actions/checkout` missing `persist-credentials: false`. Fix on every checkout unless the job pushes to git.
  - **`template-injection`** (high/medium): `${{ ... }}` interpolated into a `run:` block. Fix by passing the value through `env:` and quoting `"$VAR"` in the shell.
  - **`concurrency-limits`** (low): no workflow-level `concurrency:` block. Add one keyed on `${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress: true` for CI; `false` for release/deploy workflows.
  - **`dangerous-triggers`** (high): `pull_request_target` combined with a checkout of `github.event.pull_request.head.ref`. Requires immediate human review.
  - **`unpinned-uses`** (high): action referenced by tag (`@v4`) instead of SHA. Already covered by the harden-runner / SHA-pinning checks above, but zizmor will surface it again.
  - **`excessive-permissions`** (medium): workflow or job missing `permissions:` declaration, or granting more than `contents: read` without justification.
  - **`undocumented-permissions`** (auditor low): `permissions:` block missing inline comments justifying each grant. Fix with trailing `# why this is needed` comments on each line.

### Runner image pinning

- Are all `runs-on:` values pinned to a specific image (`ubuntu-24.04`, `ubuntu-22.04`, `windows-2022`, `macos-14`)? Flag every `ubuntu-latest` / `windows-latest` / `macos-latest` as ⚠️. GitHub rolls these forward and has historically changed pre-installed tools mid-lifecycle.
- Note that Dependabot does not propose runner-image bumps. Recommend adding a calendar reminder or tracking via a long-lived issue when a new LTS is GA.

### Dependency review on PRs

- Is there an `actions/dependency-review-action` job, gated on `if: github.event_name == 'pull_request'`? Flag absence as ❌.
- Is `fail-on-severity` at least `high`? `moderate` or `low` is preferred for security-sensitive repos.
- Is there a `deny-licenses` list appropriate to the project's own license? At minimum, MIT/Apache projects should deny GPL/AGPL.
- Is `comment-summary-in-pr: on-failure` set so contributors see why the check failed?
- Is the job a required status check on `main`? If not, the gate can be merged around.

### OpenSSF Scorecard

- Is there a `.github/workflows/scorecard.yml` running `ossf/scorecard-action` on a weekly schedule + push to `main`? Flag absence as ❌.
- Are SARIF results uploaded via `github/codeql-action/upload-sarif` so they appear in the Security tab?
- Is `publish_results: true` set so the README badge resolves?
- Is the workflow's `egress-policy` set to `audit` (not `block`)? Scorecard legitimately contacts deps.dev, OSV, npm, PyPI, etc. and cannot run under a fixed allowlist. Flag `block` here as ⚠️.
- Is the Scorecard badge in the README so the score is publicly visible?
- Note that a *dropping* Scorecard score is a regression to triage — not just a green/red flag at a point in time.

### SECURITY.md and private vulnerability reporting

- Is there a `SECURITY.md` at the repo root? Flag absence as ❌.
- Does it link to `https://github.com/<owner>/<repo>/security/advisories/new`?
- Does it include explicit "do not file public issues" wording?
- Does it state response-time expectations (acknowledgement + patch SLOs)?
- Is GitHub's private vulnerability reporting enabled? Check via `gh api repos/<owner>/<repo>/private-vulnerability-reporting --jq .enabled`. Flag `false` as ❌. Enable with `gh api -X PUT repos/<owner>/<repo>/private-vulnerability-reporting`.
