# Package Manager Security Hardening

A reference for hardening software supply chains across npm, pnpm, Yarn, Bun, pip, uv, Go modules, Cargo, Terraform, and OpenTofu.

Supply chain attacks typically succeed through one of a small number of vectors: a loose version constraint allows a newly published malicious version to be silently pulled in; a missing or unenforced lockfile lets an attacker's package substitute for a legitimate one; a compromised maintainer account publishes a backdoored patch release that lands in CI within minutes of publication; or a package's postinstall script runs arbitrary code during a routine `npm install`. This repository addresses all of these through a layered set of controls applied consistently across ecosystems.

The core practices covered here are:

**Exact version pinning** — specifying precise versions (`1.0.0`, `==1.0.0`, `=1.0.0`, `= 5.31.0`) rather than ranges (`^`, `~>`, `>=`) in package manifests. Ranges allow any version satisfying the constraint to be resolved at install time; exact pins mean only one version is ever valid.

**Lockfile enforcement** — committing lockfiles (`package-lock.json`, `uv.lock`, `go.sum`, `Cargo.lock`, `.terraform.lock.hcl`) and using strict install commands in CI (`npm ci`, `--frozen-lockfile`, `uv sync --frozen`, `--locked`, `-lockfile=readonly`) so that builds cannot silently resolve to a different version than what was reviewed.

**Minimum release age / cooldown windows** — blocking packages published within the last N days (typically 7). Most supply chain attacks involving typosquatting or account takeover are detected and removed from registries within hours to days. A cooldown window gives the community time to catch malicious versions before they reach production. Native support exists in pnpm, Yarn Berry, Bun, npm, and uv; Dependabot provides the equivalent at the PR level for all ecosystems.

**Dependency auditing** — scanning for known vulnerabilities on every CI run using ecosystem-native tools (`npm audit`, `cargo audit`, `govulncheck`, `pip-audit`) so that newly disclosed CVEs trigger action before they reach production.

**Build script control** — restricting which packages are permitted to run postinstall scripts (`onlyBuiltDependencies` in pnpm, `lifecycleScripts` in Bun). Postinstall scripts are one of the most common mechanisms used by malicious packages to execute code at install time.

**Automated updates with cooldown** — using Dependabot with per-semver-level delay windows (e.g. 30 days for major, 7 for minor, 3 for patch) so that dependency updates are proposed automatically but not merged until after the cooldown has elapsed. Security advisories bypass the cooldown automatically.

