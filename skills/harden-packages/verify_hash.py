#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Linux Foundation
# SPDX-License-Identifier: MIT
"""
verify_hash.py — resolve and verify hashes / digests / SHAs from authoritative
upstream sources so AI agents never have to fabricate them.

Default output: a single line with just the hash, suitable for shell capture:

    SHA=$(python verify_hash.py gh-action actions/checkout v4)

With --json, prints a structured object with extra metadata.

Exit codes:
    0  success (hash printed)
    1  upstream lookup failed (not found, version doesn't exist, network)
    2  usage error
    3  required external tool missing (only for subcommands that need one)

No third-party Python dependencies. Uses urllib for HTTP and shells out only
where there's no plain HTTP API (git, docker/crane/skopeo, go).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any, NoReturn

UA = "verify-hash/1.0 (+https://github.com/linuxfoundation/package-manager-hardening)"
TIMEOUT = 20


# ---------- helpers ----------------------------------------------------------

def _die(msg: str, code: int = 1) -> NoReturn:
    print(f"verify-hash: {msg}", file=sys.stderr)
    sys.exit(code)


def _http_json(url: str, headers: dict[str, str] | None = None) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        _die(f"HTTP {e.code} from {url}")
    except urllib.error.URLError as e:
        _die(f"network error fetching {url}: {e.reason}")


def _http_text(url: str, headers: dict[str, str] | None = None) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8").strip()
    except urllib.error.HTTPError as e:
        _die(f"HTTP {e.code} from {url}")
    except urllib.error.URLError as e:
        _die(f"network error fetching {url}: {e.reason}")


def _emit(value: str, extra: dict[str, Any] | None, as_json: bool) -> None:
    if as_json:
        out = {"hash": value}
        if extra:
            out.update(extra)
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(value)


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=TIMEOUT).stdout.strip()
    except FileNotFoundError:
        _die(f"required tool not found: {cmd[0]}", 3)
    except subprocess.CalledProcessError as e:
        _die(f"{cmd[0]} failed: {e.stderr.strip() or e.stdout.strip()}")


def _gh_headers() -> dict[str, str]:
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


# ---------- subcommands ------------------------------------------------------

def cmd_gh_action(args: argparse.Namespace) -> None:
    """Resolve a GitHub repo tag/branch/SHA to a full 40-char commit SHA."""
    if "/" not in args.repo:
        _die("repo must be OWNER/NAME", 2)
    data = _http_json(f"https://api.github.com/repos/{args.repo}/commits/{args.ref}", _gh_headers())
    sha = data.get("sha")
    if not sha or len(sha) != 40:
        _die(f"unexpected API response: {data!r}")
    _emit(sha, {
        "repo": args.repo,
        "ref": args.ref,
        "date": data.get("commit", {}).get("committer", {}).get("date"),
        "message": (data.get("commit", {}).get("message", "") or "").splitlines()[0],
    }, args.json)


def cmd_git_ref(args: argparse.Namespace) -> None:
    """Resolve a tag/branch to a commit SHA in any git remote (works for non-GitHub)."""
    if not shutil.which("git"):
        _die("git not installed", 3)
    # Try annotated-tag dereference first, then plain ref.
    out = _run([
        "git", "ls-remote", args.url,
        f"refs/tags/{args.ref}^{{}}",
        f"refs/tags/{args.ref}",
        f"refs/heads/{args.ref}",
        args.ref,
    ])
    if not out:
        _die(f"ref {args.ref!r} not found in {args.url}")
    # Prefer the ^{} line (annotated-tag dereference) if present.
    chosen = None
    for line in out.splitlines():
        sha, _, ref = line.partition("\t")
        if ref.endswith("^{}"):
            chosen = sha
            break
    if not chosen:
        chosen = out.splitlines()[0].split("\t", 1)[0]
    _emit(chosen, {"url": args.url, "ref": args.ref}, args.json)


def cmd_oci(args: argparse.Namespace) -> None:
    """Resolve an OCI image tag to an immutable sha256 digest."""
    ref = args.image
    if "@sha256:" in ref:
        # Already a digest — verify it exists by re-resolving.
        pass
    # Prefer crane (fastest, no Docker daemon), then skopeo, then docker buildx.
    if shutil.which("crane"):
        digest = _run(["crane", "digest", ref])
    elif shutil.which("skopeo"):
        digest = _run(["skopeo", "inspect", f"docker://{ref}", "--format", "{{.Digest}}"])
    elif shutil.which("docker"):
        out = _run(["docker", "buildx", "imagetools", "inspect", ref, "--format", "{{json .Manifest}}"])
        digest = json.loads(out).get("digest", "")
    else:
        _die("need one of: crane, skopeo, or docker (with buildx) to resolve OCI digests", 3)
    if not digest.startswith("sha256:"):
        _die(f"unexpected digest format: {digest!r}")
    _emit(digest, {"image": ref}, args.json)


def cmd_pypi(args: argparse.Namespace) -> None:
    """Return SHA256(s) for a PyPI release. Defaults to all artifacts; --wheel/--sdist filter."""
    data = _http_json(f"https://pypi.org/pypi/{args.package}/{args.version}/json")
    urls = data.get("urls") or []
    if not urls:
        _die(f"no artifacts for {args.package}=={args.version}")
    rows = []
    for u in urls:
        ptype = u.get("packagetype")
        if args.wheel and ptype != "bdist_wheel":
            continue
        if args.sdist and ptype != "sdist":
            continue
        rows.append({"filename": u["filename"], "packagetype": ptype, "sha256": u["digests"]["sha256"]})
    if not rows:
        _die("no artifacts matched the filter")
    if args.json:
        print(json.dumps({"package": args.package, "version": args.version, "artifacts": rows}, indent=2))
    elif len(rows) == 1:
        print(rows[0]["sha256"])
    else:
        for r in rows:
            print(f"{r['sha256']}  {r['filename']}")


def cmd_npm(args: argparse.Namespace) -> None:
    """Return the SRI integrity string and tarball SHA1 for a published npm version."""
    pkg = args.package.replace("/", "%2F") if args.package.startswith("@") else args.package
    data = _http_json(f"https://registry.npmjs.org/{pkg}/{args.version}")
    dist = data.get("dist") or {}
    integrity = dist.get("integrity")
    if not integrity:
        _die(f"no dist.integrity for {args.package}@{args.version}")
    _emit(integrity, {
        "package": args.package,
        "version": args.version,
        "tarball": dist.get("tarball"),
        "shasum": dist.get("shasum"),
    }, args.json)


def cmd_crate(args: argparse.Namespace) -> None:
    """Return the SHA256 checksum that crates.io publishes for a crate version."""
    data = _http_json(f"https://crates.io/api/v1/crates/{args.crate}/{args.version}", {"Accept": "application/json"})
    ver = data.get("version") or {}
    checksum = ver.get("checksum")
    if not checksum:
        _die(f"no checksum for {args.crate} {args.version}")
    _emit(checksum, {"crate": args.crate, "version": args.version, "yanked": ver.get("yanked")}, args.json)


def cmd_gem(args: argparse.Namespace) -> None:
    """Return the SHA256 for a published RubyGems version."""
    data = _http_json(f"https://rubygems.org/api/v2/rubygems/{args.gem}/versions/{args.version}.json")
    sha = data.get("sha")
    if not sha:
        _die(f"no sha for {args.gem} {args.version}")
    _emit(sha, {"gem": args.gem, "version": args.version, "platform": data.get("platform")}, args.json)


def cmd_packagist(args: argparse.Namespace) -> None:
    """Return dist.shasum + dist.reference for a published Composer package version."""
    if "/" not in args.package:
        _die("package must be VENDOR/NAME", 2)
    data = _http_json(f"https://repo.packagist.org/p2/{args.package}.json")
    versions = (data.get("packages") or {}).get(args.package) or []
    match = next((v for v in versions if v.get("version") == args.version), None)
    if not match:
        _die(f"version {args.version} not found for {args.package}")
    dist = match.get("dist") or {}
    src = match.get("source") or {}
    primary = dist.get("shasum") or src.get("reference")
    if not primary:
        _die("no dist.shasum or source.reference")
    _emit(primary, {
        "package": args.package,
        "version": args.version,
        "dist_url": dist.get("url"),
        "source_reference": src.get("reference"),
    }, args.json)


def cmd_gradle_dist(args: argparse.Namespace) -> None:
    """Return the official SHA256 for a Gradle wrapper distribution."""
    kind = args.kind  # bin or all
    sha = _http_text(f"https://services.gradle.org/distributions/gradle-{args.version}-{kind}.zip.sha256")
    if len(sha) != 64:
        _die(f"unexpected checksum length: {sha!r}")
    _emit(sha, {"version": args.version, "kind": kind}, args.json)


def cmd_maven(args: argparse.Namespace) -> None:
    """Return the SHA-256 (or SHA-1 fallback) for a Maven Central artifact."""
    parts = args.gav.split(":")
    if len(parts) != 3:
        _die("gav must be GROUP:ARTIFACT:VERSION", 2)
    group, artifact, version = parts
    group_path = group.replace(".", "/")
    base = (
        f"https://repo1.maven.org/maven2/{group_path}/{artifact}/"
        f"{version}/{artifact}-{version}.{args.ext}"
    )
    # Try sha256 first, then sha1.
    for algo in ("sha256", "sha1"):
        try:
            sha = _http_text(base + f".{algo}")
            sha = sha.split()[0]  # files often "<hash>  <filename>"
            _emit(sha, {"gav": args.gav, "extension": args.ext, "algorithm": algo, "url": base + f".{algo}"}, args.json)
            return
        except SystemExit:
            continue
    _die(f"no sha256/sha1 sibling found at {base}")


def cmd_tf_provider(args: argparse.Namespace) -> None:
    """List or verify a Terraform / OpenTofu provider version on the registry."""
    registry = "registry.opentofu.org" if args.opentofu else "registry.terraform.io"
    if "/" not in args.provider:
        _die("provider must be NAMESPACE/NAME", 2)
    data = _http_json(f"https://{registry}/v1/providers/{args.provider}/versions")
    versions = [v["version"] for v in data.get("versions", [])]
    if not versions:
        _die(f"no versions found for {args.provider} on {registry}")
    if args.version:
        if args.version not in versions:
            _die(f"version {args.version} not found for {args.provider}")
        _emit(args.version, {"provider": args.provider, "registry": registry, "exists": True}, args.json)
        return
    if args.json:
        print(json.dumps({"provider": args.provider, "registry": registry, "versions": versions}, indent=2))
    else:
        for v in versions:
            print(v)


def cmd_go_module(args: argparse.Namespace) -> None:
    """Return go.sum-style hash for a Go module version via the module proxy."""
    # The proxy serves /<module>/@v/<version>.ziphash containing the h1: hash.
    mod = args.module.lower()  # proxy is case-folded
    ver = args.version
    url = f"https://proxy.golang.org/{mod}/@v/{ver}.ziphash"
    h1 = _http_text(url)
    if not h1.startswith("h1:"):
        _die(f"unexpected ziphash content: {h1!r}")
    _emit(h1, {"module": args.module, "version": args.version}, args.json)


# ---------- arg parser -------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="verify-hash",
        description="Resolve cryptographic hashes from authoritative upstream sources.",
    )
    p.add_argument("--json", action="store_true", help="emit JSON instead of bare hash")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("gh-action", help="resolve a GitHub tag/branch/SHA to a full commit SHA")
    s.add_argument("repo", help="OWNER/NAME")
    s.add_argument("ref", help="tag, branch, or short/long SHA")
    s.set_defaults(func=cmd_gh_action)

    s = sub.add_parser("git-ref", help="resolve a tag/branch on any git remote to a commit SHA")
    s.add_argument("url", help="git remote URL")
    s.add_argument("ref", help="tag or branch name")
    s.set_defaults(func=cmd_git_ref)

    s = sub.add_parser("oci", help="resolve an OCI image tag to an immutable sha256 digest")
    s.add_argument("image", help="IMAGE:TAG (or IMAGE@sha256:... to re-verify)")
    s.set_defaults(func=cmd_oci)

    s = sub.add_parser("pypi", help="return SHA256 for a PyPI release")
    s.add_argument("package")
    s.add_argument("version")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--wheel", action="store_true", help="only wheel artifacts")
    g.add_argument("--sdist", action="store_true", help="only sdist artifacts")
    s.set_defaults(func=cmd_pypi)

    s = sub.add_parser("npm", help="return SRI integrity for a published npm version")
    s.add_argument("package", help="package name (use @scope/name for scoped)")
    s.add_argument("version")
    s.set_defaults(func=cmd_npm)

    s = sub.add_parser("crate", help="return SHA256 for a crates.io version")
    s.add_argument("crate")
    s.add_argument("version")
    s.set_defaults(func=cmd_crate)

    s = sub.add_parser("gem", help="return SHA256 for a RubyGems version")
    s.add_argument("gem")
    s.add_argument("version")
    s.set_defaults(func=cmd_gem)

    s = sub.add_parser("packagist", help="return dist.shasum / source.reference for a Composer version")
    s.add_argument("package", help="VENDOR/NAME")
    s.add_argument("version")
    s.set_defaults(func=cmd_packagist)

    s = sub.add_parser("gradle-dist", help="return SHA256 of the official Gradle wrapper distribution")
    s.add_argument("version")
    s.add_argument("kind", nargs="?", default="bin", choices=("bin", "all"))
    s.set_defaults(func=cmd_gradle_dist)

    s = sub.add_parser("maven", help="return SHA256/SHA1 for a Maven Central artifact")
    s.add_argument("gav", help="GROUP:ARTIFACT:VERSION")
    s.add_argument("--ext", default="jar", help="artifact extension (default: jar)")
    s.set_defaults(func=cmd_maven)

    s = sub.add_parser("tf-provider", help="list / verify Terraform or OpenTofu provider versions")
    s.add_argument("provider", help="NAMESPACE/NAME (e.g. hashicorp/aws)")
    s.add_argument("version", nargs="?", help="if omitted, list all versions")
    s.add_argument("--opentofu", action="store_true", help="use the OpenTofu registry")
    s.set_defaults(func=cmd_tf_provider)

    s = sub.add_parser("go-module", help="return h1: hash for a Go module version via the proxy")
    s.add_argument("module", help="module path (e.g. github.com/foo/bar)")
    s.add_argument("version", help="e.g. v1.2.3")
    s.set_defaults(func=cmd_go_module)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
