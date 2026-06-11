# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Unit tests for audit_harden_runner()."""

import audit
from conftest import make_workflow

WF_NO_HR = "steps:\n  - run: npm ci\n"

WF_HR_AUDIT = """\
steps:
  - uses: step-security/harden-runner@v2
    with:
      egress-policy: audit
  - run: npm ci
"""

WF_HR_BLOCK = """\
steps:
  - uses: step-security/harden-runner@v2
    with:
      egress-policy: block
      disable-sudo: true
      allowed-endpoints: >
        registry.npmjs.org:443
  - run: npm ci
"""


# ---------------------------------------------------------------------------
# No workflows
# ---------------------------------------------------------------------------

def test_no_workflows(tmp_path):
    result = audit.audit_harden_runner(str(tmp_path))
    assert result["status"] == "no_workflows"
    assert result["workflows"] == {}


# ---------------------------------------------------------------------------
# Workflow without harden-runner
# ---------------------------------------------------------------------------

def test_workflow_missing_hr_fails(tmp_path):
    make_workflow(tmp_path, "ci.yml", WF_NO_HR)
    result = audit.audit_harden_runner(str(tmp_path))
    assert result["workflows"]["ci.yml"]["harden_runner_present"] is False
    assert result["workflows"]["ci.yml"]["status"] == "fail"
    assert result["status"] == "fail"


# ---------------------------------------------------------------------------
# Workflow with harden-runner in audit mode
# ---------------------------------------------------------------------------

def test_workflow_hr_audit_mode_warns(tmp_path):
    make_workflow(tmp_path, "ci.yml", WF_HR_AUDIT)
    result = audit.audit_harden_runner(str(tmp_path))
    assert result["workflows"]["ci.yml"]["harden_runner_present"] is True
    assert result["workflows"]["ci.yml"]["egress_policy"] == "audit"
    assert result["workflows"]["ci.yml"]["status"] == "warn"
    assert result["status"] == "warn"


# ---------------------------------------------------------------------------
# Workflow with harden-runner in block mode
# ---------------------------------------------------------------------------

def test_workflow_hr_block_mode_passes(tmp_path):
    make_workflow(tmp_path, "ci.yml", WF_HR_BLOCK)
    result = audit.audit_harden_runner(str(tmp_path))
    assert result["workflows"]["ci.yml"]["harden_runner_present"] is True
    assert result["workflows"]["ci.yml"]["egress_policy"] == "block"
    assert result["workflows"]["ci.yml"]["disable_sudo"] is True
    assert result["workflows"]["ci.yml"]["allowed_endpoints"] is True
    assert result["workflows"]["ci.yml"]["status"] == "pass"
    assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# Mixed workflows (one pass, one warn)
# ---------------------------------------------------------------------------

def test_mixed_workflows_overall_warn(tmp_path):
    make_workflow(tmp_path, "ci.yml", WF_HR_BLOCK)
    make_workflow(tmp_path, "release.yml", WF_HR_AUDIT)
    result = audit.audit_harden_runner(str(tmp_path))
    assert result["workflows"]["ci.yml"]["status"] == "pass"
    assert result["workflows"]["release.yml"]["status"] == "warn"
    # overall not all pass → warn (at least one has harden-runner)
    assert result["status"] == "warn"


def test_mixed_workflows_one_missing_hr(tmp_path):
    make_workflow(tmp_path, "ci.yml", WF_HR_BLOCK)
    make_workflow(tmp_path, "release.yml", WF_NO_HR)
    result = audit.audit_harden_runner(str(tmp_path))
    assert result["workflows"]["release.yml"]["status"] == "fail"
    # some have HR, some don't → warn (at least one present)
    assert result["status"] == "warn"


# ---------------------------------------------------------------------------
# Quoted YAML values (lfreleng-actions feedback)
# ---------------------------------------------------------------------------

def test_quoted_egress_policy_block_passes(tmp_path):
    content = (
        "jobs:\n  build:\n    steps:\n"
        "      - uses: step-security/harden-runner@abc # v2\n"
        "        with:\n"
        "          egress-policy: 'block'\n"
        "          disable-sudo: 'true'\n"
        "          allowed-endpoints: >\n"
        "            github.com:443\n"
    )
    make_workflow(tmp_path, "ci.yml", content)
    result = audit.audit_harden_runner(str(tmp_path))
    wf = result["workflows"]["ci.yml"]
    assert wf["egress_policy"] == "block"
    assert wf["disable_sudo"] is True
    assert wf["status"] == "pass"


