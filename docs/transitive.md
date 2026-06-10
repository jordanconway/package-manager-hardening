<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Transitive Dependency Coverage

Most supply chain attacks do not target your direct dependencies — they target packages that
your dependencies depend on. The `colors` and `faker` sabotage, the `event-stream` backdoor,
and the `xz-utils` compromise all affected packages that most consuming projects never listed
in their own manifests. This document explains which controls in this repository cover
transitive dependencies, where the gaps are, and what to do about them.

## What "transitive" means

A direct dependency is a package you explicitly declare (`"express": "4.19.2"` in
`package.json`, `requests = "2.32.3"` in `pyproject.toml`). A transitive dependency is
anything those packages depend on, recursively. In a typical web application the ratio is
often 1:10 — one direct dependency for every ten transitive ones.

## Three defence layers and their transitive coverage

### Layer 1: Lockfiles + frozen install

**This is the primary control for transitive dependencies and applies universally across all
supported ecosystems that have a lockfile.**

A committed, enforced lockfile records every resolved package — direct and transitive — at an
exact version with a cryptographic hash. When `npm ci`, `uv sync --frozen`, `bundle install`
with `BUNDLE_FROZEN=true`, `dotnet restore --locked-mode`, etc. are used in CI, the resolver
is not permitted to introduce any package not already present in the lockfile. A new transitive
dependency — malicious or otherwise — cannot enter the build without a deliberate lockfile
update that produces a reviewable diff.

**What this protects against:** silent adoption of new or updated transitive packages during
normal CI runs.

