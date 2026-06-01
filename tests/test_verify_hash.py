# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""
Unit tests for verify_hash.py.

All upstream HTTP calls are mocked — these tests must not touch the network.
The point of the helper is to be the *one* place agents go for hashes; if its
contract drifts (output format, exit codes, subcommand names) every AGENTS-*.md
file that references it breaks silently. These tests pin that contract.
"""

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Make verify_hash.py importable as `verify_hash`
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "harden-packages"))

import verify_hash  # noqa: E402

# ---------- helpers ----------------------------------------------------------

def _run(argv, json_response=None, text_response=None, run_output=None):
    """Invoke verify_hash.main(argv) with HTTP / subprocess calls mocked."""
    patches = []
    if json_response is not None:
        patches.append(patch.object(verify_hash, "_http_json", return_value=json_response))
    if text_response is not None:
        patches.append(patch.object(verify_hash, "_http_text", return_value=text_response))
    if run_output is not None:
        patches.append(patch.object(verify_hash, "_run", return_value=run_output))

    for p in patches:
        p.start()
    try:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            try:
                verify_hash.main(argv)
                code = 0
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
        return code, buf.getvalue()
    finally:
        for p in patches:
            p.stop()


# ---------- parser / usage --------------------------------------------------

def test_no_subcommand_errors():
    with pytest.raises(SystemExit) as exc:
        verify_hash.main([])
    assert exc.value.code == 2


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        verify_hash.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    # Every advertised subcommand must appear in --help so AGENTS files stay in sync.
    for sub in (
        "gh-action", "git-ref", "oci", "pypi", "npm", "crate", "gem",
        "packagist", "gradle-dist", "maven", "tf-provider", "go-module",
    ):
        assert sub in out


# ---------- gh-action --------------------------------------------------------

def test_gh_action_prints_bare_sha():
    sha = "34e114876b0b11c390a56381ad16ebd13914f8d5"
    code, out = _run(
        ["gh-action", "actions/checkout", "v4"],
        json_response={
            "sha": sha,
            "commit": {"committer": {"date": "2025-01-15T00:00:00Z"}, "message": "release v4\n\nbody"},
        },
    )
    assert code == 0
    assert out.strip() == sha


def test_gh_action_json_mode_includes_metadata():
    sha = "34e114876b0b11c390a56381ad16ebd13914f8d5"
    code, out = _run(
        ["--json", "gh-action", "actions/checkout", "v4"],
        json_response={
            "sha": sha,
            "commit": {"committer": {"date": "2025-01-15T00:00:00Z"}, "message": "release v4"},
        },
    )
    assert code == 0
    data = json.loads(out)
    assert data["hash"] == sha
    assert data["repo"] == "actions/checkout"
    assert data["ref"] == "v4"
    assert data["date"] == "2025-01-15T00:00:00Z"
    assert data["message"] == "release v4"


def test_gh_action_rejects_bare_repo():
    with pytest.raises(SystemExit) as exc:
        verify_hash.main(["gh-action", "checkout", "v4"])
    assert exc.value.code == 2


def test_gh_action_rejects_short_sha_response():
    # API returns a truncated value — must not be silently accepted.
    with pytest.raises(SystemExit) as exc, \
         patch.object(verify_hash, "_http_json", return_value={"sha": "34e1148"}):
        verify_hash.main(["gh-action", "actions/checkout", "v4"])
    assert exc.value.code == 1


# ---------- pypi -------------------------------------------------------------

_PYPI_REQUESTS = {
    "urls": [
        {
            "packagetype": "bdist_wheel",
            "filename": "requests-2.32.3-py3-none-any.whl",
            "digests": {"sha256": "wheelsha"},
        },
        {
            "packagetype": "sdist",
            "filename": "requests-2.32.3.tar.gz",
            "digests": {"sha256": "sdistsha"},
        },
    ]
}


def test_pypi_all_artifacts_prints_two_lines():
    code, out = _run(["pypi", "requests", "2.32.3"], json_response=_PYPI_REQUESTS)
    assert code == 0
    lines = out.strip().splitlines()
    assert len(lines) == 2
    assert "wheelsha  requests-2.32.3-py3-none-any.whl" in lines
    assert "sdistsha  requests-2.32.3.tar.gz" in lines


def test_pypi_sdist_filter_prints_bare_hash():
    code, out = _run(["pypi", "requests", "2.32.3", "--sdist"], json_response=_PYPI_REQUESTS)
    assert code == 0
    assert out.strip() == "sdistsha"


def test_pypi_wheel_filter_prints_bare_hash():
    code, out = _run(["pypi", "requests", "2.32.3", "--wheel"], json_response=_PYPI_REQUESTS)
    assert code == 0
    assert out.strip() == "wheelsha"


def test_pypi_empty_artifacts_exits_nonzero():
    with pytest.raises(SystemExit) as exc, \
         patch.object(verify_hash, "_http_json", return_value={"urls": []}):
        verify_hash.main(["pypi", "requests", "2.32.3"])
    assert exc.value.code == 1


# ---------- npm --------------------------------------------------------------

def test_npm_prints_sri_integrity():
    integrity = "sha512-XI5MPzVNApjAyhQzphX8BkmKsKUxD4LdyK24iZeQGinBN9yTQT3bFlCBy/aVx2HrNcqQGsdot8ghrjyrvMCoEA=="
    code, out = _run(
        ["npm", "left-pad", "1.3.0"],
        json_response={"dist": {"integrity": integrity, "tarball": "https://...", "shasum": "abc"}},
    )
    assert code == 0
    assert out.strip() == integrity


def test_npm_scoped_package_url_encoded():
    integrity = "sha512-AAA"
    seen = {}

    def fake(url, headers=None):
        seen["url"] = url
        return {"dist": {"integrity": integrity, "tarball": "", "shasum": ""}}

    with patch.object(verify_hash, "_http_json", side_effect=fake), \
         patch("sys.stdout", io.StringIO()):
        verify_hash.main(["npm", "@scope/pkg", "1.0.0"])
    assert "%2F" in seen["url"]
    assert "@scope" in seen["url"]


# ---------- crate / gem / packagist -----------------------------------------

def test_crate_prints_checksum():
    code, out = _run(
        ["crate", "serde", "1.0.210"],
        json_response={"version": {"checksum": "cratesha", "yanked": False}},
    )
    assert code == 0
    assert out.strip() == "cratesha"


def test_gem_prints_sha():
    code, out = _run(
        ["gem", "rails", "7.2.1"],
        json_response={"sha": "gemsha", "platform": "ruby"},
    )
    assert code == 0
    assert out.strip() == "gemsha"


def test_packagist_prefers_dist_shasum_over_source_reference():
    code, out = _run(
        ["packagist", "symfony/console", "7.1.5"],
        json_response={
            "packages": {
                "symfony/console": [
                    {"version": "7.1.4", "dist": {"shasum": "old"}, "source": {"reference": "oldref"}},
                    {
                        "version": "7.1.5",
                        "dist": {"shasum": "newsha", "url": "https://..."},
                        "source": {"reference": "newref"},
                    },
                ]
            }
        },
    )
    assert code == 0
    assert out.strip() == "newsha"


def test_packagist_unknown_version_exits_nonzero():
    with pytest.raises(SystemExit) as exc, \
         patch.object(verify_hash, "_http_json", return_value={"packages": {"v/p": [{"version": "1.0.0"}]}}):
        verify_hash.main(["packagist", "v/p", "9.9.9"])
    assert exc.value.code == 1


def test_packagist_requires_vendor_slash_name():
    with pytest.raises(SystemExit) as exc:
        verify_hash.main(["packagist", "console", "1.0"])
    assert exc.value.code == 2


# ---------- gradle-dist ------------------------------------------------------

def test_gradle_dist_returns_64_char_sha():
    sha = "a" * 64
    code, out = _run(["gradle-dist", "8.10"], text_response=sha)
    assert code == 0
    assert out.strip() == sha


def test_gradle_dist_rejects_bad_length():
    with pytest.raises(SystemExit) as exc, \
         patch.object(verify_hash, "_http_text", return_value="deadbeef"):
        verify_hash.main(["gradle-dist", "8.10"])
    assert exc.value.code == 1


def test_gradle_dist_only_accepts_bin_or_all():
    with pytest.raises(SystemExit) as exc:
        verify_hash.main(["gradle-dist", "8.10", "src"])
    assert exc.value.code == 2


# ---------- maven ------------------------------------------------------------

def test_maven_falls_back_to_sha1_when_sha256_missing():
    calls = []

    def fake_text(url, headers=None):
        calls.append(url)
        if url.endswith(".sha256"):
            raise SystemExit(1)  # mimics _die for HTTP 404
        return "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef  commons-lang3-3.17.0.jar"

    with patch.object(verify_hash, "_http_text", side_effect=fake_text), \
         patch("sys.stdout", io.StringIO()) as buf:
        verify_hash.main(["maven", "org.apache.commons:commons-lang3:3.17.0"])
    assert calls[0].endswith(".sha256")
    assert calls[1].endswith(".sha1")
    assert buf.getvalue().strip() == "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"


def test_maven_rejects_bad_gav():
    with pytest.raises(SystemExit) as exc:
        verify_hash.main(["maven", "commons-lang3"])
    assert exc.value.code == 2


# ---------- tf-provider ------------------------------------------------------

_TF_VERSIONS = {"versions": [{"version": "5.83.0"}, {"version": "5.84.0"}]}


def test_tf_provider_lists_versions_when_unspecified():
    code, out = _run(["tf-provider", "hashicorp/aws"], json_response=_TF_VERSIONS)
    assert code == 0
    assert out.strip().splitlines() == ["5.83.0", "5.84.0"]


def test_tf_provider_verifies_known_version():
    code, out = _run(["tf-provider", "hashicorp/aws", "5.84.0"], json_response=_TF_VERSIONS)
    assert code == 0
    assert out.strip() == "5.84.0"


def test_tf_provider_rejects_unknown_version():
    with pytest.raises(SystemExit) as exc, \
         patch.object(verify_hash, "_http_json", return_value=_TF_VERSIONS):
        verify_hash.main(["tf-provider", "hashicorp/aws", "9.9.9"])
    assert exc.value.code == 1


def test_tf_provider_opentofu_flag_uses_opentofu_registry():
    seen = {}

    def fake(url, headers=None):
        seen["url"] = url
        return _TF_VERSIONS

    with patch.object(verify_hash, "_http_json", side_effect=fake), \
         patch("sys.stdout", io.StringIO()):
        verify_hash.main(["tf-provider", "hashicorp/aws", "--opentofu"])
    assert "registry.opentofu.org" in seen["url"]


# ---------- go-module --------------------------------------------------------

def test_go_module_returns_h1_hash():
    h1 = "h1:abcdef=="
    code, out = _run(["go-module", "github.com/stretchr/testify", "v1.9.0"], text_response=h1)
    assert code == 0
    assert out.strip() == h1


def test_go_module_rejects_non_h1_response():
    with pytest.raises(SystemExit) as exc, \
         patch.object(verify_hash, "_http_text", return_value="deadbeef"):
        verify_hash.main(["go-module", "github.com/foo/bar", "v1.0.0"])
    assert exc.value.code == 1


def test_go_module_proxy_lowercases_module_path():
    """proxy.golang.org case-folds module paths; verify the URL we build matches."""
    seen = {}

    def fake(url, headers=None):
        seen["url"] = url
        return "h1:ok="

    with patch.object(verify_hash, "_http_text", side_effect=fake), \
         patch("sys.stdout", io.StringIO()):
        verify_hash.main(["go-module", "github.com/Stretchr/Testify", "v1.9.0"])
    assert "github.com/stretchr/testify" in seen["url"]
    assert "github.com/Stretchr/Testify" not in seen["url"]


# ---------- oci --------------------------------------------------------------

def test_oci_uses_crane_when_available():
    with patch("shutil.which", side_effect=lambda t: "/usr/local/bin/crane" if t == "crane" else None), \
         patch.object(verify_hash, "_run", return_value="sha256:" + "a" * 64), \
         patch("sys.stdout", io.StringIO()) as buf:
        verify_hash.main(["oci", "node:20-alpine"])
    assert buf.getvalue().strip() == "sha256:" + "a" * 64


def test_oci_errors_when_no_tool_available():
    with patch("shutil.which", return_value=None), \
         pytest.raises(SystemExit) as exc:
        verify_hash.main(["oci", "node:20-alpine"])
    assert exc.value.code == 3


def test_oci_rejects_non_sha256_digest():
    with patch("shutil.which", side_effect=lambda t: "/usr/local/bin/crane" if t == "crane" else None), \
         patch.object(verify_hash, "_run", return_value="md5:something"), \
         pytest.raises(SystemExit) as exc:
        verify_hash.main(["oci", "node:20-alpine"])
    assert exc.value.code == 1


# ---------- git-ref ----------------------------------------------------------

def test_git_ref_prefers_annotated_tag_dereference():
    output = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\trefs/tags/v1.0.0\n"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\trefs/tags/v1.0.0^{}\n"
    )
    with patch("shutil.which", return_value="/usr/bin/git"), \
         patch.object(verify_hash, "_run", return_value=output), \
         patch("sys.stdout", io.StringIO()) as buf:
        verify_hash.main(["git-ref", "https://example.com/x.git", "v1.0.0"])
    assert buf.getvalue().strip() == "b" * 40


def test_git_ref_falls_back_to_first_when_no_dereference():
    output = "cccccccccccccccccccccccccccccccccccccccc\trefs/heads/main\n"
    with patch("shutil.which", return_value="/usr/bin/git"), \
         patch.object(verify_hash, "_run", return_value=output), \
         patch("sys.stdout", io.StringIO()) as buf:
        verify_hash.main(["git-ref", "https://example.com/x.git", "main"])
    assert buf.getvalue().strip() == "c" * 40


def test_git_ref_no_git_binary_exits_3():
    with patch("shutil.which", return_value=None), \
         pytest.raises(SystemExit) as exc:
        verify_hash.main(["git-ref", "https://example.com/x.git", "v1.0.0"])
    assert exc.value.code == 3