**Runtime CI egress control** — using [Harden-Runner](https://github.com/step-security/harden-runner) to monitor and block unexpected outbound network connections during CI jobs. This catches malicious packages that pass version checks but attempt to exfiltrate secrets or call home during `npm install` or equivalent.

---

## Quick start

**For AI coding assistants:** copy a ready-made `AGENTS.md` into your repo to give your agent standing dependency-management instructions:

```bash
# Pick the one that matches your stack
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/agents/AGENTS-nodejs.md
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/agents/AGENTS-python.md
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/agents/AGENTS-go.md
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/agents/AGENTS-rust.md
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/agents/AGENTS-terraform.md
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/agents/AGENTS-php.md
```

**For on-demand auditing:** install the `harden-packages` skill and say `harden my repo` in Claude Code or Cowork.

```bash
cp -r skills/harden-packages ~/.claude/skills/
```

---

## Contents

### Package ecosystems

| Doc | Covers |
|-----|--------|
| [Node.js](docs/nodejs.md) | npm, pnpm, Yarn, Bun — lockfiles, version pinning, minimum release age, build script control, CI config |
| [Python](docs/python.md) | pip / pip-tools, uv — lockfiles, hash verification, `exclude-newer`, frozen installs |
| [Go](docs/go.md) | Go modules — `go.sum`, MVS pinning, `GOPRIVATE`, `govulncheck`, CI verification |
| [Rust](docs/rust.md) | Cargo — exact version pinning, `cargo-cooldown`, `cargo audit`, lockfile enforcement |
| [PHP](docs/php.md) | Composer — lockfile enforcement, exact pinning, `composer audit`, `roave/security-advisories`, build script control |
| [Terraform / OpenTofu](docs/terraform.md) | Provider pinning, `.terraform.lock.hcl`, multi-platform hashes, `-lockfile=readonly`, OpenTofu differences |

### Cross-cutting controls

| Doc | Covers |
|-----|--------|
| [Dependabot](docs/dependabot.md) | Cooldown configuration per ecosystem, semver-level delay, known Terraform provider bug |
| [Harden-Runner](docs/harden-runner.md) | Runtime CI egress control, audit → block mode, per-ecosystem `allowed-endpoints` |

### AI assistant tooling

| Doc | Covers |
|-----|--------|
| [AGENTS.md Files](docs/agents.md) | Ready-made dependency management instructions for Claude Code and compatible agents — one file per stack |
| [harden-packages Skill](docs/skill.md) | On-demand audit and fix skill for Cowork / Claude Code — detects gaps, reports findings, applies fixes |

---

## Native Minimum Release Age Support Matrix

| Package Manager        | Native Support | Since        | Config Key                  | Relative Duration |
|------------------------|---------------|--------------|------------------------------|-------------------|
| [pnpm](docs/nodejs.md#pnpm) | ✅ Yes | v10.16 (Sep 2025) | `minimumReleaseAge` | ✅ Yes |
| [Yarn Classic](docs/nodejs.md#yarn-classic) / [Berry](docs/nodejs.md#yarn-berry) | ✅ Yes | v4.10 (Sep 2025) | `npmMinimalAgeGate` | ✅ Yes (seconds) |
| [Bun](docs/nodejs.md#bun) | ✅ Yes | v1.3 (Oct 2025) | `minimumReleaseAge` | ✅ Yes |
| [npm](docs/nodejs.md#npm) | ✅ Yes | v11.10 (Feb 2026) | `minimum-release-age` | ✅ Yes (minutes) |
| [uv](docs/python.md#uv) | ✅ Yes | v0.9.17 (Dec 2025) | `exclude-newer` | ✅ Yes |
| [pip](docs/python.md#pip) | ⚠️ Partial | v26.0 (Jan 2026) | `--uploaded-prior-to` | ❌ Absolute only |
| [Cargo](docs/rust.md#cargo-rust) | ❌ No | — | (use `cargo-cooldown`) | — |
| [Go modules](docs/go.md#go-modules) | ❌ No | — | (use Dependabot or proxy) | — |
| [Composer](docs/php.md#composer) | ❌ No | — | (use Dependabot + exact pins) | — |
| [Terraform](docs/terraform.md#terraform) / [OpenTofu](docs/terraform.md#opentofu) | ❌ No | — | (use exact `=` pins + Dependabot²) | — |

---

## Version Constraint Support

Loose version constraints are one of the most common vectors for supply chain attacks. When a manifest allows a range (`^1.0.0`, `>=1.0.0`, `~=1.0`), any newly published version matching that range can be silently pulled in — particularly during fresh installs, dependency updates, or CI runs that don't enforce a lockfile. A compromised maintainer account publishing `1.0.1` with malicious code will satisfy `^1.0.0` in every consuming project that doesn't pin exactly.

The lockfile provides a partial mitigation — it pins exact resolved versions — but it only protects you when it is actively enforced (e.g. `npm ci`, `uv sync --frozen`). A developer running a bare `npm install` or `pip install -r requirements.txt` against a loose manifest will re-resolve within the allowed range and can pull in a version the lockfile never saw.

| Package Manager | Default Constraint | Loose Syntax (avoid) | Exact Syntax (use) | Lockfile pins exact? | Enforce exact via |
|---|---|---|---|---|---|
| [npm](docs/nodejs.md#npm) | `^` (minor+patch) | `^1.0.0` `~1.0.0` `>=1.0.0` `*` | `1.0.0` | ✅ Yes — `npm ci` enforces it | `save-exact=true` in `.npmrc` |
| [pnpm](docs/nodejs.md#pnpm) | `^` (minor+patch) | `^1.0.0` `~1.0.0` `>=1.0.0` | `1.0.0` | ✅ Yes — `--frozen-lockfile` | `save-exact=true` in `.npmrc` |
| [Yarn Classic](docs/nodejs.md#yarn-classic) / [Berry](docs/nodejs.md#yarn-berry) | `^` (minor+patch) | `^1.0.0` `~1.0.0` `>=1.0.0` | `1.0.0` | ✅ Yes — `--immutable` | `defaultSemverRangePrefix: ""` in `.yarnrc.yml` |
| [Bun](docs/nodejs.md#bun) | `^` (minor+patch) | `^1.0.0` `~1.0.0` `>=1.0.0` | `1.0.0` | ✅ Yes — `--frozen-lockfile` | `exact = true` in `bunfig.toml` |
| [pip](docs/python.md#pip) | None (user-specified) | `>=1.0.0` `~=1.0.0` `!=1.0.0` | `==1.0.0` | ❌ No native lockfile | `pip-compile --generate-hashes`; always use `==` |
| [uv](docs/python.md#uv) | None (user-specified) | `>=1.0.0` `~=1.0.0` | `==1.0.0` | ✅ Yes — `uv sync --frozen` | `require-hashes = true` in `[tool.uv]` |
| [Go modules](docs/go.md#go-modules) | MVS minimum¹ | `@latest` `@master` | `@v1.9.1` | ✅ Yes — `go.sum` hashes | Never use `@latest`; always specify a tagged version |
| [Cargo](docs/rust.md#cargo-rust) | `^` (caret, implicit) | `1.0.0` `^1.0.0` `~1.0.0` `>=1.0.0` | `=1.0.0` | ✅ Yes — `--locked` | Use `=` prefix explicitly in `Cargo.toml` |
| [Composer](docs/php.md#composer) | `^` (caret) | `^1.2.3` `~1.2.3` `>=1.0` `1.2.*` | `1.2.3` | ✅ Yes — `composer install` enforces it | Use bare version strings in `composer.json` |
| [Terraform](docs/terraform.md#terraform) / [OpenTofu](docs/terraform.md#opentofu) | `~>` (patch-only by default²) | `~> 5.0` `>= 5.0` `>= 5.0, < 6.0` | `= 5.31.0` | ✅ Yes — `.terraform.lock.hcl`; `-lockfile=readonly` | Use `= X.Y.Z` in `required_providers`; run `terraform providers lock` for multi-platform hashes |

**¹ Go's Minimum Version Selection (MVS)** works differently from other package managers. A `require` directive specifies the *minimum acceptable version*, and Go always resolves to that exact version (never newer) unless you explicitly run `go get -u`. This makes Go more conservative by default — it will not silently adopt new versions without an explicit developer action. However, `go get -u` and `go get @latest` bypass this safety and should be avoided in favour of pinning explicit tagged versions.

**² Terraform and OpenTofu `~>` semantics:** The pessimistic constraint `~> 5.0` allows any `5.x` release (equivalent to `>= 5.0, < 6.0`), while `~> 5.31.0` allows only `5.31.x` patch releases. Neither form is as restrictive as exact pinning. Unlike other ecosystems there is also no native cooldown — the `.terraform.lock.hcl` lockfile records hashes of the resolved version but does not prevent automatic adoption of new versions when `terraform init -upgrade` is run or when Dependabot opens a PR. Exact pinning with `= 5.31.0` is the only reliable defence. Note: Dependabot cooldown for the `terraform` ecosystem is affected by a known bug (GitHub issue [#13715](https://github.com/dependabot/dependabot-core/issues/13715)) that may prevent provider updates from respecting cooldown days — use exact pinning as the primary control.

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
- [Composer Documentation](https://getcomposer.org/doc/)
- [Composer Version Constraints](https://getcomposer.org/doc/articles/versions.md)
- [Composer Security Audit](https://php.watch/articles/composer-audit)
- [roave/security-advisories](https://github.com/Roave/SecurityAdvisories)
- [local-php-security-checker](https://github.com/fabpot/local-php-security-checker)
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

