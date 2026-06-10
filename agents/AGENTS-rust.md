<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Agent Instructions: Rust/Cargo Dependency Management

This file contains mandatory guidelines for managing dependencies in this Rust project. Follow these rules whenever adding, updating, or removing crates, or modifying CI configuration.

## Hash Verification: Never Fabricate

**AI agents must never invent, guess, autocomplete, or extrapolate a `Cargo.lock` checksum, a `[source.<name>] replace-with` SHA, a `cargo-vet` audit hash, or a git `rev = "..."` commit SHA.** A fabricated hash either fails verification or silently pins to the wrong artifact.

All `Cargo.lock` checksums must be produced by Cargo itself — run `cargo update -p <crate>` / `cargo generate-lockfile` and commit the result. Do not hand-edit `checksum = "..."` lines.

To confirm a published crate's checksum or a git commit:

**Preferred:** if the `harden-packages` skill is available, use its helper:

```bash
python {SKILL_DIR}/verify_hash.py crate <crate> <version>         # → SHA256
python {SKILL_DIR}/verify_hash.py gh-action <owner>/<repo> <ref>  # for git-sourced crates
```

**Fallback:** `curl -fsSL https://crates.io/api/v1/crates/<crate>/<version> | jq '.version | {num, checksum, dl_path}'`.

If you cannot verify a hash with any of the above, **stop and ask the user**. Do not insert a placeholder or a "likely correct" value.

## Crate Names: Never Guess

**AI agents must never add a crate whose exact name they have not verified against crates.io in the current session.** Typosquatting and slopsquatting — attackers registering names that language models tend to invent — are actively exploited vectors. A guessed name either fails to resolve or resolves to a malicious look-alike.

Before adding any new crate:

1. Verify the exact name and confirm it is the crate you intend: check `https://crates.io/crates/<crate>` (or `curl -fsSL https://crates.io/api/v1/crates/<crate> | jq '{name: .crate.name, description: .crate.description, repository: .crate.repository}'`) — the description and linked repository must match the stated purpose.
2. Treat as red flags: a very recent first release, a name differing from a popular crate by a hyphen/underscore swap or one character, a missing or unrelated repository link, and low download counts for a supposedly well-known crate.

If the lookup is ambiguous or the crate cannot be confidently identified, **stop and ask the user** — do not choose between similar names on intuition.

## Dependency Rules

**Always pin exact versions** using the `=` operator in `Cargo.toml`. Never use bare version strings, `>=`, or `~` ranges for production dependencies:

```toml
# correct
[dependencies]
serde = { version = "=1.0.196", features = ["derive"] }
tokio = { version = "=1.36.0", features = ["full"] }

# incorrect — do not use
[dependencies]
serde = "1"
serde = "1.0"
serde = ">=1.0"
serde = "~1.0"
```

**Never add a crate version published within the last 7 days.** Check the publication date on crates.io before adding any new dependency. If a version was published less than 7 days ago, defer the addition until the cooldown has elapsed. Use `cargo-cooldown` (configured below) to enforce this automatically.

**Always commit `Cargo.lock` for binaries and applications.** For library crates intended for downstream use, follow the project's established convention. When in doubt, commit it.

**When updating a single crate, use `--precise`** to avoid pulling in unintended version changes:

```bash
cargo update --precise 1.0.197 -p serde
```

## Configuration to Verify

**`cargo-cooldown`** must be installed and used in place of bare `cargo` commands for build and test operations:

```bash
cargo install cargo-cooldown
```

Configure a default cooldown in `.cargo/config.toml`:

```toml
[cooldown]
days = 7
```

Then invoke via:

```bash
cargo cooldown --days 7 build
cargo cooldown --days 7 test
```

**Feature flags:** Minimise enabled features to reduce attack surface. Only enable features explicitly required:

```toml
[dependencies]
openssl = { version = "=0.10.64", default-features = false, features = ["v102", "v110"] }
```

## CI Commands

```bash
cargo fetch --locked              # pre-fetch with lockfile enforcement
cargo build --locked --release    # fail if Cargo.lock is out of sync
cargo test --locked               # test with lockfile enforcement
cargo audit --deny warnings       # fail on any RustSec advisory
```

Install `cargo-audit` if not present:

```bash
cargo install cargo-audit
```

## Security Audit

Run `cargo audit` whenever dependencies change:

```bash
cargo audit                        # check against RustSec advisory DB
cargo audit --deny warnings        # stricter: fail on informational advisories too
```

If the audit reports vulnerabilities, do not merge the change until they are resolved or explicitly acknowledged with a documented justification.

## CI Configuration

### Dependabot

`.github/dependabot.yml` must include a cooldown for `cargo`. If the file does not exist or lacks a cooldown block, add it:

```yaml
version: 2
updates:
  - package-ecosystem: "cargo"
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

Every GitHub Actions workflow that fetches crates must include `step-security/harden-runner` as its first step. New workflows must not be added without it.

Start in `audit` mode for new workflows, then tighten to `block` once the egress policy is stable:

```yaml
- uses: step-security/harden-runner@6c3c2f2c1c457b00c10c4848d6f5491db3b629df # v2
  with:
    egress-policy: block
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      crates.io:443
      index.crates.io:443
      static.crates.io:443
```

## Workspace Projects

For workspace projects, declare shared dependency versions in the root `Cargo.toml` and inherit them in member crates:

```toml
# Cargo.toml (workspace root)
[workspace.dependencies]
serde = { version = "=1.0.196", features = ["derive"] }
```

```toml
# crates/mylib/Cargo.toml
[dependencies]
serde = { workspace = true }
```

This ensures version pins are maintained in a single location.

## What Requires Human Review

The following changes must not be made autonomously and require explicit human approval before proceeding:

- Adding a new crate not previously present in `Cargo.toml`
- Upgrading a major version
- Changing `=` pins to `>=` or bare version ranges
- Adding a crate to build script allowlists
- Modifying `.github/dependabot.yml` cooldown values downward
- Removing or modifying Harden-Runner from a workflow
- Disabling `--locked` in CI build or test commands
