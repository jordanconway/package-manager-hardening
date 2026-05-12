# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""
Coverage-guided fuzz harnesses for skills/harden-packages/audit.py.

Run locally:

    pip install atheris
    python fuzz/fuzz_audit_parsers.py -atheris_runs=100000

Or via the scheduled GitHub Actions workflow `.github/workflows/fuzz.yml`.

Each ecosystem audit function consumes one or more manifest / lockfile / workflow
files in a directory. The harness writes random bytes to the file the audit
function expects, runs the function, and asserts no unhandled exception is
raised. Atheris's libFuzzer instrumentation evolves inputs toward unexplored
branches \u2014 catches a different class of bug than the property-based suite in
tests/test_fuzz.py (which is *not* recognised by OpenSSF Scorecard's Fuzzing
check).
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


# Maps each audit function to the per-repo file(s) the function reads.
TARGETS = {
    "audit_nodejs": ("package.json",),
    "audit_python": ("pyproject.toml", "requirements.txt"),
    "audit_go": ("go.mod", "go.sum"),
    "audit_rust": ("Cargo.toml", "Cargo.lock"),
    "audit_php": ("composer.json", "composer.lock"),
    "audit_ruby": ("Gemfile", "Gemfile.lock"),
    "audit_terraform": ("main.tf", ".terraform.lock.hcl"),
    "audit_maven": ("pom.xml",),
    "audit_gradle": ("build.gradle", "settings.gradle"),
    "audit_harden_runner": (".github/workflows/ci.yml",),
    "audit_dependabot": (".github/dependabot.yml",),
}


def TestOneInput(data: bytes) -> None:
    """Atheris entry point. Each call: random bytes -> every audit function."""
    fdp = atheris.FuzzedDataProvider(data)
    # Pick which audit function to drive, plus content for each of its files.
    fn_name = fdp.PickValueInList(list(TARGETS.keys()))
    files = TARGETS[fn_name]

    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        for filename in files:
            target = root / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            # Consume up to ~4 KiB of random bytes for each manifest file.
            payload = fdp.ConsumeBytes(4096)
            try:
                target.write_bytes(payload)
            except OSError:
                return

        fn = getattr(audit, fn_name)
        try:
            fn(str(root))
        except Exception as exc:
            # Any unhandled exception is a bug. Atheris will minimise the input
            # and report the reproducer.
            raise AssertionError(
                f"{fn_name} raised on adversarial input: {type(exc).__name__}: {exc}"
            ) from exc


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
