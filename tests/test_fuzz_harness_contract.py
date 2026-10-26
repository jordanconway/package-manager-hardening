# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""
Drift guard for the Atheris harnesses in fuzz/.

The harnesses call audit.py directly, so an audit.py change can break them --
but atheris ships wheels for Linux x86_64 only and is deliberately not in the
dev dependency group, so nothing in the PR suite imports them. The only signal
is the weekly Fuzz workflow, and in October 2026 both harnesses sat broken
behind a separate atheris install failure: fuzz_audit_parsers was calling
`audit_dependabot(root)` after the function gained a `detected_ecosystems`
parameter, and fuzz_audit_helpers crashed in its own fixture setup.

This module closes that gap without needing atheris. It:

  1. Installs a deterministic stub `atheris` and drives each harness's real
     TestOneInput over a spread of inputs -- catching signature drift and
     crashes in the harnesses' own setup code.
  2. Compares the regex corpora copied into fuzz_audit_helpers against the
     patterns audit.py actually uses, so the two cannot silently diverge.

These are tests of the *harnesses*, not of audit.py. tests/test_fuzz.py covers
audit.py itself with Hypothesis.
"""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import random
import re
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
FUZZ_DIR = REPO_ROOT / "fuzz"
AUDIT_PY = REPO_ROOT / "skills" / "harden-packages" / "audit.py"

HARNESSES = ("fuzz_audit_helpers", "fuzz_audit_parsers")

# Characters chosen to provoke the failure modes the harnesses exist to find:
# regex metacharacters, NUL and control bytes, non-ASCII, and the punctuation
# that shows up in the manifests audit.py parses.
_ADVERSARIAL = "\x00\n\r\t%\\[](){}|*+?^$.'\"abcABC019 é中�:=-_/<>#"


class _StubFuzzedDataProvider:
    """Deterministic stand-in for atheris.FuzzedDataProvider."""

    def __init__(self, data: bytes) -> None:
        self._r = random.Random(data)

    def ConsumeIntInRange(self, lo: int, hi: int) -> int:  # noqa: N802
        return self._r.randint(lo, hi)

    def ConsumeUnicode(self, count: int) -> str:  # noqa: N802
        return "".join(self._r.choice(_ADVERSARIAL) for _ in range(self._r.randint(0, count)))

    def ConsumeBytes(self, count: int) -> bytes:  # noqa: N802
        n = self._r.randint(0, min(count, 64))
        return bytes(self._r.randrange(256) for _ in range(n))

    def PickValueInList(self, values):  # noqa: N802
        return self._r.choice(list(values))


@contextlib.contextmanager
def _noop_instrument_imports():
    """Stand-in for atheris.instrument_imports(); must propagate exceptions."""
    yield


def _stub_atheris() -> types.ModuleType:
    mod = types.ModuleType("atheris")
    mod.FuzzedDataProvider = _StubFuzzedDataProvider
    mod.instrument_imports = _noop_instrument_imports
    mod.Setup = lambda argv, fn: None
    mod.Fuzz = lambda: None
    return mod


@pytest.fixture(params=HARNESSES)
def harness(request):
    """Import a real harness module with atheris stubbed out."""
    name = request.param
    saved = sys.modules.get("atheris")
    sys.modules["atheris"] = _stub_atheris()
    try:
        spec = importlib.util.spec_from_file_location(name, FUZZ_DIR / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        if saved is None:
            sys.modules.pop("atheris", None)
        else:
            sys.modules["atheris"] = saved
        sys.modules.pop(name, None)


# ---------------------------------------------------------------------------
# 1. The harnesses still run against the current audit.py
# ---------------------------------------------------------------------------


def test_harness_survives_adversarial_inputs(harness):
    """
    Drive the harness's real TestOneInput over a spread of inputs.

    A TypeError here means the harness drifted from an audit.py signature. An
    AssertionError means the harness found something in audit.py -- which the
    weekly Fuzz run would also report, and is a genuine finding either way.
    """
    for seed in range(120):
        harness.TestOneInput(str(seed).encode())


def test_harness_exposes_atheris_entry_points(harness):
    """Atheris calls TestOneInput and main(); both must stay importable."""
    assert callable(harness.TestOneInput)
    assert callable(harness.main)


# ---------------------------------------------------------------------------
# 2. The parsers harness targets real audit functions
# ---------------------------------------------------------------------------


def test_parser_targets_are_real_audit_functions():
    """Every key in TARGETS must name a function that still exists in audit.py."""
    sys.path.insert(0, str(REPO_ROOT / "skills" / "harden-packages"))
    import audit  # noqa: PLC0415

    targets = _literal_assignment(FUZZ_DIR / "fuzz_audit_parsers.py", "TARGETS")
    assert targets, "TARGETS not found in fuzz_audit_parsers.py"
    for fn_name in targets:
        assert hasattr(audit, fn_name), f"TARGETS names {fn_name}, which audit.py no longer defines"
        assert callable(getattr(audit, fn_name))


# ---------------------------------------------------------------------------
# 3. The helper harness's regex corpora match audit.py
# ---------------------------------------------------------------------------


def _literal_assignment(path: Path, name: str):
    """Return the value of a module-level literal assignment, without importing."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name:
            return ast.literal_eval(node.value)
    return None


def _audit_patterns() -> dict[str, set[str]]:
    """Collect the literal patterns audit.py passes to grep() and find_value()."""
    found: dict[str, set[str]] = {"grep": set(), "find_value": set()}
    tree = ast.parse(AUDIT_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in found
            and len(node.args) >= 2
        ):
            arg = node.args[1]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found[node.func.id].add(arg.value)
    return found


def test_grep_corpus_still_matches_audit():
    """
    GREP_PATTERNS is a curated subset of audit.py's grep() patterns.

    Fuzzing a pattern audit.py no longer uses tests nothing, so every entry
    must still appear in audit.py.
    """
    corpus = _literal_assignment(FUZZ_DIR / "fuzz_audit_helpers.py", "GREP_PATTERNS")
    assert corpus, "GREP_PATTERNS not found in fuzz_audit_helpers.py"
    real = _audit_patterns()["grep"]
    stale = [p for p in corpus if p not in real]
    assert not stale, f"GREP_PATTERNS entries no longer used by audit.py: {stale}"


def test_find_value_corpus_covers_every_audit_pattern():
    """
    FIND_VALUE_PATTERNS claims to hold *every* find_value() pattern in audit.py.

    Equality in both directions: a new pattern in audit.py must be added here,
    and a removed one must be dropped.
    """
    corpus = _literal_assignment(FUZZ_DIR / "fuzz_audit_helpers.py", "FIND_VALUE_PATTERNS")
    assert corpus, "FIND_VALUE_PATTERNS not found in fuzz_audit_helpers.py"
    real = _audit_patterns()["find_value"]
    missing = sorted(real - set(corpus))
    stale = sorted(set(corpus) - real)
    assert not missing, f"audit.py find_value patterns missing from FIND_VALUE_PATTERNS: {missing}"
    assert not stale, f"FIND_VALUE_PATTERNS entries no longer used by audit.py: {stale}"


def test_find_value_corpus_patterns_have_exactly_one_group():
    """
    find_value returns `m.group(1)`, so a pattern without a capturing group
    raises IndexError by contract. Feeding it one would be a harness bug
    reported as a false finding, which is exactly what happened in Oct 2026.
    """
    corpus = _literal_assignment(FUZZ_DIR / "fuzz_audit_helpers.py", "FIND_VALUE_PATTERNS")
    for pattern in corpus:
        assert re.compile(pattern).groups == 1, f"find_value pattern must have exactly one group: {pattern!r}"
