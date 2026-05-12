<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Fuzz harnesses

Coverage-guided fuzz harnesses for `skills/harden-packages/audit.py`, using [Atheris](https://github.com/google/atheris) (libFuzzer for Python).

## Why two fuzz suites?

| Suite | Tool | Goal | Where |
|---|---|---|---|
| Property-based | [Hypothesis](https://hypothesis.readthedocs.io/) | Catch crashes and contract violations on adversarial *shapes* of input. Runs on every PR. Fast. | [`tests/test_fuzz.py`](../tests/test_fuzz.py) |
| Coverage-guided | [Atheris](https://github.com/google/atheris) (libFuzzer) | Drive the parser toward unexplored branches using coverage feedback. Catches crashes property tests miss. Runs on a schedule. | [`fuzz/`](.) |

The two are complementary. Hypothesis is *blind* — it samples inputs from a strategy. Atheris is *guided* — it watches which branches each input exercises and mutates toward unexplored ones. Property tests cover declarative invariants ("audit must not crash"); coverage-guided fuzzing finds the inputs that satisfy those invariants in interesting ways.

This setup also satisfies [OpenSSF Scorecard's `Fuzzing` check](https://github.com/ossf/scorecard/blob/main/docs/checks.md#fuzzing) — the check's Python detector matches `import atheris`, **not** Hypothesis. (See [docs/github-actions.md](../docs/github-actions.md#fuzzing) for context.)

## Running locally

Atheris ships pre-built wheels for Linux x86_64 + Python ≤ 3.11. On macOS or with Python ≥ 3.12 you'll need to build from source against an LLVM/clang install — easier to use the CI workflow or a Linux VM/container.

```bash
# Linux + Python 3.11
python3.11 -m venv .venv-fuzz
source .venv-fuzz/bin/activate
pip install atheris

# Run a single harness for 60 seconds
python fuzz/fuzz_audit_parsers.py -atheris_runs=0 -max_total_time=60

# Or fixed iteration count
python fuzz/fuzz_audit_helpers.py -atheris_runs=100000
```

Reproducing a crash:

```bash
# Atheris prints the crash input as a base64 blob on failure;
# save it as crash-XXXX and replay:
python fuzz/fuzz_audit_parsers.py crash-XXXX
```

## Continuous fuzzing in CI

The scheduled workflow [`.github/workflows/fuzz.yml`](../.github/workflows/fuzz.yml) runs each harness for a few minutes weekly and on `workflow_dispatch`. Crashes upload as artifacts and fail the run.

## Adding a harness

1. Create `fuzz/fuzz_<surface>.py` with `import atheris`, an `instrument_imports()` block around `import audit`, and a `TestOneInput(data: bytes)` function.
2. Add it to the `fuzz.yml` matrix.
3. Update [`tests/test_fuzz.py`](../tests/test_fuzz.py) with a Hypothesis property test for the same surface (different bug class, complements rather than replaces).

## What to do with crashes

Every crash is a bug. The audit functions' contract is "must not raise on any input from a target repository's filesystem". If the input is something the audit function should reject explicitly (e.g. binary garbage in a YAML file), the function should detect and skip it cleanly, not crash.

Fix the underlying defensive-parsing bug in `audit.py`, then add the crash input to the corpus (`fuzz/corpus/<harness>/`) so it's regression-tested forever.
