# Go Modules


**Configuration files:** `go.mod`, `go.sum`, environment variables (set in shell profile or CI)

Go's module system is built into the `go` toolchain — there is no separate package manager to install.

## go.mod and go.sum

`go.mod` declares the module path and all direct dependencies with minimum version requirements. `go.sum` records cryptographic hashes for all direct and transitive dependencies. Both files must be committed to source control.

```
// go.mod
module github.com/myorg/myapp

go 1.22

require (
    github.com/gin-gonic/gin v1.9.1
    github.com/jackc/pgx/v5 v5.5.4
)

require (
    // indirect dependencies managed automatically
    github.com/bytedance/sonic v1.11.2 // indirect
)
```

```bash
go mod tidy              # add missing, remove unused dependencies
go mod verify            # verify module hashes against go.sum
go mod download          # download all modules to local cache
```

## Version Pinning

Dependency versions in `go.mod` are exact — Go uses Minimum Version Selection (MVS), which always resolves to the *minimum* version satisfying all constraints, never a newer one. This makes Go's resolution deterministic without needing a separate lockfile.

To pin to a specific version:

```bash
go get github.com/gin-gonic/gin@v1.9.1
```

To update a specific dependency:

```bash
go get -u github.com/gin-gonic/gin@latest   # update to latest
go get github.com/gin-gonic/gin@v1.10.0     # update to specific version
```

## Checksum Database (GOSUMDB)

Go verifies all module downloads against `sum.golang.org` by default. This provides cryptographic integrity guarantees without requiring a lockfile.

```bash
# Disable checksum database (not recommended)
GONOSUMDB="github.com/my-private-repo/*"

# Use a custom checksum database
GOSUMDB="sum.golang.org"

# Bypass sum check entirely (use with caution)
GONOSUMCHECK="github.com/internal/*"
```

## Module Proxy Configuration

By default, Go downloads modules through `proxy.golang.org`. Configure alternatives via `GOPROXY`:

```bash
# Default: try proxy, fall back to direct
GOPROXY="https://proxy.golang.org,direct"

# Private mirror or GOPROXY-compatible proxy
GOPROXY="https://your-proxy.example.com,direct"

# Disable proxy (fetch direct from VCS)
GOPROXY="direct"

# Offline mode only (use local cache)
GOPROXY="off"
```

Exclude specific modules from the proxy (e.g., private repos):

```bash
GOPRIVATE="github.com/myorg/*,gitlab.mycompany.com/*"
```

`GOPRIVATE` automatically sets both `GONOSUMDB` and `GONOPROXY` for the matched patterns.

## Security: No Native Minimum Release Age

Go has no native time-delay or cooldown mechanism. The best available options are:

- **Dependabot `cooldown`:** Prevents automated dependency PRs from adopting versions published within a configurable window. Security update PRs automatically bypass the cooldown. Does not gate manual `go get` invocations.
- **Explicit version pinning in go.mod:** Never use `@latest` in production workflows; always pin explicit versions.
- **GONOSUMDB + private proxy:** Route Go module fetches through a controlled proxy where new versions can be reviewed before becoming available.

## Vendoring

For air-gapped environments or extra reproducibility, vendor all dependencies:

```bash
go mod vendor                    # copy all dependencies into ./vendor/
go build -mod=vendor ./...       # build using only vendored modules
go test -mod=vendor ./...        # test using only vendored modules
```

In CI, enforce vendor directory is up to date:

```bash
go mod vendor
git diff --exit-code vendor/     # fail if vendor/ was modified
```

## CI Recommended Configuration

```bash
# go.env or CI environment
GOPROXY="https://proxy.golang.org,direct"
GOPRIVATE="github.com/myorg/*"
GONOSUMDB="github.com/myorg/*"

# CI commands
go mod verify
go mod tidy
git diff --exit-code go.mod go.sum   # fail if go.mod/go.sum was modified
```

---

