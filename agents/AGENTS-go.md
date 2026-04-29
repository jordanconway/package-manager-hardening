<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Agent Instructions: Go Dependency Management

This file contains mandatory guidelines for managing dependencies in this Go module project. Follow these rules whenever adding, updating, or removing modules, or modifying CI configuration.

## Dependency Rules

**Always pin explicit versions.** Never use `@latest` or `@master` when adding or updating a module. Always specify a tagged version:

```bash
# correct
go get github.com/gin-gonic/gin@v1.9.1

# incorrect — do not use
go get github.com/gin-gonic/gin@latest
go get github.com/gin-gonic/gin@master
```

**Never add a module version published within the last 7 days.** Check the release date on pkg.go.dev or the module's VCS before adding any new dependency. If a version was published less than 7 days ago, defer the addition until the cooldown has elapsed. Use Dependabot (configured below) for automated updates, which enforces the cooldown automatically.

**Always commit both `go.mod` and `go.sum`.** These files are the source of truth for dependency versions and integrity hashes. Never add them to `.gitignore`.

**Run `go mod tidy` after any dependency change** and commit the result. A dirty `go.mod` or `go.sum` is a CI failure.

**Never disable the checksum database** (`GONOSUMDB`, `GONOSUMCHECK`) for public modules. Only set `GOPRIVATE` / `GONOSUMDB` for modules hosted on internal infrastructure:

```bash
# correct — scoped to internal modules only
GOPRIVATE="github.com/myorg/*"

# incorrect — disabling sum checks for public modules
GONOSUMDB="*"
```

## CI Verification

Run these checks in CI in this exact order — integrity checks must run **before** the build so a tampered or stale module graph never reaches the compiler:

```bash
go mod verify                                # verify hashes against go.sum
go mod tidy                                  # ensure go.mod/go.sum are clean
git diff --exit-code -- go.mod go.sum        # fail if either file was modified
# ... build and test steps ...
govulncheck ./...                            # scan for known vulnerabilities
```

Note the `--` separator in the `git diff` invocation — it unambiguously separates flags from pathspecs and must always be present.

`govulncheck` is the preferred vulnerability scanner for Go — it checks whether vulnerable code paths are actually reachable in your binary, not just whether a module is present. It reads the `go` directive in `go.mod` as the stdlib version baseline, so the `go` directive must include the full patch version (see below).

Install it with a pinned version — never `@latest`:

```bash
go install golang.org/x/vuln/cmd/govulncheck@v1.3.0
```

## Environment Configuration

Set the following in your CI environment:

```bash
GOPROXY="https://proxy.golang.org,direct"
GOPRIVATE="github.com/myorg/*"        # adjust to your org
GONOSUMDB="github.com/myorg/*"        # matches GOPRIVATE
GOTOOLCHAIN=local                     # prevent runtime toolchain auto-fetch
```

`GOTOOLCHAIN=local` prevents the `go` binary from silently downloading a different toolchain version at runtime, even after `actions/setup-go` has installed the intended version. Always set it in CI.

## CI Configuration

### Dependabot

Go modules have no native cooldown mechanism. Dependabot is the primary control for preventing adoption of recently published versions. `.github/dependabot.yml` must include a cooldown for `gomod`. If the file does not exist or lacks a cooldown block, add it:

```yaml
version: 2
updates:
  - package-ecosystem: "gomod"
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

Every GitHub Actions workflow that downloads modules must include `step-security/harden-runner` as its first step. New workflows must not be added without it.

Pin to a commit SHA — never use a mutable tag like `@v2`. Start in `audit` mode for new workflows, then tighten to `block` once the egress policy is stable:

```yaml
- uses: step-security/harden-runner@<SHA>  # replace with current SHA for desired version
  with:
    egress-policy: audit
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      proxy.golang.org:443
      sum.golang.org:443
      storage.googleapis.com:443
```

Add any private module hosts to `allowed-endpoints` as needed.

Jobs that use a reusable workflow at the job level (`uses:` as a job-level key rather than a step key) cannot receive a `steps:` block and therefore cannot have harden-runner added to them. These job-level `uses:` references are still mutable refs and must be SHA-pinned, but they are audited separately from harden-runner coverage.

## go Directive and Toolchain Pinning

The `go` directive in `go.mod` must include the **full patch version**, e.g.:

```
go 1.25.9
```

not just the minor version (`go 1.25`) or the base patch (`go 1.25.0`).

`govulncheck` reads the `go` directive — not `go env GOVERSION` — as the stdlib baseline for CVE analysis. With `go 1.25.0`, govulncheck will report all CVEs fixed in go1.25.1 through the latest patch as active, even if the installed toolchain is already patched.

Additionally, `go mod tidy` preserves fully-specified patch versions (`go 1.25.9`) but normalises bare minor versions: `go 1.25` becomes `go 1.25.0`. Committing `go 1.25` would cause a tidy-diff CI check to fail on every run.

Do **not** split a patch-versioned directive into `go 1.25` + `toolchain go1.25.9`. The `toolchain` directive is not read by `govulncheck` for CVE analysis — only the `go` directive is. When both directives name the same version, `go mod tidy` removes the redundant `toolchain` line automatically.

**Stdlib CVEs** cannot be fixed by bumping a `require` entry — they require upgrading the `go` directive to the patched Go release. When `govulncheck` reports stdlib findings, check the "Fixed in" version and update the `go` directive accordingly.

## go install Pinning

Every `go install` invocation — whether in a Makefile, shell script, or CI workflow — must pin an explicit version:

```bash
# correct
go install golang.org/x/vuln/cmd/govulncheck@v1.3.0
go install goa.design/goa/v3/cmd/goa@v3.23.4

# incorrect — never use these
go install golang.org/x/vuln/cmd/govulncheck@latest
go install tool@master
```

`@latest` is the same supply-chain risk as an unpinned GitHub Action. The go sum database verifies the hash of whatever version resolves, but the version itself is mutable — a new release can change behaviour or introduce malicious code without warning.

Also audit CI jobs that call a Makefile target (e.g. `make deps`) to ensure they don't install tools the job never uses. If a `deps` target installs a linter and the CI job never runs `make lint`, extract only the needed commands rather than running the full target.

## What Requires Human Review

The following changes must not be made autonomously and require explicit human approval before proceeding:

- Adding a new module not previously present in `go.mod`
- Upgrading a major version (v1 → v2, etc.)
- Setting `GONOSUMDB` or `GONOSUMCHECK` for any public module
- Modifying `.github/dependabot.yml` cooldown values downward
- Removing or modifying Harden-Runner from a workflow
- Vendoring or un-vendoring dependencies
