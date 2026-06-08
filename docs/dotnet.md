<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# .NET Ecosystem

## NuGet

**Configuration files:** `.csproj` / `.fsproj` / `.vbproj`, `packages.lock.json`, `nuget.config`,
`Directory.Packages.props`, `Directory.Build.props`

NuGet is the standard package manager for .NET (C#, F#, VB.NET). Dependencies are declared
in SDK-style project files (`.csproj`) as `<PackageReference>` elements, or centrally in
`Directory.Packages.props` for multi-project solutions.

### Lockfile

Unlike most package managers, NuGet does **not** generate a lockfile by default. You must
explicitly opt in by adding `<RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>`
to each project file, or once in a `Directory.Build.props` at the solution root so it applies
to all projects:

```xml
<!-- Directory.Build.props (applies to all projects in the solution) -->
<Project>
  <PropertyGroup>
    <RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>
  </PropertyGroup>
</Project>
```

After adding this, run `dotnet restore` once locally to generate `packages.lock.json` next to
each `.csproj`, then commit all generated lockfiles.

In CI, enforce the lockfile so builds cannot silently re-resolve to different versions:

```bash
# Fail if packages.lock.json would need to change
dotnet restore --locked-mode

# Build and test without re-running restore
dotnet build --no-restore
dotnet test --no-restore
```

`--locked-mode` is the equivalent of `npm ci`, `bundle install` with `BUNDLE_FROZEN=true`, or
`uv sync --frozen`. If it fails, the lockfile is out of sync — run `dotnet restore` locally,
commit the updated `packages.lock.json`, and retry.

### Version Pinning

NuGet version notation differs from most ecosystems. Without brackets, a bare version is a
*minimum* constraint, not an exact pin:

| Syntax | Meaning | Use? |
|--------|---------|------|
| `13.0.3` | Minimum — resolves ≥ 13.0.3 | ⚠️ Acceptable with lockfile |
| `[13.0.3]` | Exact — only this version | ✅ Preferred |
| `[13.0.3, 14.0.0)` | Range | ❌ Avoid |
| `[13.0.3,)` | Open minimum (range form) | ❌ Avoid |
| `*` | Floating (latest) | ❌ Never |
| `*-*` | Floating prerelease | ❌ Never |

Prefer bracket notation for true exact pinning. Without a lockfile, a bare `13.0.3` allows
any version ≥ 13.0.3 to be resolved at install time — a newly published `13.0.4` would be
silently adopted. With `packages.lock.json` and `--locked-mode`, even bare versions are
effectively pinned at CI time; the lockfile records the exact resolved version.

```xml
<!-- .csproj — bracket notation for true exact pinning -->
<PackageReference Include="Newtonsoft.Json" Version="[13.0.3]" />
<PackageReference Include="Serilog" Version="[4.2.0]" />

<!-- Acceptable alternative when paired with packages.lock.json -->
<PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
```

Never use floating (`*`) or range syntax in production project files.

### Central Package Management

For solutions with multiple projects, Central Package Management (CPM) consolidates all
version declarations into a single `Directory.Packages.props` at the solution root. This
eliminates version drift across projects — every project in the solution uses identical
versions.

```xml
<!-- Directory.Packages.props -->
<Project>
  <PropertyGroup>
    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>
    <RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>
  </PropertyGroup>
  <ItemGroup>
    <PackageVersion Include="Newtonsoft.Json" Version="[13.0.3]" />
    <PackageVersion Include="Serilog" Version="[4.2.0]" />
    <PackageVersion Include="Microsoft.Extensions.Logging" Version="[8.0.1]" />
  </ItemGroup>
</Project>
```

In each `.csproj`, reference packages without specifying a version — the version comes from
`Directory.Packages.props`:

```xml
<ItemGroup>
  <PackageReference Include="Newtonsoft.Json" />
  <PackageReference Include="Serilog" />
</ItemGroup>
```

CPM is strongly recommended for any solution with more than one project. Without it, the same
package can be pinned to different versions in different projects, and a compromised release
only needs to satisfy one project's loose constraint.

### Package Source Mapping

Package Source Mapping prevents dependency confusion attacks by explicitly declaring which
package registry each package name may come from. Without it, a package named
`MyCompany.Internal.Utils` on nuget.org could shadow a genuine private package of the same
name — a dependency confusion attack.

```xml
<!-- nuget.config -->
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
    <!-- Add private feed if applicable:
    <add key="private-feed" value="https://pkgs.example.com/nuget/v3/index.json" />
    -->
  </packageSources>
  <packageSourceMapping>
    <!-- All packages come from nuget.org unless explicitly overridden below -->
    <packageSource key="nuget.org">
      <package pattern="*" />
    </packageSource>
    <!-- If using a private registry, map internal packages explicitly:
    <packageSource key="private-feed">
      <package pattern="MyCompany.*" />
    </packageSource>
    -->
  </packageSourceMapping>
</configuration>
```

The `<clear />` inside `<packageSources>` removes any machine-level source configuration,
ensuring only the sources you declare here are used. This is especially important in CI.

### Security: Vulnerability Auditing

```bash
# Check all packages in the solution against the GitHub Advisory Database
dotnet list package --vulnerable

# Include transitive (indirect) dependencies
dotnet list package --vulnerable --include-transitive

# Also check for deprecated packages
dotnet list package --deprecated
```

Run `dotnet list package --vulnerable --include-transitive` on every CI build. The command
exits non-zero if any vulnerable package is found, making it suitable as a build gate.

### Security: Signed Packages and NuGet Trust

NuGet supports cryptographic package signing. Most packages on nuget.org are signed with
repository signatures. You can enforce signed packages in `nuget.config`:

```xml
<configuration>
  <trustedSigners>
    <repository name="nuget.org" serviceIndex="https://api.nuget.org/v3/index.json">
      <certificate fingerprint="0E5F38F57DC1BCC806D8494F4F90FBBA" hashAlgorithm="SHA256"
                   allowUntrustedRoot="false" />
    </repository>
  </trustedSigners>
  <config>
    <!-- Require signed packages — rejects unsigned or untrusted packages -->
    <add key="signatureValidationMode" value="require" />
  </config>
</configuration>
```

Note: `signatureValidationMode: require` blocks packages that are not signed, which may
affect some older or private packages. Start with `accept` mode and tighten after auditing
your dependency tree.

### CI Recommended Configuration

```bash
# Restore with lockfile enforcement — fail if packages.lock.json would change
dotnet restore --locked-mode

# Build (skip restore since we just ran it with --locked-mode)
dotnet build --no-restore --configuration Release

# Run tests
dotnet test --no-restore --configuration Release

# Check for known vulnerabilities (fail build if any found)
dotnet list package --vulnerable --include-transitive
```

For stricter environments, also add:

```bash
# Check for deprecated packages
dotnet list package --deprecated

# Enforce no packages from unrecognised sources (via nuget.config packageSourceMapping)
# This is configuration-driven, not a separate CLI step
```

### Gemfile-equivalent: global.json

Pin the .NET SDK version in `global.json` at the solution root. Without it, the SDK version
used depends on whatever is installed on the CI runner, which can change between runs:

```json
{
  "sdk": {
    "version": "8.0.404",
    "rollForward": "disable"
  }
}
```

`"rollForward": "disable"` prevents MSBuild from silently using a newer SDK version if the
pinned one is not installed. Use `"latestMinor"` if you want to allow SDK patch updates.

## Dependabot

Dependabot supports the `nuget` ecosystem. Configure cooldowns in `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "nuget"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30
      semver-minor-days: 7
      semver-patch-days: 3
```

If your solution has multiple `.csproj` files in subdirectories, Dependabot scans the whole
repo from `"/"` — you do not need a separate entry per project. For multi-repo solutions
with `Directory.Packages.props`, Dependabot updates the centrally-managed versions in that
file.

Security update PRs from Dependabot bypass the cooldown automatically and should be reviewed
and merged promptly.

## Harden-Runner

Every GitHub Actions workflow that runs `dotnet restore` or `dotnet build` must include
`step-security/harden-runner`:

```yaml
- uses: step-security/harden-runner@9af89fc71515a100421586dfdb3dc9c984fbf411 # v2.19.4
  with:
    egress-policy: block
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      api.nuget.org:443
      globalcdn.nuget.org:443
```

Additional endpoints to add as needed:

- `dotnet list package --vulnerable` calls the GitHub Advisory Database via `api.github.com`
  (already in the list above).
- Private package feeds (Azure Artifacts, GitHub Packages, Artifactory): add each feed's
  hostname explicitly.
- `actions/setup-dotnet` downloads SDK binaries from `dotnetcli.azureedge.net:443` and
  `builds.dotnet.microsoft.com:443` — add both if using the action.

Start in `audit` mode for new workflows and switch to `block` after reviewing audit logs to
build a confirmed allowlist.
