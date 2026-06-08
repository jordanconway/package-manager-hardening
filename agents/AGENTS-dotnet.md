<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Agent Instructions: .NET / NuGet Dependency Management

This file contains mandatory guidelines for managing dependencies in this .NET project. Follow
these rules whenever adding, updating, or removing NuGet packages, or modifying CI
configuration.

## Hash Verification: Never Fabricate

**AI agents must never invent, guess, autocomplete, or extrapolate a `packages.lock.json`
content hash, NuGet package SHA512, or commit SHA for a git-sourced dependency.** A fabricated
hash either fails verification or silently pins to the wrong artifact.

All `packages.lock.json` content is produced by `dotnet restore` — run it locally and commit
the result. Do not hand-edit `contentHash` or `resolved` fields in the lockfile.

To verify a published NuGet package's hash before pinning:

**Preferred:** if the `harden-packages` skill is available, use its helper:

```bash
python {SKILL_DIR}/verify_hash.py git-ref https://github.com/NuGet/NuGet.Client.git <tag>
```

**Fallback:** check the package page on `https://www.nuget.org/packages/<pkg>/<version>` —
the SHA512 hash is listed under "Package Details". Or query the NuGet API directly:

```bash
# Get package info including content hash
curl -fsSL "https://api.nuget.org/v3/registration5-semver2/<pkg>/index.json" | \
  jq '.items[].items[] | select(.catalogEntry.version == "<version>") | .catalogEntry'
```

If you cannot verify a hash with any of the above, **stop and ask the user**. Do not insert
a placeholder or a "likely correct" value.

## Dependency Rules

**Always pin exact versions** in `.csproj` files and `Directory.Packages.props`. Prefer
bracket notation for true exact pins:

```xml
<!-- Correct — bracket notation is truly exact -->
<PackageReference Include="Newtonsoft.Json" Version="[13.0.3]" />

<!-- Acceptable — bare version is a minimum constraint, but effectively exact with lockfile -->
<PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
```

```xml
<!-- Incorrect — do not use floating, wildcard, or range syntax -->
<PackageReference Include="Newtonsoft.Json" Version="*" />
<PackageReference Include="Newtonsoft.Json" Version="*-*" />
<PackageReference Include="Newtonsoft.Json" Version="[13.0.0, 14.0.0)" />
<PackageReference Include="Newtonsoft.Json" Version="[13.0.0,)" />
```

**Never add a package version published within the last 7 days.** Check the publication date
on `https://www.nuget.org/packages/<pkg>/<version>` before adding any new dependency. If the
version was published less than 7 days ago, defer the addition until the cooldown has elapsed.

**Always commit `packages.lock.json`** to version control. For solutions with multiple
projects, commit all generated `packages.lock.json` files. They ensure reproducible installs
across development, CI, and production environments.

**Enable `RestorePackagesWithLockFile`** in `Directory.Build.props` or each `.csproj`. Without
this opt-in, no lockfile is generated and `--locked-mode` has nothing to enforce.

**Never run `dotnet restore` without `--locked-mode` in CI.** Bare `dotnet restore` will
re-resolve and can silently update `packages.lock.json` if any version constraint is satisfied
by a newly published package.

## Configuration to Verify

**`packages.lock.json`** must be present and committed. If missing, add
`<RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>` to `Directory.Build.props`,
run `dotnet restore` locally, and commit the result.

**`nuget.config`** should be present with `<packageSourceMapping>` configured to restrict
which registry each package name may come from. Without source mapping, a package on nuget.org
can shadow a private registry package of the same name (dependency confusion).

**`global.json`** should pin the .NET SDK version with `"rollForward": "disable"`.

**Vulnerability scanning** must run in CI:

```bash
dotnet list package --vulnerable --include-transitive
```

## CI Commands

```bash
# Enforce lockfile — fail if packages.lock.json would change
dotnet restore --locked-mode

# Build
dotnet build --no-restore --configuration Release

# Test
dotnet test --no-restore --configuration Release

# Check for known vulnerabilities
dotnet list package --vulnerable --include-transitive
```

**`--locked-mode`** causes `dotnet restore` to fail if the lockfile would need to change. This
prevents CI from silently re-resolving to a different set of packages than what was reviewed.

## CI Configuration

### Dependabot

`.github/dependabot.yml` must include a cooldown for the `nuget` ecosystem. If the file does
not exist or lacks a cooldown block, add it:

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

Security update PRs from Dependabot bypass the cooldown automatically and should be reviewed
and merged promptly.

### Harden-Runner

Every GitHub Actions workflow that runs `dotnet restore` or `dotnet build` must include
`step-security/harden-runner` as its first step. New workflows must not be added without it.

Start in `audit` mode for new workflows, then tighten to `block` once the egress policy
is stable:

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

Add `dotnetcli.azureedge.net:443` and `builds.dotnet.microsoft.com:443` if using
`actions/setup-dotnet`. Add your private feed hostname if using Azure Artifacts, GitHub
Packages, or Artifactory.

## What Requires Human Review

The following changes must not be made autonomously and require explicit human approval before
proceeding:

- Adding a new NuGet package not previously present in the project
- Upgrading a major version
- Changing exact version pins to range or floating constraints
- Modifying `.github/dependabot.yml` cooldown values downward
- Removing or modifying Harden-Runner from a workflow
- Removing `--locked-mode` from CI restore commands
- Adding packages with native code or post-install scripts (flag for security review)
- Changing `packageSourceMapping` in `nuget.config` (source changes affect which registry
  serves each package — review carefully for dependency confusion risk)
- Adding a new package source to `nuget.config`
