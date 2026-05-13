<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Fuzz corpus — `fuzz_audit_helpers`

Persistent corpus inputs for the [`fuzz/fuzz_audit_helpers.py`](../../fuzz_audit_helpers.py) Atheris harness. libFuzzer replays every file here at the start of each fuzz run, so any past crash becomes a permanent regression test even if the underlying bug is fixed.

Files in this directory **must remain raw bytes on disk** — libFuzzer reads them with `read(2)`, not as text. To keep them reviewable (per OpenSSF Baseline `OSPS-QA-05.02`, "no unreviewable binary artifacts"), every file is documented below with its exact byte sequence, the bug it triggered, and the unit-test regression that pins the same input.

## `crash-find_value-no-group`

| | |
|---|---|
| Size | 4 bytes |
| Hex | `00 8b 00 89` |
| Base64 | `AIsAiQ==` |
| Found by | Atheris, first scheduled run of `.github/workflows/fuzz.yml`, iteration #16 (~1s of fuzz time) |
| Bug | `audit.find_value()` raised `IndexError: no such group` when the regex pattern matched but had no capture group |
| Fix | [`skills/harden-packages/audit.py`](../../../skills/harden-packages/audit.py) — `find_value()` now returns `None` if `m.groups()` is empty |
| Regression test | [`tests/test_helpers.py::test_find_value_pattern_without_capture_group`](../../../tests/test_helpers.py) — pins the exact 4 bytes in source |
| Reachability from production callers | None: every internal call site in `audit.py` uses a pattern with `(...)`. Defensive fix to align the function with its documented contract ("return None on no match") |

Reproduce locally (Linux, Python 3.11):

```bash
pip install -r fuzz/requirements.txt
python fuzz/fuzz_audit_helpers.py fuzz/corpus/fuzz_audit_helpers/crash-find_value-no-group
# Expected: clean exit (the bug is fixed). Pre-fix: IndexError: no such group.
```

## Adding a new corpus entry

When a future fuzz run finds a crash:

1. Fix the bug in `skills/harden-packages/audit.py`.
2. Add a unit-test regression in `tests/test_helpers.py` (or the relevant `tests/test_audit_*.py`) that pins the exact input bytes in source.
3. Move the Atheris artifact (`fuzz-artifacts/crash-*`) into this directory with a descriptive name.
4. Add a section to this README following the same template as above (size, hex, base64, found-by, bug, fix, regression test, reachability).