def test_double_quoted_egress_policy_audit_warns(tmp_path):
    content = (
        "jobs:\n  build:\n    steps:\n"
        "      - uses: step-security/harden-runner@abc # v2\n"
        "        with:\n"
        '          egress-policy: "audit"\n'
    )
    make_workflow(tmp_path, "ci.yml", content)
    result = audit.audit_harden_runner(str(tmp_path))
    assert result["workflows"]["ci.yml"]["egress_policy"] == "audit"
    assert result["workflows"]["ci.yml"]["status"] == "warn"


# ---------------------------------------------------------------------------
# Companion allow-list loaders + reusable-workflow callers
# (lfreleng-actions/.github feedback)
# ---------------------------------------------------------------------------

WF_LOADER_THEN_HR = (
    "jobs:\n  build:\n    steps:\n"
    "      - uses: lfreleng-actions/harden-runner-block-action@18d9c44 # v0.1.1\n"
    "      - uses: step-security/harden-runner@abc # v2\n"
    "        with:\n"
    "          egress-policy: block\n"
    "          allowed-endpoints: ${{ env.CONNECTION_ALLOW_LIST }}\n"
)

WF_HR_THEN_LOADER = (
    "jobs:\n  build:\n    steps:\n"
    "      - uses: step-security/harden-runner@abc # v2\n"
    "        with:\n"
    "          egress-policy: block\n"
    "          allowed-endpoints: ${{ env.CONNECTION_ALLOW_LIST }}\n"
    "      - uses: lfreleng-actions/harden-runner-block-action@18d9c44 # v0.1.1\n"
)

WF_LOADER_ONLY = (
    "jobs:\n  build:\n    steps:\n"
    "      - uses: lfreleng-actions/harden-runner-block-action@18d9c44 # v0.1.1\n"
    "      - uses: actions/checkout@abc # v6\n"
)

WF_REUSABLE_CALLER = (
    "jobs:\n  audit:\n"
    "    uses: lfit/releng-reusable-workflows/.github/workflows/reuse-audit.yaml@f43b219 # v0.6.0\n"
    "    permissions:\n      contents: read\n"
    "    with:\n      warn_only: true\n"
)


def test_loader_before_harden_runner_block_passes(tmp_path):
    make_workflow(tmp_path, "ci.yml", WF_LOADER_THEN_HR)
    result = audit.audit_harden_runner(str(tmp_path))
    wf = result["workflows"]["ci.yml"]
    assert wf["status"] == "pass"
    assert "note" not in wf


def test_loader_after_harden_runner_warns_with_ordering_note(tmp_path):
    make_workflow(tmp_path, "ci.yml", WF_HR_THEN_LOADER)
    result = audit.audit_harden_runner(str(tmp_path))
    wf = result["workflows"]["ci.yml"]
    assert wf["status"] == "warn"
    assert "pre: hooks run in step order" in wf["note"]


def test_loader_without_harden_runner_fails_with_note(tmp_path):
    make_workflow(tmp_path, "ci.yml", WF_LOADER_ONLY)
    result = audit.audit_harden_runner(str(tmp_path))
    wf = result["workflows"]["ci.yml"]
    assert wf["status"] == "fail"
    assert "no step-security/harden-runner step" in wf["note"]


def test_reusable_workflow_caller_warns_with_note(tmp_path):
    make_workflow(tmp_path, "package-hardening-audit.yaml", WF_REUSABLE_CALLER)
    result = audit.audit_harden_runner(str(tmp_path))
    wf = result["workflows"]["package-hardening-audit.yaml"]
    assert wf["status"] == "warn"
    assert wf["harden_runner_present"] is False
    assert wf["reusable_workflow_call"] is True
    assert "reusable workflow" in wf["note"]
    # repo with only thin callers is warn overall, not fail
    assert result["status"] == "warn"


def test_harden_runner_in_comment_only_fails(tmp_path):
    content = (
        "jobs:\n  build:\n    steps:\n"
        "      # TODO: add step-security/harden-runner here\n"
        "      - uses: actions/checkout@abc # v6\n"
    )
    make_workflow(tmp_path, "ci.yml", content)
    result = audit.audit_harden_runner(str(tmp_path))
    assert result["workflows"]["ci.yml"]["harden_runner_present"] is False
    assert result["workflows"]["ci.yml"]["status"] == "fail"
