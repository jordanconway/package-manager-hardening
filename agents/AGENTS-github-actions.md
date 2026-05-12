<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Agent Instructions: GitHub Actions Security

This file contains mandatory guidelines for working with GitHub Actions workflows in this repository. Follow these rules whenever adding, modifying, or reviewing files under `.github/workflows/`.

## Checkout: disable credential persistence

Every `actions/checkout` invocation must set `persist-credentials: false` unless the job genuinely needs to push back to the repo (release tagging, automated commits). The default leaves `GITHUB_TOKEN` in `.git/config` for the rest of the job, where any subsequent step — including a compromised dependency build — can use it.

```yaml
- uses: actions/checkout@<sha> # v4
  with:
    persist-credentials: false
```

If a job needs to push, override only in that job and document why in a YAML comment.

## Workflow concurrency

Every workflow must declare a top-level `concurrency:` block. For CI workflows (lint/test/build), cancel superseded runs:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

For release / deploy workflows where in-flight runs should complete, keep the `group:` but set `cancel-in-progress: false`.

## Static analysis: zizmor

Every repository must run [`zizmor`](https://docs.zizmor.sh) against `.github/workflows/` in CI as a required status check. zizmor catches the controls in this file plus many others (template injection, mutable reusable-workflow refs, dangerous triggers, secrets exposed to forks, etc.) and is the canonical static analyser for this domain.

Minimum gate: `--min-severity=medium` on the default persona. Stricter gate (preferred for security-sensitive repos): `--persona=auditor --min-severity=low`.

New or modified workflows must pass `uvx zizmor --persona=auditor .` locally before being committed. New zizmor findings must not be merged — either fix the underlying issue or, if it is a confirmed false positive, suppress it explicitly with a `# zizmor: ignore[<rule>]` comment plus a justification in the PR description.

Do not downgrade the `--min-severity` threshold or remove the zizmor job from CI without explicit human approval.

## Pin runner images

`runs-on: ubuntu-latest` is mutable and changes underneath you. Always pin to a specific image (`ubuntu-24.04`, `ubuntu-22.04`, `windows-2022`, `macos-14`). Bump explicitly when you've validated the new image. Dependabot does not propose runner-image bumps; track these manually.

## Block vulnerable / disallowed dependencies on PRs

Every repository must run `actions/dependency-review-action` as a PR-only required status check. It compares head against base and fails on:

- Vulnerabilities at or above `fail-on-severity: high` (or stricter)
- Licenses on the `deny-licenses` list (project-specific)
- Packages on the `deny-packages` list, if any

Do not lower `fail-on-severity` below `high` without explicit human approval. Do not delete the job or remove its required-check status without explicit human approval.

## OpenSSF Scorecard

Every repository must publish an OpenSSF Scorecard score via `ossf/scorecard-action`, run on a weekly schedule and on push to `main`. SARIF results upload to the Security tab; results publish to the OpenSSF API so the README badge resolves.

The Scorecard workflow uses `egress-policy: audit`, not `block` — the analyser legitimately contacts dozens of ecosystem endpoints. Do not change to `block`.

A dropping Scorecard score is a regression that must be triaged like any other CI failure. Common causes: a new unpinned action, a removed branch protection rule, a permission grant added without justification.

## Vulnerability disclosure: SECURITY.md

Every repository must have a root `SECURITY.md` linking to GitHub's private vulnerability reporting (`https://github.com/<owner>/<repo>/security/advisories/new`), with explicit "do not file public issues" wording, expected response SLOs, and scope. Private vulnerability reporting must be enabled in repo Settings → Code security → "Privately report a vulnerability".

## Action Version Pinning

**Always pin actions to their full commit SHA**, not to a version tag. Include the human-readable tag as a comment on the same line:

```yaml
# Correct
- uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4

# Incorrect — tag can be silently moved
- uses: actions/checkout@v4
```

To resolve the commit SHA for a tag:

```bash
git ls-remote https://github.com/<owner>/<action>.git refs/tags/<tag> 'refs/tags/<tag>^{}'
# Use the ^{} line (dereferenced SHA) for annotated tags
```

**Never add a new action that was published within the last 7 days.** Check the release date before adding any new action to a workflow.

## Workflow Permissions

Every workflow must declare `permissions:` at the workflow level with `contents: read` as the baseline. Grant elevated permissions at the job level only where explicitly required:

```yaml
# Workflow-level baseline
permissions:
  contents: read

jobs:
  deploy:
    permissions:
      contents: write   # only if this job pushes commits or creates releases
      id-token: write   # only if this job uses OIDC to authenticate to a cloud provider
```

Never leave `permissions:` undeclared — this relies on organisation defaults which vary.

## Harden-Runner

Every job that installs dependencies or runs build steps must include `step-security/harden-runner` as its **first step**:

```yaml
steps:
  - uses: step-security/harden-runner@<sha> # v2
    with:
      egress-policy: block
      disable-sudo: true
      allowed-endpoints: >
        api.github.com:443
        github.com:443
        objects.githubusercontent.com:443
```

Add ecosystem-specific endpoints as needed (e.g. `pypi.org:443 files.pythonhosted.org:443` for Python jobs, `registry.npmjs.org:443` for Node.js jobs).

For any action that downloads a binary from a GitHub release (e.g. `astral-sh/setup-uv`, `opentofu/setup-opentofu`), also allow `release-assets.githubusercontent.com:443` — modern GitHub release downloads redirect through that host. The older `github-production-release-asset-2e65be.s3.amazonaws.com` is deprecated and will fail with `ECONNREFUSED` in `block` mode.

Some actions also fetch a runtime version manifest from `raw.githubusercontent.com`. Notable case: `astral-sh/setup-uv` **v8+** reads `https://raw.githubusercontent.com/astral-sh/versions/main/v1/uv.ndjson` on every run; v6.x did not. A Dependabot bump that crosses this boundary will fail in `block` mode until `raw.githubusercontent.com:443` is added. Always re-validate the allowlist when an action crosses a major version.

**Exception:** jobs that fetch arbitrary external URLs (link checkers, scanners) must use `egress-policy: audit` since a fixed allowlist cannot be constructed. Add a comment explaining why.

Start new jobs in `audit` mode and tighten to `block` once the allowlist is confirmed from the audit logs.

## Tool Version Pinning

Pin all tool installs in CI steps to exact versions. Do not use bare installs:

```yaml
# Correct
- run: pip install ruff==0.11.2
- run: pip install pytest==8.3.5
- run: npm install markdownlint-cli2@0.17.2

# Incorrect
- run: pip install ruff
- run: npx --yes markdownlint-cli2
```

**Dependabot blind spot:** inline `pip install x==y` / `npm install x@y` lines in workflow files are pinned but **not parsed by Dependabot** — no ecosystem will open update PRs for them, and they silently rot. For tools used by CI, prefer declaring them in a manifest Dependabot understands (e.g. `pyproject.toml [dependency-groups]` for Python, `package.json` `devDependencies` for Node) and invoking via `uv run` / `npx` from the locked install. Inline pins are acceptable only as a short-term measure with a tracked follow-up.

## Expression Injection

Never interpolate untrusted context values directly into `run:` blocks. Pass them through environment variables:

```yaml
# Correct
- env:
    PR_TITLE: ${{ github.event.pull_request.title }}
  run: echo "$PR_TITLE"

# Incorrect — attacker-controlled input interpolated into shell
- run: echo "${{ github.event.pull_request.title }}"
```

Untrusted values include: `github.event.issue.title`, `github.head_ref`, `github.event.pull_request.body`, any `workflow_dispatch` input.

## `pull_request_target`

Do not use `pull_request_target` unless write access or secrets are explicitly required. If used, never check out or run code from the PR head branch in that context.

## What Requires Human Review

The following changes must not be made autonomously and require explicit human approval:

- Adding a new action not already present in an existing workflow
- Upgrading an action to a new major version
- Adding or modifying `secrets:` references
- Changing `egress-policy` from `block` to `audit`
- Adding `pull_request_target` triggers
- Granting any permission beyond `contents: read` at the workflow level
- Modifying the Dependabot configuration for the `github-actions` ecosystem
- Setting `persist-credentials: true` (or omitting it, which defaults to `true`) on `actions/checkout`
- Removing or weakening the workflow-level `concurrency:` block
- Removing the zizmor job, lowering its `--min-severity`, or suppressing a finding without a documented justification
- Removing the dependency-review job, lowering its `fail-on-severity`, or removing it from required status checks
- Removing the Scorecard workflow, or changing its `egress-policy` away from `audit`
- Bumping a runner image (`ubuntu-24.04` → `ubuntu-26.04`, etc.) without confirming the matrix still passes
- Removing or weakening `SECURITY.md` or disabling private vulnerability reporting
