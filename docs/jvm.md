<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# JVM Ecosystem (Java, Kotlin, Scala)

**Build tools covered:** Maven, Gradle (Groovy DSL and Kotlin DSL)

Java and Kotlin share the same artefact ecosystem — Maven Central (`repo.maven.apache.org`) is the canonical registry, and the same `groupId:artifactId:version` coordinates are consumed by Maven, Gradle, sbt, Leiningen, and Mill. Hardening recommendations therefore apply equally regardless of language: a Kotlin/Android project using Gradle Kotlin DSL has the same supply-chain surface as a Java service using Maven.

Two facts make the JVM ecosystem distinctive:

1. **Build scripts execute arbitrary code.** Maven plugins and Gradle build scripts run JVM code on the build host. This is strictly worse than npm `postinstall` — a malicious plugin or build script has full access to the developer's machine and CI runner. Plugin and build-script versions must be pinned and reviewed with the same rigour as runtime dependencies.
2. **Neither Maven nor Gradle has native minimum-release-age support.** Cooldown must be enforced via Dependabot (which supports both `maven` and `gradle` ecosystems) or Renovate.

## Maven

**Configuration files:** `pom.xml`, `~/.m2/settings.xml`, `.mvn/maven.config`, `.mvn/extensions.xml`

### No native lockfile

Maven has no built-in lockfile equivalent to `package-lock.json` or `Cargo.lock`. The `pom.xml` declares dependencies; transitive resolution happens fresh on each build unless every version (including transitives) is explicitly managed.

Effective controls:

