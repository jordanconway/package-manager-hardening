# Agent Instructions: Rust/Cargo Dependency Management

This file contains mandatory guidelines for managing dependencies in this Rust project. Follow these rules whenever adding, updating, or removing crates, or modifying CI configuration.

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
- uses: step-security/harden-runner@v2
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
