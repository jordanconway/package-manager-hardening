<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Renovate Integration

Renovate is an alternative to Dependabot for automated dependency updates. For supply chain
hardening it has one decisive advantage: **`minimumReleaseAge` works for every package manager
Renovate supports**, including the ecosystems where neither the package manager nor Dependabot
provides a reliable cooldown — Maven, Gradle, Go modules, Composer, Bundler, NuGet, Helm, and
Terraform.

The [Transitive Dependency Coverage](transitive.md) matrix marks those ecosystems ❌ for native
age gates. Renovate closes that gap at the PR level: an update PR is not offered until the new
version has been published for at least the configured window.

## Configuration

Renovate reads `renovate.json` (or `.github/renovate.json`, `renovate.json5`,
`.renovaterc.json`) in the repository root:

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended"],
  "minimumReleaseAge": "7 days",
  "internalChecksFilter": "strict",
  "dependencyDashboard": true,
  "osvVulnerabilityAlerts": true,
  "packageRules": [
    {
      "matchUpdateTypes": ["major"],
      "minimumReleaseAge": "30 days"
    },
    {
      "matchUpdateTypes": ["patch"],
      "minimumReleaseAge": "3 days"
    }
  ]
}
```

**Key settings:**

- **`minimumReleaseAge`** — the cooldown window. Accepts human-readable durations
  (`"3 days"`, `"2 weeks"`). Applies to every manager in the repository unless overridden
  in a `packageRules` entry.
- **`internalChecksFilter: "strict"`** — when several new versions exist, propose the newest
  one that *satisfies* the age window instead of waiting for the very latest to age. Without
  this, a package releasing frequently can keep resetting the clock and never produce an
  update PR.
- **`packageRules`** — per-update-type, per-manager, or per-package overrides. The example
  above mirrors the Dependabot semver-level convention used elsewhere in this repository
  (30 days major / 7 days minor / 3 days patch).
- **`osvVulnerabilityAlerts`** — raise PRs for OSV-database vulnerabilities in addition to
  GitHub Security Advisories.
- **`dependencyDashboard`** — creates a tracking issue listing updates currently held by the
  age window, so delayed updates are visible rather than silent.

Security-alert PRs (from `vulnerabilityAlerts` / `osvVulnerabilityAlerts`) bypass
`minimumReleaseAge` — a fix for a disclosed CVE is never delayed, matching Dependabot's
cooldown-bypass behaviour.

## Per-manager cooldowns for the gap ecosystems

A `packageRules` entry scoped with `matchManagers` applies the window only where you need it —
useful if Dependabot handles some ecosystems and Renovate covers the rest:

```json
{
  "packageRules": [
    {
      "matchManagers": ["maven", "gradle", "gomod", "composer", "bundler", "nuget", "helmv3", "terraform"],
      "minimumReleaseAge": "7 days"
    }
  ]
}
```

## Renovate vs Dependabot

| | Dependabot | Renovate |
|---|---|---|
| Cooldown mechanism | `cooldown` block per ecosystem | `minimumReleaseAge` global or per-rule |
| Cooldown ecosystem coverage | All supported ecosystems, but [known Terraform provider bug](https://github.com/dependabot/dependabot-core/issues/13715) | All supported managers, including Helm chart dependencies (which Dependabot doesn't update at all) |
| Semver-level windows | `semver-major/minor/patch-days` keys | `packageRules` + `matchUpdateTypes` |
| Per-package overrides | `include` / `exclude` lists | `packageRules` + `matchPackageNames` (more expressive) |
| Security PRs bypass cooldown | ✅ Yes | ✅ Yes |
| Vulnerability sources | GitHub Security Advisories | GitHub Security Advisories + OSV (`osvVulnerabilityAlerts`) |
| Visibility of held updates | None — delayed PRs simply don't appear | Dependency Dashboard issue lists pending updates |
| Grouped updates | `groups` config | `packageRules` grouping / built-in presets |
| Hosting | GitHub-native, zero setup | Hosted GitHub App (Mend) or self-hosted |
| Configuration review | `dependabot.yml` in-repo | `renovate.json` in-repo |

**When to choose which:**

- **Dependabot** is the lower-friction default for repositories whose ecosystems all have
  either a native package-manager age gate (npm, pnpm, Yarn, Bun, uv, Cargo via
  `cargo-cooldown`) or acceptable Dependabot cooldown coverage. It is GitHub-native and
  requires no third-party app authorization.
- **Renovate** is the better choice when the repository depends on Maven, Gradle, Go,
  Composer, Bundler, NuGet, Helm, or Terraform and you want a PR-level age gate that
  actually applies — or when you want the Dependency Dashboard's visibility into what is
  currently being held back.
- Running **both** is possible (e.g. Dependabot for `github-actions`, Renovate for
  application dependencies) but configure disjoint ecosystem coverage so they don't open
  duplicate PRs.

## Limitations

- Like Dependabot's cooldown, `minimumReleaseAge` gates the *update PR*, not the resolver.
  A developer running `go get`, `bundle update`, or `mvn versions:use-latest-releases`
  locally bypasses it entirely. Where a native resolver-level gate exists (npm, pnpm, Yarn,
  Bun, uv, cargo-cooldown), treat it as an **alternative**, not a layer to stack underneath
  Renovate: the resolver-level gate has no security-update exception, so running both blocks
  automated security updates. Pick one per ecosystem — see
  [Cooldown: resolver-level vs Dependabot](dependabot.md#cooldown-resolver-level-vs-dependabot--pick-one)
  (the same trade-off applies to Renovate's PR-level cooldown).
- New *transitive* packages introduced by an aged direct update are not individually
  age-checked — the same update-window caveat described in
  [Transitive Dependency Coverage](transitive.md).
- Renovate needs release timestamps from the registry to evaluate age. For registries that
  don't expose them (some private mirrors), the check is skipped silently — verify behaviour
  against your registry before relying on it.

## Reference

- [Renovate documentation](https://docs.renovatebot.com/)
- [`minimumReleaseAge`](https://docs.renovatebot.com/configuration-options/#minimumreleaseage)
- [`internalChecksFilter`](https://docs.renovatebot.com/configuration-options/#internalchecksfilter)
- [`packageRules`](https://docs.renovatebot.com/configuration-options/#packagerules)
- [Renovate vulnerability alerts](https://docs.renovatebot.com/configuration-options/#vulnerabilityalerts)