- **Pin every direct dependency exactly** in `<dependencies>`.
- **Pin every transitive dependency** in `<dependencyManagement>` — this forces Maven's resolver to a specific version regardless of what transitive ranges request.
- **Pin every plugin** in `<build><pluginManagement>` and never omit `<version>` on a plugin declaration.
- Use the **Maven Enforcer Plugin** rules to fail the build on any unpinned or ranged dependency.
- Optionally adopt a third-party lockfile plugin such as [`io.github.chains-project:maven-lockfile`](https://github.com/chains-project/maven-lockfile) if reproducibility-by-hash is required.

### Version Pinning

Maven accepts both exact versions and Ivy-style version ranges. Ranges are rare in practice but must be banned explicitly because the resolver will silently pick the highest matching release on every build.

```xml
<!-- Correct — exact version -->
<dependency>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-starter-web</artifactId>
  <version>3.2.1</version>
</dependency>
```

```xml
<!-- Incorrect — do not use -->
<version>[3.2,)</version>        <!-- open range -->
<version>[3.2,4.0)</version>     <!-- bounded range -->
<version>LATEST</version>        <!-- removed in Maven 3.5; still parsed by some plugins -->
<version>RELEASE</version>       <!-- same -->
<version>3.2-SNAPSHOT</version>  <!-- mutable; resolves to whatever the last upload was -->
```

| Syntax | Meaning |
|--------|---------|
| `3.2.1` | Soft requirement — exact unless overridden by `<dependencyManagement>` or transitive resolution |
| `[3.2.1]` | Hard requirement — exact, build fails if anything else is forced |
| `[3.2,4.0)` | Bounded range — resolver picks highest matching |
| `[3.2,)` | Open range — resolver picks highest available |
| `1.0-SNAPSHOT` | Mutable snapshot — re-downloaded on every build by default |

Always use the bare exact form (`3.2.1`) combined with `<dependencyManagement>` for transitives. Hard requirements (`[3.2.1]`) can cause conflicts in multi-module builds where transitive consumers disagree.

### Enforcing pinning with maven-enforcer-plugin

The Enforcer plugin is the closest thing Maven has to lockfile enforcement at the manifest level:

```xml
<plugin>
  <groupId>org.apache.maven.plugins</groupId>
  <artifactId>maven-enforcer-plugin</artifactId>
  <version>3.5.0</version>
  <executions>
    <execution>
      <id>enforce</id>
      <goals><goal>enforce</goal></goals>
      <configuration>
        <rules>
          <banDynamicVersions/>
          <requirePluginVersions>
            <banLatest>true</banLatest>
            <banRelease>true</banRelease>
            <banSnapshots>true</banSnapshots>
          </requirePluginVersions>
          <requireReleaseDeps>
            <message>No SNAPSHOT dependencies allowed</message>
          </requireReleaseDeps>
          <dependencyConvergence/>
        </rules>
      </configuration>
    </execution>
  </executions>
</plugin>
```

- `banDynamicVersions` — fails the build on any ranged or `LATEST`/`RELEASE` version.
- `requirePluginVersions` — fails the build if any plugin is used without a pinned version.
- `requireReleaseDeps` — fails the build on `SNAPSHOT` dependencies (useful for release branches).
- `dependencyConvergence` — fails the build when multiple transitives disagree on a version, forcing an explicit `<dependencyManagement>` entry.

### Checksum verification

Maven verifies SHA-1 checksums against `.sha1` files alongside artefacts in the repository. By default it only **warns** on mismatch. Switch the policy to `fail`:

```xml
<!-- ~/.m2/settings.xml or repository definition in pom.xml -->
<repository>
  <id>central</id>
  <url>https://repo.maven.apache.org/maven2</url>
  <releases>
    <enabled>true</enabled>
    <checksumPolicy>fail</checksumPolicy>
  </releases>
  <snapshots>
    <enabled>false</enabled>
  </snapshots>
</repository>
```

Or pass `--strict-checksums` (`-C`) on the command line. Note: Maven Central only publishes SHA-1 checksums by default; modern Maven Central artefacts also include `.sha256` and `.sha512` but plugin-level verification is patchy. For strong artefact verification, prefer Gradle's verification-metadata feature or use Sigstore-signed artefacts where available.

### Snapshot dependencies

`SNAPSHOT` versions are mutable — `1.0-SNAPSHOT` can be re-uploaded by the publisher at any time, and Maven re-downloads it (by default once per day) without changing the version string. **Never depend on a `SNAPSHOT` for production builds.** Use `<requireReleaseDeps>` in the Enforcer plugin to fail the build if any snapshot creeps in.

If you publish snapshots internally, isolate them to a separate repository ID so they cannot mask a Central artefact.

### Repository control

Restrict Maven to known repositories. Avoid declaring arbitrary `<repository>` entries in `pom.xml`. Configure a mirror in `~/.m2/settings.xml` to route all resolution through a single, audited proxy (e.g. internal Nexus, Artifactory, or a Maven Central mirror):

```xml
<settings>
  <mirrors>
    <mirror>
      <id>internal-mirror</id>
      <mirrorOf>*</mirrorOf>
      <url>https://nexus.example.com/repository/maven-public/</url>
    </mirror>
  </mirrors>
</settings>
```

`<mirrorOf>*</mirrorOf>` forces every artefact request through the mirror regardless of what individual POMs declare. This is the strongest control against [dependency confusion / namespace squatting](https://medium.com/@alex.birsan/dependency-confusion-4a5d60fec610) for internal coordinates.

### Build script (plugin) execution

Maven plugins run JVM code with the privileges of the build process. Treat plugin upgrades with the same scrutiny as runtime dependencies:

- Pin every plugin version in `<pluginManagement>`.
- Enforce with `requirePluginVersions`.
- Avoid third-party plugins from low-reputation groups; prefer plugins published under `org.apache.maven.plugins`, `org.codehaus.mojo`, `org.jetbrains.kotlin`, or organisations you trust.
- Plugins loaded via `.mvn/extensions.xml` are particularly sensitive — they run before any POM is parsed. Audit this file specifically.

### Security scanning

- **OWASP Dependency-Check** — `org.owasp:dependency-check-maven`. Scans against the NVD and GitHub Advisory Database.
- **CycloneDX SBOM** — `org.cyclonedx:cyclonedx-maven-plugin`. Generates an SBOM that downstream scanners can consume.
- **Sonatype OSS Index** — `org.sonatype.ossindex.maven:ossindex-maven-plugin`. Fails the build on known vulnerabilities.

Pick one SCA tool and run it in CI on every build.

```xml
<plugin>
  <groupId>org.owasp</groupId>
  <artifactId>dependency-check-maven</artifactId>
  <version>10.0.4</version>
  <configuration>
    <failBuildOnCVSS>7</failBuildOnCVSS>
    <suppressionFile>dependency-check-suppressions.xml</suppressionFile>
  </configuration>
  <executions>
    <execution>
      <goals><goal>check</goal></goals>
    </execution>
  </executions>
</plugin>
```

### CI Recommended Configuration

```bash
# Strict checksums, batch mode (no interactive prompts), fail fast
mvn --batch-mode --strict-checksums --fail-fast \
    -DskipTests=false \
    verify

# Run enforcer rules explicitly if not bound to a phase
mvn --batch-mode enforcer:enforce

# SCA
mvn --batch-mode org.owasp:dependency-check-maven:check
```

Pass `-Dmaven.wagon.http.retryHandler.class=standard` and `-Dmaven.wagon.http.retryHandler.count=3` to make transient network failures retry rather than mask a registry-level issue.

## Gradle

**Configuration files:** `build.gradle` / `build.gradle.kts`, `settings.gradle` / `settings.gradle.kts`, `gradle.properties`, `gradle/wrapper/gradle-wrapper.properties`, `gradle.lockfile` (per configuration), `gradle/verification-metadata.xml`

Gradle has stronger built-in supply-chain controls than Maven:

- Native **dependency locking** produces a `gradle.lockfile` per configuration.
- Native **dependency verification** records SHA-256 / SHA-512 hashes and (optionally) PGP signatures of every resolved artefact in `gradle/verification-metadata.xml` and fails the build on mismatch.
- The **Gradle Wrapper** (`gradlew`) lets you pin the Gradle version itself, with a SHA-256 checksum.

Use all three.

### Gradle Wrapper version pinning

`gradle/wrapper/gradle-wrapper.properties` pins the Gradle version. Always commit it and include the SHA-256 of the distribution:

```properties
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.10.2-bin.zip
distributionSha256Sum=31c55713e40233a8303827ceb42ca48a47267a0ad4bab9177123121e71524c26
networkTimeout=10000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
```

Regenerate after a Gradle upgrade with `./gradlew wrapper --gradle-version 8.10.2 --distribution-type bin`. CI must invoke `./gradlew`, never a system-wide `gradle` binary — the wrapper is the only thing pinning the Gradle version and its scripts.

### Version Pinning

Gradle accepts dynamic versions (`1.+`, `latest.release`, `[1.0,2.0)`). All of these must be banned:

```kotlin
// build.gradle.kts — correct
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web:3.2.1")
    implementation("com.fasterxml.jackson.core:jackson-databind:2.17.2")
}
```

```kotlin
// build.gradle.kts — incorrect
implementation("org.springframework.boot:spring-boot-starter-web:3.+")          // dynamic
implementation("org.springframework.boot:spring-boot-starter-web:latest.release")
implementation("org.springframework.boot:spring-boot-starter-web") {            // unspecified
    version { strictly("[3.2,4.0)") }
}
```

| Syntax | Meaning |
|--------|---------|
| `"group:name:1.2.3"` | Exact |
| `"group:name:1.+"` | Dynamic — highest 1.x |
| `"group:name:latest.release"` | Dynamic — highest non-snapshot |
| `"group:name:[1.2,2.0)"` | Range |
| `"group:name:1.2.3-SNAPSHOT"` | Mutable snapshot |

Use [version catalogs](https://docs.gradle.org/current/userguide/platforms.html) (`gradle/libs.versions.toml`) so versions are declared once and referenced symbolically — this makes pinning auditable and makes Dependabot's PRs much easier to read.

### Failing the build on dynamic versions

Configure each resolution strategy to reject dynamic or changing versions:

```kotlin
// settings.gradle.kts or root build.gradle.kts
allprojects {
    configurations.all {
        resolutionStrategy {
            failOnDynamicVersions()
            failOnChangingVersions()
            failOnNonReproducibleResolution()
        }
    }
}
```

`failOnNonReproducibleResolution()` combines the previous two and additionally rejects any resolution that depends on a mutable repository state.

### Dependency Locking

Enable lockfile generation for every configuration:

```kotlin
// settings.gradle.kts
dependencyResolutionManagement {
    // ...
}

// root build.gradle.kts
allprojects {
    dependencyLocking {
        lockAllConfigurations()
        lockMode.set(LockMode.STRICT)
    }
}
```

Generate or update the lockfile:

```bash
./gradlew dependencies --write-locks
```

This writes one `gradle.lockfile` per project containing every resolved coordinate. Commit these files. CI runs `./gradlew build` normally — `LockMode.STRICT` causes the build to fail if any resolution would diverge from the lockfile.

Pass `--update-locks org.foo:*` to refresh a subset when intentionally updating.

### Dependency Verification

Generate the verification metadata for every artefact (jars, POMs, plugin marker artefacts):

```bash
./gradlew --write-verification-metadata sha256,pgp \
          --export-keys \
          help
```

This creates `gradle/verification-metadata.xml`:

```xml
<?xml version="1.1" encoding="UTF-8"?>
<verification-metadata>
  <configuration>
    <verify-metadata>true</verify-metadata>
    <verify-signatures>true</verify-signatures>
  </configuration>
  <trusted-keys>
    <trusted-key id="..."/>
  </trusted-keys>
  <components>
    <component group="org.springframework.boot" name="spring-boot-starter-web" version="3.2.1">
      <artifact name="spring-boot-starter-web-3.2.1.jar">
        <sha256 value="..." origin="Generated by Gradle"/>
        <pgp value="..."/>
      </artifact>
    </component>
    ...
  </components>
</verification-metadata>
```

Commit this file and the `gradle/verification-keyring.keys` it generates. Every subsequent build verifies SHA-256 and (where present) PGP signatures against this manifest and **fails** on any mismatch. This is the strongest artefact-integrity control available in any JVM build tool.

Run with `--refresh-keys` after rotating signing keys. Run with `--write-verification-metadata sha256,pgp` again when adding or upgrading any dependency.

### Repository control

Restrict the repositories Gradle will use to a small, known set. In `settings.gradle.kts`:

```kotlin
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        mavenCentral()
        gradlePluginPortal()
    }
}
```

`FAIL_ON_PROJECT_REPOS` prevents subprojects from quietly adding additional repositories. **Do not use `mavenLocal()`** — it allows artefacts from the developer's `~/.m2/repository` to silently substitute for Central. **Do not use `jcenter()`** — it has been read-only since 2022 and unmaintained since 2024.

For internal artefacts, pair with a `repositories.exclusiveContent` block so that internal coordinates can only be served by your internal repository:

```kotlin
repositories {
    exclusiveContent {
        forRepository {
            maven("https://nexus.example.com/repository/internal/")
        }
        filter {
            includeGroup("com.example.internal")
        }
    }
    mavenCentral()
}
```

This is the canonical defence against dependency confusion attacks: `com.example.internal:*` can never be resolved from Maven Central, even if a malicious package with the same coordinates is published there.

### Build script execution

Gradle build scripts are Groovy or Kotlin code executed at evaluation time. A compromised plugin runs on every build with full filesystem and network access.

- Pin every plugin version via the `plugins { id("...") version "x.y.z" }` block (or via version catalog).
- Never use `plugins { id("...") version "+" }` or dynamic plugin versions.
- Apply [`org.gradle.api.publish.PublishingExtension`](https://docs.gradle.org/current/userguide/dependency_verification.html) verification to plugins too — dependency verification covers plugin marker artefacts.
- Run untrusted Gradle projects in a sandbox; `--no-daemon` is **not** a security boundary.

### Security scanning

- **OWASP Dependency-Check** — `org.owasp.dependencycheck` Gradle plugin.
- **CycloneDX SBOM** — `org.cyclonedx.bom` Gradle plugin.
- **Snyk / Sonatype OSS Index** — both publish official Gradle plugins.

Pick one SCA tool and bind it to a CI task:

```kotlin
plugins {
    id("org.owasp.dependencycheck") version "10.0.4"
}

dependencyCheck {
    failBuildOnCVSS = 7.0f
    suppressionFile = "dependency-check-suppressions.xml"
}
```

### CI Recommended Configuration

```bash
# Use the wrapper — never a system gradle
./gradlew \
    --no-daemon \
    --console=plain \
    --stacktrace \
    build

# Dependency verification + lockfile enforcement happen automatically
# during normal task execution (no separate flag required)

# SCA
./gradlew dependencyCheckAnalyze
```

`--no-daemon` in CI ensures every build starts from a clean JVM, avoiding any cross-build state.

`--write-locks` and `--write-verification-metadata` must **never** run in CI. They are local-only operations to be performed by a human when intentionally updating dependencies.

## sbt (Scala) — brief note

If a Scala project is using sbt, the equivalent controls are:

- Pin versions exactly in `build.sbt` (`libraryDependencies += "org" %% "name" % "1.2.3"`).
- Enable [coursier](https://get-coursier.io/) and use `coursier resolve` to produce a lockfile-equivalent manifest, or use [`sbt-lock`](https://github.com/tkawachi/sbt-lock).
- Pin the sbt version in `project/build.properties`.
- Pin every sbt plugin in `project/plugins.sbt`.

The Maven Central registry and `repo.maven.apache.org:443` egress are identical to Java/Kotlin projects.

## Dependabot

Dependabot supports both `maven` and `gradle` ecosystems. Both support `cooldown`:

```yaml
version: 2
updates:
  - package-ecosystem: "maven"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30
      semver-minor-days: 7
      semver-patch-days: 3

  - package-ecosystem: "gradle"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30
      semver-minor-days: 7
      semver-patch-days: 3
```

The `gradle` ecosystem covers `build.gradle`, `build.gradle.kts`, and version catalogs (`gradle/libs.versions.toml`). It does **not** update the Gradle Wrapper version itself — for that, use the separate `gradle-wrapper` ecosystem:

```yaml
  - package-ecosystem: "gradle-wrapper"
    directory: "/"
    schedule:
      interval: "weekly"
```

Security update PRs from Dependabot bypass the cooldown automatically and should be reviewed and merged promptly.

## Harden-Runner

Every GitHub Actions workflow that runs `mvn` or `./gradlew` must include `step-security/harden-runner` as its first step:

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
      jcenter.bintray.com:443
```

Endpoint notes:

- `repo.maven.apache.org` and `repo1.maven.org` are both Maven Central — different DNS entries used by different clients and CDNs.
- `plugins.gradle.org` serves the Gradle Plugin Portal.
- `services.gradle.org` and `downloads.gradle.org` serve the Gradle distribution zip referenced by `gradle-wrapper.properties`.
- For private registries (Nexus, Artifactory, GitHub Packages Maven), add the hostname.
- For Kotlin projects, also include `dl.google.com:443` if pulling Android-related artefacts.
- For OWASP Dependency-Check NVD downloads, add `nvd.nist.gov:443` and `services.nvd.nist.gov:443`.

Start in `audit` mode for new workflows and switch to `block` after reviewing audit logs to build a confirmed allowlist.
