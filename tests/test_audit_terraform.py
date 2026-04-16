# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Unit tests for audit_terraform()."""

import audit
from conftest import make_workflow, write_file


TERRAFORM_BLOCK = 'terraform {\n  required_providers {\n    aws = { source = "hashicorp/aws", version = "= 5.0.0" }\n  }\n}\n'
TERRAFORM_LOOSE = 'terraform {\n  required_providers {\n    aws = { source = "hashicorp/aws" }\n  }\n}\n\nresource "aws_s3_bucket" "b" {}\n'


# ---------------------------------------------------------------------------
# Lockfile
# ---------------------------------------------------------------------------

def test_lockfile_present_passes(tmp_path):
    (tmp_path / "main.tf").write_text(TERRAFORM_BLOCK)
    (tmp_path / ".terraform.lock.hcl").write_text("# lockfile\n")
    result = audit.audit_terraform(str(tmp_path))
    assert result["lockfile"]["status"] == "pass"


def test_lockfile_missing_fails(tmp_path):
    (tmp_path / "main.tf").write_text(TERRAFORM_BLOCK)
    result = audit.audit_terraform(str(tmp_path))
    assert result["lockfile"]["status"] == "fail"


def test_lockfile_per_module(tmp_path):
    # Module in a subdirectory
    module = tmp_path / "modules" / "vpc"
    module.mkdir(parents=True)
    (module / "main.tf").write_text(TERRAFORM_BLOCK)
    (module / ".terraform.lock.hcl").write_text("# lockfile\n")
    result = audit.audit_terraform(str(tmp_path))
    assert result["lockfile"]["status"] == "pass"


def test_lockfile_missing_in_one_module_fails(tmp_path):
    (tmp_path / "main.tf").write_text(TERRAFORM_BLOCK)
    module = tmp_path / "modules" / "vpc"
    module.mkdir(parents=True)
    (module / "main.tf").write_text(TERRAFORM_BLOCK)
    # No .terraform.lock.hcl in module dir
    (tmp_path / ".terraform.lock.hcl").write_text("# lockfile\n")
    result = audit.audit_terraform(str(tmp_path))
    assert result["lockfile"]["status"] == "fail"


# ---------------------------------------------------------------------------
# Version pins
# ---------------------------------------------------------------------------

def test_exact_provider_pin_passes(tmp_path):
    content = 'terraform {\n  required_providers {\n    aws = { source = "hashicorp/aws", version = "= 5.0.0" }\n  }\n}\n'
    (tmp_path / "main.tf").write_text(content)
    result = audit.audit_terraform(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"


def test_loose_provider_pin_detected(tmp_path):
    content = 'terraform {\n  required_providers {\n    aws = { source = "hashicorp/aws", version = "~> 5.0" }\n  }\n}\n'
    (tmp_path / "main.tf").write_text(content)
    result = audit.audit_terraform(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"
    assert result["exact_pins"]["loose_count"] > 0


# ---------------------------------------------------------------------------
# CLI detection (terraform vs tofu)
# ---------------------------------------------------------------------------

def test_terraform_cli_default(tmp_path):
    (tmp_path / "main.tf").write_text(TERRAFORM_BLOCK)
    result = audit.audit_terraform(str(tmp_path))
    assert result["cli"] == "terraform"


def test_tofu_cli_detected_from_workflow(tmp_path):
    (tmp_path / "main.tf").write_text(TERRAFORM_BLOCK)
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: tofu init\n  - run: tofu plan\n")
    result = audit.audit_terraform(str(tmp_path))
    assert result["cli"] == "tofu"


# ---------------------------------------------------------------------------
# lockfile=readonly
# ---------------------------------------------------------------------------

def test_lockfile_readonly_found(tmp_path):
    (tmp_path / "main.tf").write_text(TERRAFORM_BLOCK)
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: terraform plan -lockfile=readonly\n")
    result = audit.audit_terraform(str(tmp_path))
    assert result["lockfile_readonly"]["status"] == "pass"


def test_lockfile_readonly_missing(tmp_path):
    (tmp_path / "main.tf").write_text(TERRAFORM_BLOCK)
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: terraform plan\n")
    result = audit.audit_terraform(str(tmp_path))
    assert result["lockfile_readonly"]["status"] == "fail"


# ---------------------------------------------------------------------------
# OpenTofu state encryption
# ---------------------------------------------------------------------------

def test_opentofu_state_encryption_detected(tmp_path):
    (tmp_path / "main.tf").write_text(
        "terraform {\n  required_providers {}\n}\n\nencryption {\n  key_provider \"pbkdf2\" \"default\" {}\n}\n"
    )
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: tofu plan\n")
    result = audit.audit_terraform(str(tmp_path))
    assert result["cli"] == "tofu"
    assert result["opentofu"]["state_encryption"] is True
    assert result["opentofu"]["status"] == "pass"
