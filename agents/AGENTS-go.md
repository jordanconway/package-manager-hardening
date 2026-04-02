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

Run these checks in CI to enforce lockfile integrity:

```bash
go mod verify                              # verify hashes against go.sum
go mod tidy                                # ensure go.mod/go.sum are clean
git diff --exit-code go.mod go.sum         # fail if either file was modified
govulncheck ./...                          # scan for known vulnerabilities
```

`govulncheck` is the preferred vulnerability scanner for Go — it checks whether vulnerable code paths are actually reachable in your binary, not just whether a module is present.

Install it with:
```bash
go install golang.org/x/vuln/cmd/govulncheck@latest
```

## Environment Configuration

Set the following in your CI environment:

```bash
GOPROXY="https://proxy.golang.org,direct"
GOPRIVATE="github.com/myorg/*"        # adjust to your org
GONOSUMDB="github.com/myorg/*"        # matches GOPRIVATE
```

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
      proxy.golang.org:443
      sum.golang.org:443
      storage.googleapis.com:443
```

Add any private module hosts to `allowed-endpoints` as needed.

## What Requires Human Review

The following changes must not be made autonomously and require explicit human approval before proceeding:

- Adding a new module not previously present in `go.mod`
- Upgrading a major version (v1 → v2, etc.)
- Setting `GONOSUMDB` or `GONOSUMCHECK` for any public module
- Modifying `.github/dependabot.yml` cooldown values downward
- Removing or modifying Harden-Runner from a workflow
- Vendoring or un-vendoring dependencies
