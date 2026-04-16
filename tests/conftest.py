# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""
Shared test configuration and fixture helpers for audit.py tests.
"""

import json
import sys
from pathlib import Path

# Make audit.py importable as `audit`
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "harden-packages"))


def write_file(tmp_path: Path, rel_path: str, content: str) -> Path:
    """Write content to a file within tmp_path, creating parent directories."""
    p = tmp_path / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def make_workflow(tmp_path: Path, name: str, content: str) -> Path:
    """Write a GitHub Actions workflow file."""
    return write_file(tmp_path, f".github/workflows/{name}", content)


def make_package_json(tmp_path: Path, deps: dict | None = None, dev_deps: dict | None = None, pkg_manager: str = "") -> Path:
    """Write a minimal package.json."""
    data: dict = {}
    if deps:
        data["dependencies"] = deps
    if dev_deps:
        data["devDependencies"] = dev_deps
    if pkg_manager:
        data["packageManager"] = pkg_manager
    return write_file(tmp_path, "package.json", json.dumps(data))
