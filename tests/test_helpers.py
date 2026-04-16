# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Unit tests for audit.py helper functions."""

import re

import audit


def test_read_existing_file(tmp_path):
    p = tmp_path / "sample.txt"
    p.write_text("hello world", encoding="utf-8")
    assert audit.read(p) == "hello world"


def test_read_missing_file(tmp_path):
    assert audit.read(tmp_path / "nonexistent.txt") == ""


def test_exists_present(tmp_path):
    p = tmp_path / "file.txt"
    p.write_text("x")
    assert audit.exists(p) is True


def test_exists_absent(tmp_path):
    assert audit.exists(tmp_path / "nope.txt") is False


def test_is_gitignored_match(tmp_path):
    (tmp_path / ".gitignore").write_text("node_modules\npackage-lock.json\n")
    assert audit.is_gitignored(tmp_path, "package-lock.json") is True


def test_is_gitignored_no_match(tmp_path):
    (tmp_path / ".gitignore").write_text("node_modules\n")
    assert audit.is_gitignored(tmp_path, "package-lock.json") is False


def test_is_gitignored_comment_ignored(tmp_path):
    (tmp_path / ".gitignore").write_text("# package-lock.json\n")
    assert audit.is_gitignored(tmp_path, "package-lock.json") is False


def test_is_gitignored_no_gitignore(tmp_path):
    assert audit.is_gitignored(tmp_path, "anything") is False


def test_grep_match():
    assert audit.grep("npm ci --legacy-peer-deps", r"npm ci\b") is True


def test_grep_no_match():
    assert audit.grep("npm install", r"npm ci\b") is False


def test_grep_with_flags():
    assert audit.grep("GONOSUMDB=*", r"gonosumdb", re.IGNORECASE) is True


def test_find_value_match():
    content = "minimum-release-age = 10080\n"
    result = audit.find_value(content, r"minimum-release-age\s*=\s*(\d+)")
    assert result == "10080"


def test_find_value_no_match():
    assert audit.find_value("no match here", r"minimum-release-age\s*=\s*(\d+)") is None


def test_status_true():
    assert audit.status(True) == "pass"


def test_status_false():
    assert audit.status(False) == "fail"


def test_workflow_files_empty(tmp_path):
    result = audit.workflow_files(str(tmp_path))
    assert result == {}


def test_workflow_files_no_dir(tmp_path):
    result = audit.workflow_files(str(tmp_path))
    assert result == {}


def test_workflow_files_reads_yml_and_yaml(tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("steps: []")
    (wf / "release.yaml").write_text("steps: [release]")
    result = audit.workflow_files(str(tmp_path))
    assert "ci.yml" in result
    assert "release.yaml" in result
    assert result["ci.yml"] == "steps: []"


def test_glob_files_finds_matches(tmp_path):
    (tmp_path / "main.tf").write_text("terraform {}")
    (tmp_path / "vars.tf").write_text("variable x {}")
    results = audit.glob_files(str(tmp_path), "*.tf")
    names = [p.name for p in results]
    assert "main.tf" in names
    assert "vars.tf" in names


def test_glob_files_no_matches(tmp_path):
    assert audit.glob_files(str(tmp_path), "*.tf") == []
