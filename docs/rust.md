<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Cargo (Rust)

**Configuration files:** `Cargo.toml`, `Cargo.lock`, `.cargo/config.toml`

## Cargo.lock

Cargo always generates `Cargo.lock` for workspace/binary crates. **Always commit `Cargo.lock` for applications and binaries.** For libraries, the convention is to not commit it (so downstream users get fresh resolution), though committing it for internal libraries is reasonable.

```bash
cargo build                   # generates/updates Cargo.lock
cargo update                  # update all dependencies to latest compatible
cargo update --precise 1.0.1 -p serde  # update one dep to an exact version
```

In CI, use `--locked` to fail if `Cargo.lock` is out of sync with `Cargo.toml`:

```bash
cargo build --locked
cargo test --locked
```

## Version Pinning

In `Cargo.toml`, use exact version requirements with `=`:

```toml
[dependencies]
serde = { version = "=1.0.196", features = ["derive"] }
tokio = { version = "=1.36.0", features = ["full"] }
reqwest = { version = "=0.11.27", features = ["json", "rustls-tls"] }
```

To update a single dependency to a precise version without accepting any semver-compatible alternatives:

```bash
cargo update --precise 1.0.197 -p serde
```

## Registry Configuration

```toml
# .cargo/config.toml

[registry]
default = "my-registry"   # override default registry (default: crates.io)

[registries.my-registry]
index = "sparse+https://your-registry.example.com/index/"
# or git index:
# index = "https://your-registry.example.com/git/index"

[registries.crates-io]
token = "your-crates-io-token"   # or use CARGO_REGISTRY_TOKEN env var

[registries.my-registry]
token = "${MY_REGISTRY_TOKEN}"
```

Authentication via environment variables:

```bash
CARGO_REGISTRY_TOKEN="your-crates-io-token"
CARGO_REGISTRIES_MY_REGISTRY_TOKEN="your-internal-token"
```

## Source Replacement

Source replacement redirects all fetches of one registry to another — useful for routing through an internal mirror without changing `Cargo.toml` files:

```toml
# .cargo/config.toml

[source.crates-io]
replace-with = "internal-mirror"

[source.internal-mirror]
registry = "sparse+https://your-mirror.example.com/index/"
```

All crates.io fetches now go through your mirror. Individual crate `Cargo.toml` files do not need to change.

## Security: Minimum Release Age

### Native (Cargo ≥ 1.100)

Cargo 1.100 (November 2026) stabilised a minimum publish age for dependency resolution. Set it in `.cargo/config.toml`:

```toml
# .cargo/config.toml
[registry]
global-min-publish-age = "7 days"
```

The value is a string: an integer followed by `seconds`, `minutes`, `hours`, `days`, `weeks` or `months`, or `"0"` to disable. A single registry can be overridden with `[registries.<name>] min-publish-age`, and the environment variable `CARGO_REGISTRY_GLOBAL_MIN_PUBLISH_AGE` sets the same value.

Limits to know about:

- Cargo older than 1.100 ignores the key, so pin the toolchain (`rust-toolchain.toml`) to 1.100 or later wherever the gate must hold.
- `cargo install` ignores the minimum publish age.
- The gate applies when Cargo resolves versions, not when it builds from an existing `Cargo.lock`. A crate that is already in the lockfile builds whatever its age, so a pull request that edits `Cargo.lock` to a too-new version passes `cargo build --locked`; only a re-resolve such as `cargo update` applies the gate (observed on Cargo 1.100.0, where `cargo update` then moved the crate back to an older version). Review lockfile changes, and rely on a Dependabot cooldown or `cargo-vet` to cover that path.
- Versions with no `pubtime` in the registry index are never held back.
- The table is `[registry]` with the `global-` prefix. `[registry] min-publish-age` is not a native key.

### Older toolchains: cargo-cooldown

For Cargo older than 1.100, the community [`cargo-cooldown`](https://crates.io/crates/cargo-cooldown) plugin (≥ 0.3.1) reads the same key from its own file, `cooldown.toml`, in the workspace root:

```toml
# cooldown.toml
[registry]
global-min-publish-age = "7 days"
```

```bash
cargo install cargo-cooldown --locked
cargo cooldown build
cargo cooldown test
```

cargo-cooldown's own documentation recommends the native setting once you are on Cargo 1.100 or later.

> **Two forms that do nothing.** A `[cooldown]` table with `days = 7` in `.cargo/config.toml` is read by neither Cargo nor cargo-cooldown, and `cargo cooldown --days 7` is not a valid flag. Both leave freshly published crates free to enter `Cargo.lock` with no warning. Earlier revisions of this guide showed both; replace them with one of the forms above.

## Security: Cargo Audit

```bash
cargo install cargo-audit
cargo audit                           # audit Cargo.lock against RustSec advisory DB
cargo audit --deny warnings           # fail on any advisory (including informational)
cargo audit fix                       # attempt to auto-upgrade vulnerable dependencies
```

For CI integration:

```bash
cargo audit --json | jq '.vulnerabilities.found'
```

## Security: Dependency Features and Build Scripts

Restrict unnecessary features to reduce attack surface:

```toml
[dependencies]
openssl = { version = "=0.10.64", features = [], default-features = false }
```

Disable build scripts for a specific dependency (use with caution — may break packages that require them):

```toml
# Cargo.toml
[patch.crates-io]
some-package = { path = "../patched-some-package" }
```

To audit which packages run build scripts:

```bash
cargo metadata --format-version 1 --locked \
  | jq -r '.packages[] | select(any(.targets[]; .kind[] == "custom-build")) | "\(.name) \(.version)"'
```

`cargo metadata` marks a build script as a target of kind `custom-build`. Do not use `cargo build --build-plan`: it was a nightly-only flag and was removed in Cargo 1.93, so on current toolchains it errors, and with stderr discarded the pipeline prints nothing, which reads as "no build scripts".

## Offline Mode

```bash
cargo build --offline    # use only locally cached crates
cargo fetch              # pre-fetch all dependencies (useful in CI setup step)
```

```toml
# .cargo/config.toml
[net]
offline = true   # always run offline
```

## Workspace / Monorepo

```toml
# Cargo.toml (workspace root)
[workspace]
members = ["crates/*", "services/*"]
resolver = "2"   # use Cargo's v2 feature resolver (recommended)

[workspace.dependencies]
# Declare shared dependency versions once
serde = { version = "=1.0.196", features = ["derive"] }
tokio = { version = "=1.36.0", features = ["full"] }
```

Individual crates inherit from workspace:

```toml
# crates/mylib/Cargo.toml
[dependencies]
serde = { workspace = true }
tokio = { workspace = true }
```

```bash
cargo build --workspace          # build all workspace members
cargo test --workspace --locked  # test all members with lockfile
cargo update -p serde            # update one dep across entire workspace
```

## CI Recommended Configuration

```toml
# .cargo/config.toml
[net]
retry = 3

[build]
jobs = 4   # parallelism
```

```bash
# CI commands
cargo fetch --locked
cargo build --locked --release
cargo test --locked
cargo audit --deny warnings
```

---
