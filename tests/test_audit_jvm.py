# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Unit tests for audit_maven() and audit_gradle()."""

import audit
from conftest import make_workflow, write_file


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def test_detect_maven(tmp_path):
    (tmp_path / "pom.xml").write_text("<project/>")
    assert "maven" in audit.detect_ecosystems(str(tmp_path))


def test_detect_gradle_groovy(tmp_path):
    (tmp_path / "build.gradle").write_text("")
    assert "gradle" in audit.detect_ecosystems(str(tmp_path))


def test_detect_gradle_kotlin(tmp_path):
    (tmp_path / "build.gradle.kts").write_text("")
    assert "gradle" in audit.detect_ecosystems(str(tmp_path))


def test_detect_gradle_settings_only(tmp_path):
    (tmp_path / "settings.gradle.kts").write_text("")
    assert "gradle" in audit.detect_ecosystems(str(tmp_path))


# ---------------------------------------------------------------------------
# Maven — exact pins
# ---------------------------------------------------------------------------

POM_EXACT = """\
<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
      <version>3.2.1</version>
    </dependency>
  </dependencies>
</project>
"""


def test_maven_exact_pins_pass(tmp_path):
    (tmp_path / "pom.xml").write_text(POM_EXACT)
    result = audit.audit_maven(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"


def test_maven_range_detected(tmp_path):
    pom = POM_EXACT.replace("<version>3.2.1</version>", "<version>[3.2,4.0)</version>")
    (tmp_path / "pom.xml").write_text(pom)
    result = audit.audit_maven(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"
    assert "[3.2,4.0)" in result["exact_pins"]["loose"]


def test_maven_latest_detected(tmp_path):
    pom = POM_EXACT.replace("<version>3.2.1</version>", "<version>LATEST</version>")
    (tmp_path / "pom.xml").write_text(pom)
    result = audit.audit_maven(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"
    assert "LATEST" in result["exact_pins"]["loose"]


def test_maven_snapshot_detected(tmp_path):
    pom = POM_EXACT.replace("<version>3.2.1</version>", "<version>3.2-SNAPSHOT</version>")
    (tmp_path / "pom.xml").write_text(pom)
    result = audit.audit_maven(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"


def test_maven_property_placeholder_not_flagged(tmp_path):
    pom = POM_EXACT.replace("<version>3.2.1</version>", "<version>${spring.version}</version>")
    (tmp_path / "pom.xml").write_text(pom)
    result = audit.audit_maven(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"


# ---------------------------------------------------------------------------
# Maven — enforcer plugin
# ---------------------------------------------------------------------------

POM_ENFORCER = """\
<project>
  <build>
    <plugins>
      <plugin>
        <artifactId>maven-enforcer-plugin</artifactId>
        <version>3.5.0</version>
        <configuration>
          <rules>
            <banDynamicVersions/>
            <requirePluginVersions/>
            <requireReleaseDeps/>
            <dependencyConvergence/>
          </rules>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
"""


def test_maven_enforcer_full_rules_pass(tmp_path):
    (tmp_path / "pom.xml").write_text(POM_ENFORCER)
    result = audit.audit_maven(str(tmp_path))
    assert result["enforcer_plugin"]["status"] == "pass"
    assert result["enforcer_plugin"]["ban_dynamic_versions"] is True
    assert result["enforcer_plugin"]["dependency_convergence"] is True


def test_maven_no_enforcer_fails(tmp_path):
    (tmp_path / "pom.xml").write_text(POM_EXACT)
    result = audit.audit_maven(str(tmp_path))
    assert result["enforcer_plugin"]["status"] == "fail"
    assert result["enforcer_plugin"]["present"] is False


# ---------------------------------------------------------------------------
# Maven — strict checksums
# ---------------------------------------------------------------------------

def test_maven_strict_checksums_in_pom(tmp_path):
    pom = """<project><repositories><repository><id>x</id>
    <releases><checksumPolicy>fail</checksumPolicy></releases>
    </repository></repositories></project>"""
    (tmp_path / "pom.xml").write_text(pom)
    result = audit.audit_maven(str(tmp_path))
    assert result["strict_checksums"]["status"] == "pass"
    assert result["strict_checksums"]["in_pom"] is True


def test_maven_strict_checksums_in_ci(tmp_path):
    (tmp_path / "pom.xml").write_text(POM_EXACT)
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: mvn --strict-checksums verify\n")
    result = audit.audit_maven(str(tmp_path))
    assert result["strict_checksums"]["in_ci"] is True
    assert result["strict_checksums"]["status"] == "pass"


def test_maven_no_strict_checksums_fails(tmp_path):
    (tmp_path / "pom.xml").write_text(POM_EXACT)
    result = audit.audit_maven(str(tmp_path))
    assert result["strict_checksums"]["status"] == "fail"


# ---------------------------------------------------------------------------
# Maven — SCA scanner
# ---------------------------------------------------------------------------

def test_maven_sca_dependency_check(tmp_path):
    pom = "<project><build><plugins><plugin>" \
          "<artifactId>dependency-check-maven</artifactId></plugin></plugins></build></project>"
    (tmp_path / "pom.xml").write_text(pom)
    result = audit.audit_maven(str(tmp_path))
    assert result["sca_scanner"]["status"] == "pass"
    assert result["sca_scanner"]["owasp_dependency_check"] is True


def test_maven_no_sca_scanner_fails(tmp_path):
    (tmp_path / "pom.xml").write_text(POM_EXACT)
    result = audit.audit_maven(str(tmp_path))
    assert result["sca_scanner"]["status"] == "fail"


# ---------------------------------------------------------------------------
# Gradle — exact pins
# ---------------------------------------------------------------------------

BUILD_KTS_EXACT = """\
plugins {
    kotlin("jvm") version "1.9.22"
}
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web:3.2.1")
}
"""


def test_gradle_exact_pins_pass(tmp_path):
    (tmp_path / "build.gradle.kts").write_text(BUILD_KTS_EXACT)
    result = audit.audit_gradle(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"


def test_gradle_dynamic_plus_detected(tmp_path):
    content = 'dependencies { implementation("g:n:1.+") }'
    (tmp_path / "build.gradle.kts").write_text(content)
    result = audit.audit_gradle(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"


def test_gradle_latest_release_detected(tmp_path):
    content = 'dependencies { implementation("g:n:latest.release") }'
    (tmp_path / "build.gradle.kts").write_text(content)
    result = audit.audit_gradle(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"


def test_gradle_range_detected(tmp_path):
    content = 'dependencies { implementation("g:n:[1.0,2.0)") }'
    (tmp_path / "build.gradle.kts").write_text(content)
    result = audit.audit_gradle(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"


def test_gradle_snapshot_detected(tmp_path):
    content = 'dependencies { implementation("g:n:1.0-SNAPSHOT") }'
    (tmp_path / "build.gradle.kts").write_text(content)
    result = audit.audit_gradle(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"


# ---------------------------------------------------------------------------
# Gradle — dependency locking
# ---------------------------------------------------------------------------

def test_gradle_dependency_locking_full(tmp_path):
    content = """\
allprojects {
    dependencyLocking {
        lockAllConfigurations()
        lockMode.set(LockMode.STRICT)
    }
}
"""
    (tmp_path / "build.gradle.kts").write_text(content)
    (tmp_path / "gradle.lockfile").write_text("# lockfile")
    result = audit.audit_gradle(str(tmp_path))
    assert result["dependency_locking"]["status"] == "pass"
    assert result["dependency_locking"]["strict_mode"] is True


def test_gradle_dependency_locking_missing(tmp_path):
    (tmp_path / "build.gradle.kts").write_text(BUILD_KTS_EXACT)
    result = audit.audit_gradle(str(tmp_path))
    assert result["dependency_locking"]["status"] == "fail"


def test_gradle_no_lockfile_present_fails(tmp_path):
    content = """dependencyLocking { lockAllConfigurations() }"""
    (tmp_path / "build.gradle.kts").write_text(content)
    result = audit.audit_gradle(str(tmp_path))
    assert result["dependency_locking"]["status"] == "fail"
    assert result["dependency_locking"]["lockfile_count"] == 0


# ---------------------------------------------------------------------------
# Gradle — verification metadata
# ---------------------------------------------------------------------------

def test_gradle_verification_metadata_pass(tmp_path):
    (tmp_path / "build.gradle.kts").write_text("")
    write_file(tmp_path, "gradle/verification-metadata.xml",
               "<verification-metadata><configuration>"
               "<verify-metadata>true</verify-metadata>"
               "<verify-signatures>true</verify-signatures>"
               "</configuration></verification-metadata>")
    result = audit.audit_gradle(str(tmp_path))
    assert result["dependency_verification"]["status"] == "pass"
    assert result["dependency_verification"]["verify_signatures"] is True


def test_gradle_verification_metadata_missing(tmp_path):
    (tmp_path / "build.gradle.kts").write_text("")
    result = audit.audit_gradle(str(tmp_path))
    assert result["dependency_verification"]["status"] == "fail"
    assert result["dependency_verification"]["file_present"] is False


# ---------------------------------------------------------------------------
# Gradle — wrapper SHA
# ---------------------------------------------------------------------------

def test_gradle_wrapper_sha_present(tmp_path):
    (tmp_path / "build.gradle.kts").write_text("")
    write_file(tmp_path, "gradle/wrapper/gradle-wrapper.properties",
               "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.10.2-bin.zip\n"
               "distributionSha256Sum=31c55713e40233a8303827ceb42ca48a47267a0ad4bab9177123121e71524c26\n")
    result = audit.audit_gradle(str(tmp_path))
    assert result["wrapper"]["status"] == "pass"
    assert result["wrapper"]["distribution_sha256"] is True


def test_gradle_wrapper_sha_missing(tmp_path):
    (tmp_path / "build.gradle.kts").write_text("")
    write_file(tmp_path, "gradle/wrapper/gradle-wrapper.properties",
               "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.10.2-bin.zip\n")
    result = audit.audit_gradle(str(tmp_path))
    assert result["wrapper"]["status"] == "fail"
    assert result["wrapper"]["distribution_sha256"] is False


# ---------------------------------------------------------------------------
# Gradle — repository control
# ---------------------------------------------------------------------------

def test_gradle_repo_control_pass(tmp_path):
    content = """\
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        mavenCentral()
    }
}
"""
    (tmp_path / "settings.gradle.kts").write_text(content)
    result = audit.audit_gradle(str(tmp_path))
    assert result["repository_control"]["status"] == "pass"


def test_gradle_maven_local_flagged(tmp_path):
    content = """\
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        mavenLocal()
        mavenCentral()
    }
}
"""
    (tmp_path / "settings.gradle.kts").write_text(content)
    result = audit.audit_gradle(str(tmp_path))
    assert result["repository_control"]["status"] == "fail"
    assert result["repository_control"]["uses_mavenLocal"] is True


def test_gradle_jcenter_flagged(tmp_path):
    content = """\
repositories {
    jcenter()
}
"""
    (tmp_path / "build.gradle.kts").write_text(content)
    result = audit.audit_gradle(str(tmp_path))
    assert result["repository_control"]["uses_jcenter"] is True
    assert result["repository_control"]["status"] == "fail"


# ---------------------------------------------------------------------------
# Gradle — reject dynamic resolution
# ---------------------------------------------------------------------------

def test_gradle_failOnNonReproducible_pass(tmp_path):
    content = """\
configurations.all {
    resolutionStrategy {
        failOnNonReproducibleResolution()
    }
}
"""
    (tmp_path / "build.gradle.kts").write_text(content)
    result = audit.audit_gradle(str(tmp_path))
    assert result["reject_dynamic"]["status"] == "pass"


def test_gradle_no_reject_dynamic_fails(tmp_path):
    (tmp_path / "build.gradle.kts").write_text(BUILD_KTS_EXACT)
    result = audit.audit_gradle(str(tmp_path))
    assert result["reject_dynamic"]["status"] == "fail"


# ---------------------------------------------------------------------------
# Gradle — CI
# ---------------------------------------------------------------------------

def test_gradle_ci_uses_wrapper_pass(tmp_path):
    (tmp_path / "build.gradle.kts").write_text("")
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: ./gradlew --no-daemon build\n")
    result = audit.audit_gradle(str(tmp_path))
    assert result["ci"]["uses_wrapper"] is True
    assert result["ci"]["status"] == "pass"


def test_gradle_ci_writes_locks_fails(tmp_path):
    (tmp_path / "build.gradle.kts").write_text("")
    make_workflow(tmp_path, "ci.yml",
                  "steps:\n  - run: ./gradlew dependencies --write-locks\n")
    result = audit.audit_gradle(str(tmp_path))
    assert result["ci"]["writes_locks_in_ci"] is True
    assert result["ci"]["status"] == "fail"


# ---------------------------------------------------------------------------
# Dependabot integration
# ---------------------------------------------------------------------------

def test_dependabot_maven_cooldown(tmp_path):
    (tmp_path / "pom.xml").write_text(POM_EXACT)
    write_file(tmp_path, ".github/dependabot.yml", """\
version: 2
updates:
  - package-ecosystem: "maven"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
""")
    result = audit.audit_dependabot(str(tmp_path), ["maven"])
    assert result["ecosystems"]["maven"]["status"] == "pass"


def test_dependabot_gradle_wrapper_subfinding(tmp_path):
    (tmp_path / "build.gradle.kts").write_text("")
    write_file(tmp_path, ".github/dependabot.yml", """\
version: 2
updates:
  - package-ecosystem: "gradle"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
  - package-ecosystem: "gradle-wrapper"
    directory: "/"
    schedule:
      interval: "weekly"
""")
    result = audit.audit_dependabot(str(tmp_path), ["gradle"])
    assert result["ecosystems"]["gradle"]["status"] == "pass"
    assert result["ecosystems"]["gradle"]["gradle_wrapper_ecosystem"] == "pass"


def test_dependabot_gradle_wrapper_missing(tmp_path):
    (tmp_path / "build.gradle.kts").write_text("")
    write_file(tmp_path, ".github/dependabot.yml", """\
version: 2
updates:
  - package-ecosystem: "gradle"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
""")
    result = audit.audit_dependabot(str(tmp_path), ["gradle"])
    assert result["ecosystems"]["gradle"]["gradle_wrapper_ecosystem"] == "missing"