**What it does not protect against:** the moment when you intentionally update a direct
dependency and regenerate the lockfile — any new transitive packages introduced at that point
are not individually gated. See [The update window](#the-update-window) below.

### Layer 2: Vulnerability scanning

All recommended vulnerability scanners operate on the full resolved dependency graph, not just
direct dependencies. Most require an explicit flag to include transitives, or do so by default
by reading the lockfile.

| Ecosystem | Tool | Transitive coverage |
|-----------|------|---------------------|
| Node.js | `npm audit` / `pnpm audit` / `yarn npm audit` / `bun audit` | ✅ Reads lockfile; full graph |
| Python | `pip-audit` | ✅ Full graph by default |
| Go | `govulncheck ./...` | ✅ Full module graph |
| Rust | `cargo audit` | ✅ Reads `Cargo.lock`; full graph |
| PHP | `composer audit --locked` | ✅ Reads `composer.lock`; full graph |
| Ruby | `bundler-audit check` | ✅ Reads `Gemfile.lock`; full graph |
| .NET | `dotnet list package --vulnerable --include-transitive` | ✅ `--include-transitive` is required |
| JVM | OWASP Dependency-Check, CycloneDX | ✅ Full graph including transitive JARs |
| Terraform | — | ❌ No widely-adopted tool for provider vulnerability scanning |
| Helm | — | ❌ No standardised tool; review chart `Chart.lock` manually |

**Key note on .NET:** without `--include-transitive`, `dotnet list package --vulnerable` only
reports vulnerable *direct* dependencies. Always use the full flag.

### Layer 3: Minimum release age

This is where ecosystems diverge significantly.

**Native implementations evaluate every resolved package at install/lock time,** including
transitives. If any package in the resolved graph — direct or transitive — was published
within the configured age threshold, the install fails immediately.

| Ecosystem | Implementation | Applies to transitives? |
|-----------|---------------|------------------------|
| npm ≥ 11.10 | `minimum-release-age` in `.npmrc` | ✅ All resolved packages |
| pnpm ≥ 10.16 | `minimumReleaseAge` in `pnpm-workspace.yaml` | ✅ All resolved packages |
| Yarn Berry ≥ 4.10 | `npmMinimalAgeGate` in `.yarnrc.yml` | ✅ All resolved packages |
| Bun ≥ 1.3 | `minimumReleaseAge` in `bunfig.toml` | ✅ All resolved packages |
| uv ≥ 0.9.17 | `exclude-newer` in `[tool.uv]` | ✅ All resolved packages |
| pip ≥ 26.0 | `--uploaded-prior-to` | ✅ All resolved packages (absolute date only — not rolling) |
| Cargo | `cargo-cooldown` | ✅ All resolved packages at fetch time |
| Go | None native | ❌ No built-in; see [Go gap](#go-module-proxy) below |
| Composer | None native | ❌ Dependabot cooldown only (direct deps, PR level) |
| Bundler | None native | ❌ Dependabot cooldown only |
| Maven | None native | ❌ Dependabot cooldown only |
| Gradle | None native | ❌ Dependabot cooldown only |
| NuGet | None native | ❌ Dependabot cooldown only |
| Terraform | None native | ❌ Exact pinning is the primary control |
| Helm | None native | ❌ Renovate `minimumReleaseAge` (direct chart deps only) |

**Dependabot cooldown operates at the PR level on direct dependencies only.** When Dependabot
opens a PR to update `express` from `4.18.2` to `4.19.2`, the cooldown delays that PR by the
configured number of days. But the transitive packages that `express@4.19.2` introduces are
not individually subject to cooldown. Dependabot cooldown is a useful secondary gate, not a
replacement for a native resolver-level implementation.

For the ❌ rows above, [Renovate's `minimumReleaseAge`](renovate.md) provides the same PR-level
gate as Dependabot cooldown but works uniformly across all of Renovate's supported managers —
including Maven, Gradle, NuGet, Composer, Bundler, Helm, and Terraform. It shares the same
direct-dependencies-only limitation.

## The update window

The most important residual gap across all ecosystems is the moment when you merge a dependency
update — whether from Dependabot or a manual `go get` / `bundle update` / `npm install foo`.
At that point the lockfile is regenerated and any new transitive packages pulled in by the
updated version enter the build for the first time.

**Example:** `foo@1.0.0` depends on `bar@1.2.0`. You merge a Dependabot PR updating `foo` to
`1.1.0`. The new `foo@1.1.0` introduces `baz@3.0.0` as a new transitive. `baz@3.0.0` was
published yesterday.

- **With native minimum release age (pnpm, Yarn, Bun, npm, uv, Cargo):** `baz@3.0.0` fails
  the age threshold at install time. The lockfile regeneration fails cleanly. The PR cannot be
  merged until `baz@3.0.0` has aged past the threshold. This is the strongest protection.
- **Without native minimum release age (Maven, Gradle, Go, Bundler, NuGet, Composer):** `baz@3.0.0`
  is silently accepted into the lockfile. Vulnerability scanning is the only remaining gate —
  and it can only catch *known-bad* packages, not ones that are freshly malicious.

**Mitigations for ecosystems without native cooldown:**

0. **Use [Renovate](renovate.md) with `minimumReleaseAge`** so the direct update itself is
   age-gated at the PR level — this shrinks (but does not eliminate) the window, since the
   transitives a 7-day-old release introduces have usually also had time to be vetted.
1. **Review lockfile diffs carefully on every dependency update PR.** A new transitive package
   appearing in `go.sum`, `Gemfile.lock`, `composer.lock`, or `packages.lock.json` is a signal
   worth investigating — check when it was published and whether it was previously a transitive
   dep (version bump) or is genuinely new (surface area increase).
2. **Run vulnerability scanning immediately after lockfile regeneration** (in the CI job that
   tests the Dependabot PR, not just on `main`). A scan on `main` may miss a window between
   merge and the next scheduled scan.
3. **Enable Dependabot security alerts** for the repository. These fire independently of
   cooldown and bypass it automatically, so a newly-disclosed transitive CVE triggers a PR
   immediately.
4. **Use `gradle/verification-metadata.xml`** (Gradle) or `maven-lockfile` (Maven) to record
   hashes for the full artifact graph. These don't provide a cooldown, but they fail the build
   if a transitive artifact changes its content between runs — detecting a substitution attack
   after the fact.

## Go module proxy

Go's module proxy (`proxy.golang.org`) and checksum database (`sum.golang.org`) provide
strong integrity guarantees — every module version is permanently recorded with a hash and
cannot be altered or removed — but they do not enforce a minimum age. The ecosystem-level
protection against a newly-published malicious transitive module is `govulncheck` (which
catches known CVEs) and a careful review of `go.sum` changes when modules are updated.

For high-security environments, the [Athens proxy](https://docs.gomods.io/) can be configured
with a minimum age policy and run as a private GOPROXY, blocking any module version published
within the configured window.

## Summary matrix

| Ecosystem | Lockfile pins transitives | Vuln scan covers transitives | Native age gate covers transitives |
|-----------|:---:|:---:|:---:|
| npm (≥ 11.10) | ✅ | ✅ | ✅ |
| pnpm (≥ 10.16) | ✅ | ✅ | ✅ |
| Yarn Berry (≥ 4.10) | ✅ | ✅ | ✅ |
| Bun (≥ 1.3) | ✅ | ✅ | ✅ |
| uv (≥ 0.9.17) | ✅ | ✅ | ✅ |
| pip (≥ 26.0) | ✅ | ✅ | ⚠️ Absolute date only |
| Cargo | ✅ | ✅ | ✅ (`cargo-cooldown`) |
| Go modules | ✅ (`go.sum` hashes) | ✅ | ❌ Athens proxy optional |
| Composer | ✅ | ✅ | ❌ |
| Bundler | ✅ | ✅ | ❌ |
| Maven | ❌ No native lockfile | ✅ | ❌ |
| Gradle | ✅ | ✅ | ❌ |
| NuGet | ✅ (opt-in) | ✅ (`--include-transitive`) | ❌ |
| Terraform | ⚠️ Providers only | ❌ | ❌ |
| Helm | ✅ (`Chart.lock`) | ❌ | ❌ |

**Legend:** ✅ Full coverage — ⚠️ Partial — ❌ Not available natively

The strongest position is an ecosystem with all three columns ticked. For ecosystems missing
the age gate column, the lockfile + vulnerability scanning combination still catches the
majority of real attacks — most compromised packages are detected and flagged within hours,
and a lockfile prevents silent adoption in routine CI runs. The residual risk is a narrow
window between publication of a malicious transitive and its detection, during a deliberate
dependency update.
