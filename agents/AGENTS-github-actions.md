<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Agent Instructions: GitHub Actions Security

This file contains mandatory guidelines for working with GitHub Actions workflows in this repository. Follow these rules whenever adding, modifying, or reviewing files under `.github/workflows/`.

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
