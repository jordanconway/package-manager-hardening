# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""
Coverage-guided fuzz harness for skills/harden-packages/audit.py helpers.

Targets the parsing helpers (`grep`, `find_value`, `is_gitignored`,
`detect_ecosystems`) that every per-ecosystem audit function depends on.
A regex DoS or encoding crash in any of these blast-radiuses across every
ecosystem.

Run locally:

    pip install atheris
    python fuzz/fuzz_audit_helpers.py -atheris_runs=100000
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

import atheris

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "harden-packages"))

with atheris.instrument_imports():
    import audit  # noqa: E402


# audit.py only ever applies *hardcoded* patterns to untrusted file content --
# the pattern is never user-supplied, only the content is. So fuzz the content
# against the real patterns rather than generating regexes: a generated pattern
# exercises `re`, not audit.py. `find_value` in particular is documented to
# return "the first captured group", so feeding it a pattern with no group
# raises IndexError by contract rather than revealing a bug.
#
# Copied verbatim from audit.py; keep in sync when its patterns change.

# Backtracking-prone / quantifier-heavy patterns from audit.py's grep() calls.
GREP_PATTERNS = (
    r"GONOSUMDB\s*[=:]\s*['\"]?\*['\"]?|GONOSUMCHECK\s*[=:]\s*['\"]?\*['\"]?",
    r"^\s*ruby\s+['\"]",
    r"BUNDLE_FROZEN|bundle config.*frozen",
    r"bundle audit|bundler-audit",
    r"--strict-checksums|\s-C\b",
    r"--batch-mode|\s-B\b",
    r"dependencyLocking\s*\{",
    r"lockAllConfigurations\s*\(",
    r"LockMode\.STRICT|lockMode\.set\(\s*LockMode\.STRICT",
    r"mavenLocal\s*\(",
    r"jcenter\s*\(",
    r"failOnNonReproducibleResolution|failOnDynamicVersions",
    r"--write-locks|--write-verification-metadata",
    r"require-hashes\s*=\s*true",
    r"verify-hashes\s*=\s*true",
    r"<ManagePackageVersionsCentrally>\s*true\s*</ManagePackageVersionsCentrally>",
    r"^\s*steps:",
    r"disable-sudo:\s*[\"']?true[\"']?",
    r"lifecycleScripts\s*=\s*false",
    r"<RestorePackagesWithLockFile>\s*true\s*</RestorePackagesWithLockFile>",
    r"encryption\s*\{",
    r'package-ecosystem:\s*["\']?gradle-wrapper["\']?',
)

# Every find_value() pattern in audit.py. Each has exactly one capturing group,
# which is what find_value requires.
FIND_VALUE_PATTERNS = (
    r"\[cooldown\].*?days\s*=\s*(\d+)",
    r'minimumReleaseAge[:\s]+["\']?([^\s"\']+)',
    r"trustPolicy[:\s]+([^\s\n]+)",
    r'exclude-newer\s*=\s*["\']?([^"\'\\n\]]+)',
    r"days\s*=\s*(\d+)",
    r"egress-policy:\s*(\S+)",
    r"minimum-release-age\s*=\s*(\d+)",
    r"npmMinimalAgeGate[:\s]+(\d+)",
    r'minimumReleaseAge\s*=\s*["\']?([^"\'\\n]+)',
)


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    choice = fdp.ConsumeIntInRange(0, 3)

    if choice == 0:
        # ReDoS surface: adversarial *content* against a production pattern.
        pattern = fdp.PickValueInList(list(GREP_PATTERNS))
        content = fdp.ConsumeUnicode(2048)
        try:
            audit.grep(content, pattern)
        except Exception as exc:
            raise AssertionError(
                f"grep raised on adversarial input: {type(exc).__name__}: {exc} "
                f"(pattern={pattern!r})"
            ) from exc

    elif choice == 1:
        pattern = fdp.PickValueInList(list(FIND_VALUE_PATTERNS))
        content = fdp.ConsumeUnicode(2048)
        try:
            audit.find_value(content, pattern)
        except Exception as exc:
            raise AssertionError(
                f"find_value raised on adversarial input: {type(exc).__name__}: "
                f"{exc} (pattern={pattern!r})"
            ) from exc

    elif choice == 2:
        # is_gitignored writes a .gitignore and queries it.
        gi_content = fdp.ConsumeUnicode(2048)
        path = fdp.ConsumeUnicode(256)
        # Production paths come from a filesystem walk and never contain NUL,
        # so a NUL here would only test pathlib's own argument validation.
        if "\x00" in path:
            return
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            # Fixture setup: a failure to lay down the .gitignore is not a
            # finding, so it must not reach the assertion below.
            try:
                (root / ".gitignore").write_text(gi_content, errors="replace")
            except (OSError, ValueError):
                return
            try:
                audit.is_gitignored(str(root), path)
            except Exception as exc:
                raise AssertionError(
                    f"is_gitignored raised on adversarial input: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc

    else:
        # Random repo-shape: throw arbitrary file names into a tmp dir, then
        # let detect_ecosystems decide what's there.
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            for _ in range(fdp.ConsumeIntInRange(0, 8)):
                name = fdp.ConsumeUnicode(64)
                # Skip path-traversal attempts and names the filesystem cannot
                # represent; the function isn't expected to defend against
                # malicious filesystems, and a NUL byte makes pathlib raise
                # ValueError during *setup*, before detect_ecosystems is ever
                # reached.
                if "/" in name or ".." in name or "\x00" in name or not name.strip():
                    continue
                try:
                    (root / name).write_bytes(fdp.ConsumeBytes(256))
                except (OSError, ValueError):
                    continue
            try:
                audit.detect_ecosystems(str(root))
            except Exception as exc:
                raise AssertionError(
                    f"detect_ecosystems raised on adversarial input: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
