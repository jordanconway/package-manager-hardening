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

## Security: Minimum Release Age via cargo-cooldown

Cargo has no native cooldown feature. The `cargo-cooldown` crate (community tool, September 2025) wraps Cargo and enforces a configurable cooldown window before freshly published crates can enter your dependency graph:

```bash
cargo install cargo-cooldown

# Enforce a 7-day cooldown on all dependency resolution
cargo cooldown --days 7 build
cargo cooldown --days 7 test

# Or set a default cooldown in config
```

```toml
# .cargo/config.toml
[cooldown]
days = 7
```

> **Note:** `cargo-cooldown` is a community wrapper, not a native Cargo feature. Crates.io added a `pubtime` field to the registry index (providing publication timestamps) which enables this tooling, but native cooldown support in Cargo itself is not yet available.

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
cargo build --build-plan 2>/dev/null | jq '.invocations[].program'
```

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

