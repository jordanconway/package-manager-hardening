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


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    choice = fdp.ConsumeIntInRange(0, 3)

    if choice == 0:
        # Regex DoS surface: arbitrary patterns against arbitrary content.
        pattern = fdp.ConsumeUnicode(128)
        content = fdp.ConsumeUnicode(2048)
        try:
            audit.grep(content, pattern)
        except Exception as exc:
            # Bad patterns from user-supplied workflow text are realistic.
            # ReDoS / re.error are bugs; everything else is a bug.
            raise AssertionError(
                f"grep raised on adversarial input: {type(exc).__name__}: {exc}"
            ) from exc

    elif choice == 1:
        pattern = fdp.ConsumeUnicode(128)
        content = fdp.ConsumeUnicode(2048)
        try:
            audit.find_value(content, pattern)
        except Exception as exc:
            raise AssertionError(
                f"find_value raised on adversarial input: {type(exc).__name__}: {exc}"
            ) from exc

    elif choice == 2:
        # is_gitignored writes a .gitignore and queries it.
        gi_content = fdp.ConsumeUnicode(2048)
        path = fdp.ConsumeUnicode(256)
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            try:
                (root / ".gitignore").write_text(gi_content, errors="replace")
                audit.is_gitignored(str(root), path)
            except OSError:
                return
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
                # Skip path-traversal attempts; the function isn't expected
                # to defend against malicious filesystems.
                if "/" in name or ".." in name or not name.strip():
                    continue
                try:
                    (root / name).write_bytes(fdp.ConsumeBytes(256))
                except OSError:
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
