<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

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

  # uv reads pyproject.toml [project.dependencies] and [dependency-groups].
  # Inline `pip install x==y` lines in workflow files are NOT updated by
  # any ecosystem — move dev tooling into a [dependency-groups] entry to
  # make it visible to Dependabot.
  - package-ecosystem: "uv"
    directory: "/"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 7
      semver-major-days: 30
      semver-minor-days: 7
      semver-patch-days: 3

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
- **`github-actions` ecosystem special case:** action tags (`v4`, `v4.1.2`) aren't always parsed as SemVer by Dependabot, so `semver-major-days` / `semver-minor-days` / `semver-patch-days` do not reliably apply. For the `github-actions` ecosystem, rely on `default-days` only.
- **Security update PRs automatically bypass the cooldown** — a CVE-triggered Dependabot PR is never delayed, regardless of `cooldown` settings.
- Cooldown only gates automated version update PRs. A developer running `npm install foo` or `go get` locally bypasses it entirely.
- Supported for all ecosystems including npm, pip, gomod, cargo, NuGet, and more — but **not Helm chart dependencies**, which Dependabot does not update at all.

**Alternative:** [Renovate](renovate.md) provides the equivalent cooldown (`minimumReleaseAge`) across every manager it supports, with per-package rules and a dependency dashboard showing held-back updates. See the comparison table in that doc for when to prefer which.

## Cooldown: resolver-level vs Dependabot — pick one

Several ecosystems can enforce a release-age cooldown at the **resolver level** —
uv `exclude-newer`, npm `minimum-release-age`, pnpm/Bun `minimumReleaseAge`, Yarn
`npmMinimalAgeGate`, `cargo-cooldown`. The Dependabot `cooldown` block enforces the **same
control at the PR level**. They are not complementary layers to stack — configuring **both for
the same ecosystem is counter-productive**:

| | Resolver-level cooldown | Dependabot cooldown |
|---|---|---|
| Scope | Full resolved graph, incl. transitives; also local installs | Direct dependencies; PR-level |
| Security-update exception | ❌ **None** — a hard date filter | ✅ CVE-triggered PRs bypass the cooldown |
| Bypass for a specific fix | Manual per-package exemption + lockfile regen | Automatic |

The decisive asymmetry is the security-update exception. When both are set, Dependabot
correctly tries to ship a just-published security fix, but the resolver-level cooldown filters
that version out during resolution — so the update becomes unsatisfiable and requires **three
manual changes** (raise the version floor, add a per-package cooldown exemption, regenerate the
lockfile) plus a review that a plain Dependabot bump would not have needed. The resolver-level
cooldown silently defeats the automation you configured Dependabot for.

**Recommendation: prioritise Dependabot.** For most repositories the Dependabot (or
[Renovate](renovate.md)) cooldown is the better single control — security fixes keep flowing
automatically, and a maintainer can merge the bump without extra ceremony. Reach for a
resolver-level cooldown only when you specifically need full-graph / transitive coverage or
protection against local `install` commands, and in that case **do not also run a Dependabot
cooldown** for that ecosystem — accept that security fixes will need a manual per-package
exemption.

The [harden-packages audit](skill.md) reflects this: the cooldown control is satisfied by
**either** mechanism, and it **warns when both are configured** for the same ecosystem. The
`cooldown-strategy` input (`auto` / `dependabot` / `resolver`) lets an organisation declare its
posture explicitly — `dependabot` flags any resolver-level cooldown as redundant.
