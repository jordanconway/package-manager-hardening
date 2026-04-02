# Package Manager Security Hardening

A comprehensive reference for configuring npm, pnpm, Yarn, Bun, pip, uv, Go modules, Cargo, Terraform, and OpenTofu — covering lockfiles, version pinning, registry configuration, minimum release age, and CI/CD hardening.

---

## Quick start

**For AI coding assistants:** copy a ready-made `AGENTS.md` into your repo to give your agent standing dependency-management instructions:

```bash
# Pick the one that matches your stack
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/AGENTS-nodejs.md
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/AGENTS-python.md
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/AGENTS-go.md
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/AGENTS-rust.md
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/AGENTS-terraform.md
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

## Version Constraint Support

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

---

## What's in this repo

```
AGENTS-nodejs.md          ← copy to your Node.js repo as AGENTS.md
AGENTS-python.md          ← copy to your Python repo as AGENTS.md
AGENTS-go.md              ← copy to your Go repo as AGENTS.md
AGENTS-rust.md            ← copy to your Rust repo as AGENTS.md
AGENTS-terraform.md       ← copy to your Terraform/OpenTofu repo as AGENTS.md
skills/
  harden-packages/        ← copy to ~/.claude/skills/ to install the audit skill
docs/                     ← detailed reference docs for each ecosystem and control
```
