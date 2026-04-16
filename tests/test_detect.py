# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Tests for detect_ecosystems()."""

import pytest

import audit


def test_detect_empty_dir(tmp_path):
    assert audit.detect_ecosystems(str(tmp_path)) == []


def test_detect_nodejs(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    assert "nodejs" in audit.detect_ecosystems(str(tmp_path))


def test_detect_python_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    assert "python" in audit.detect_ecosystems(str(tmp_path))


def test_detect_python_requirements(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
    assert "python" in audit.detect_ecosystems(str(tmp_path))


def test_detect_go(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/foo\n\ngo 1.21\n")
    assert "go" in audit.detect_ecosystems(str(tmp_path))


def test_detect_rust(tmp_path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'foo'\n")
    assert "rust" in audit.detect_ecosystems(str(tmp_path))


def test_detect_php(tmp_path):
    (tmp_path / "composer.json").write_text("{}")
    assert "php" in audit.detect_ecosystems(str(tmp_path))


def test_detect_ruby(tmp_path):
    (tmp_path / "Gemfile").write_text('source "https://rubygems.org"\n')
    assert "ruby" in audit.detect_ecosystems(str(tmp_path))


def test_detect_terraform_required_providers(tmp_path):
    (tmp_path / "main.tf").write_text(
        'terraform {\n  required_providers {\n    aws = { source = "hashicorp/aws" }\n  }\n}\n'
    )
    assert "terraform" in audit.detect_ecosystems(str(tmp_path))


def test_detect_terraform_terraform_block(tmp_path):
    (tmp_path / "main.tf").write_text("terraform {\n  backend \"s3\" {}\n}\n")
    assert "terraform" in audit.detect_ecosystems(str(tmp_path))


def test_detect_terraform_tf_file_without_block_not_detected(tmp_path):
    # A .tf file that is just resource definitions — no terraform{} or required_providers
    (tmp_path / "resources.tf").write_text('resource "aws_s3_bucket" "b" {}\n')
    assert "terraform" not in audit.detect_ecosystems(str(tmp_path))


def test_detect_multi_ecosystem(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "go.mod").write_text("module example.com/foo\n\ngo 1.21\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    detected = audit.detect_ecosystems(str(tmp_path))
    assert "nodejs" in detected
    assert "go" in detected
    assert "python" in detected


@pytest.mark.parametrize("marker,ecosystem", [
    ("package.json", "nodejs"),
    ("go.mod", "go"),
    ("Cargo.toml", "rust"),
    ("composer.json", "php"),
    ("Gemfile", "ruby"),
])
def test_detect_single_markers(tmp_path, marker, ecosystem):
    (tmp_path / marker).write_text("")
    assert ecosystem in audit.detect_ecosystems(str(tmp_path))
