# Dependabot Integration


Configure cooldowns in `.github/dependabot.yml`. Each `updates` entry can have its own `cooldown` block with per-semver-level granularity:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30  # extra caution on breaking changes
      semver-minor-days: 7
      semver-patch-days: 3

  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7

  - package-ecosystem: "gomod"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30

  - package-ecosystem: "cargo"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
```

Per-package overrides using `include` and `exclude`:

```yaml
    cooldown:
      default-days: 7
      exclude:
        - dependency-name: "critical-security-dep"  # bypass cooldown for this package
      include:
        - dependency-name: "very-active-package"
          days: 14                                  # stricter cooldown for specific package
```

**Key behaviours to note:**

- Cooldown values must be between 1 and 90 days.
- **Security update PRs automatically bypass the cooldown** — a CVE-triggered Dependabot PR is never delayed, regardless of `cooldown` settings.
- Cooldown only gates automated version update PRs. A developer running `npm install foo` or `go get` locally bypasses it entirely.
- Supported for all ecosystems including npm, pip, gomod, cargo, NuGet, Helm, and more.

