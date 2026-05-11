<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Agent Instructions: JVM (Java / Kotlin / Scala) Dependency Management

This file contains mandatory guidelines for managing dependencies in this JVM project (Maven or Gradle). Follow these rules whenever adding, updating, or removing dependencies or plugins, or modifying CI configuration.

## Dependency Rules — All JVM projects

**Always pin exact versions** for both direct dependencies and plugins. Never use dynamic versions, ranges, `LATEST`, `RELEASE`, `+`, or `SNAPSHOT` in production manifests.

**Never add a dependency or plugin version published within the last 7 days.** Check the publication date on [Maven Central](https://central.sonatype.com/) before adding any new coordinate. If a version was published less than 7 days ago, defer the addition until the cooldown has elapsed.

**Treat plugin upgrades with the same scrutiny as runtime dependencies.** Maven plugins and Gradle build scripts execute arbitrary JVM code on the build host. A compromised plugin is strictly more dangerous than a compromised runtime library.

**Never depend on `SNAPSHOT` versions** in production code. Snapshots are mutable and re-downloaded silently.

## Maven Projects

### Dependency Rules

```xml
<!-- Correct — exact version, managed centrally -->
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
      <version>3.2.1</version>
    </dependency>
  </dependencies>
</dependencyManagement>
```

```xml
<!-- Incorrect — do not use -->
<version>[3.2,)</version>        <!-- range -->
<version>LATEST</version>        <!-- dynamic -->
<version>3.2-SNAPSHOT</version>  <!-- mutable -->
```

Every plugin must be pinned in `<build><pluginManagement>` with an explicit `<version>`.

### Configuration to Verify

**maven-enforcer-plugin** must be configured with these rules:

- `banDynamicVersions` — fails on any range or `LATEST`/`RELEASE`.
- `requirePluginVersions` (with `banLatest=true`, `banRelease=true`, `banSnapshots=true`).
- `requireReleaseDeps` — fails on `SNAPSHOT` dependencies.
- `dependencyConvergence` — fails when transitives disagree on a version.

If `pom.xml` does not include the enforcer plugin, add it before making any other dependency changes.

**Checksum policy** must be `fail` (not `warn`) — either in repository definitions or via `--strict-checksums` on every Maven invocation.

**SCA tool** — at least one of OWASP Dependency-Check (`org.owasp:dependency-check-maven`), CycloneDX (`org.cyclonedx:cyclonedx-maven-plugin`), or Sonatype OSS Index must be configured and run in CI.

### CI Commands (Maven)

```bash
mvn --batch-mode --strict-checksums --fail-fast verify
mvn --batch-mode enforcer:enforce
mvn --batch-mode org.owasp:dependency-check-maven:check
```

## Gradle Projects

### Dependency Rules

```kotlin
// Correct — exact version, ideally via version catalog
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web:3.2.1")
}
```

```kotlin
// Incorrect — do not use
implementation("group:name:1.+")
implementation("group:name:latest.release")
implementation("group:name:[1.2,2.0)")
implementation("group:name:1.2.3-SNAPSHOT")
```

Prefer `gradle/libs.versions.toml` (version catalog) so every version is declared in one auditable place.

### Configuration to Verify

**Gradle Wrapper** must be committed (`gradle/wrapper/gradle-wrapper.properties`, `gradle/wrapper/gradle-wrapper.jar`, `gradlew`, `gradlew.bat`) and must include `distributionSha256Sum`. CI must invoke `./gradlew`, never a system-wide `gradle`.

**Dynamic version rejection** must be configured at the root of the build:

```kotlin
allprojects {
    configurations.all {
        resolutionStrategy {
            failOnNonReproducibleResolution()
        }
    }
}
```

**Dependency Locking** must be enabled with strict mode:

```kotlin
allprojects {
    dependencyLocking {
        lockAllConfigurations()
        lockMode.set(LockMode.STRICT)
    }
}
```

`gradle.lockfile` files must be committed (one per project module).

**Dependency Verification** must be enabled — `gradle/verification-metadata.xml` must exist with `<verify-metadata>true</verify-metadata>` and (where feasible) `<verify-signatures>true</verify-signatures>`. SHA-256 entries for every artefact are mandatory; PGP entries are strongly preferred where publishers sign.

**Repository control** must be in `settings.gradle.kts`:

```kotlin
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        mavenCentral()
        gradlePluginPortal()
    }
}
```

`mavenLocal()` and `jcenter()` must not appear anywhere in the build. Internal coordinates must be served only by the internal repository via `exclusiveContent { filter { includeGroup("...") } }`.

**SCA tool** — at least one of OWASP Dependency-Check (`org.owasp.dependencycheck`), CycloneDX (`org.cyclonedx.bom`), or Snyk must be configured and run in CI.

### CI Commands (Gradle)

```bash
./gradlew --no-daemon --console=plain --stacktrace build
./gradlew --no-daemon dependencyCheckAnalyze
```

**Never run `--write-locks` or `--write-verification-metadata` in CI.** Both are local-only operations performed by a human when intentionally updating dependencies.

## CI Configuration — All JVM projects

### Dependabot

`.github/dependabot.yml` must include cooldowns for `maven` and/or `gradle` and `gradle-wrapper` ecosystems. If the file does not exist or lacks the cooldown blocks, add them:

```yaml
version: 2
updates:
  - package-ecosystem: "maven"      # or "gradle"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30
      semver-minor-days: 7
      semver-patch-days: 3

  - package-ecosystem: "gradle-wrapper"   # Gradle projects only
    directory: "/"
    schedule:
      interval: "weekly"
```

Security update PRs from Dependabot bypass the cooldown automatically and should be reviewed and merged promptly.

### Harden-Runner

Every GitHub Actions workflow that runs `mvn` or `./gradlew` must include `step-security/harden-runner` as its first step. Start in `audit` mode for new workflows, then tighten to `block` once the egress policy is stable:

```yaml
- uses: step-security/harden-runner@bb774aa972c2a89ff34781233d275075cbddf542 # v2
  with:
    egress-policy: block
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      repo.maven.apache.org:443
      repo1.maven.org:443
      plugins.gradle.org:443
      services.gradle.org:443
      downloads.gradle.org:443
```

Add `nvd.nist.gov:443` and `services.nvd.nist.gov:443` if OWASP Dependency-Check downloads NVD data in CI. Add `dl.google.com:443` for Android/Kotlin projects pulling Google-hosted artefacts. Add private registry hostnames (Nexus, Artifactory, GitHub Packages) if used.

## What Requires Human Review

The following changes must not be made autonomously and require explicit human approval before proceeding:

- Adding a new dependency or plugin not previously present in `pom.xml`, `build.gradle(.kts)`, or `libs.versions.toml`
- Upgrading a major version
- Changing exact pins to ranges or dynamic versions
- Adding any `SNAPSHOT` dependency
- Adding a new repository (Maven `<repository>` entry, Gradle `repositories { ... }` entry, mirror, or `<mirrorOf>` change)
- Adding or modifying entries in `.mvn/extensions.xml` (these load before any POM is parsed — extremely sensitive)
- Modifying `.github/dependabot.yml` cooldown values downward
- Removing or modifying Harden-Runner from a workflow
- Removing maven-enforcer-plugin rules or weakening them
- Removing Gradle `dependencyLocking`, `failOnNonReproducibleResolution`, or dependency verification
- Deleting `gradle.lockfile` or `gradle/verification-metadata.xml` (regenerate locally and commit, never delete)
- Adding plugins that fetch or execute remote code at build time
