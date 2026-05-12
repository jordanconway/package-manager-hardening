<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# GitHub Actions Security Best Practices

GitHub Actions workflows are a high-value target for supply chain attacks. A compromised workflow runs in a trusted environment with access to repository secrets, deployment credentials, and the ability to push code or publish packages. The controls below are complementary to the per-ecosystem lockfile and version pinning practices in this repo.

## Pin actions to commit SHAs

Action version tags (`@v4`, `@main`) are mutable. A repository owner — or an attacker who compromises one — can move a tag to point to different, malicious code after you have reviewed and adopted it. Commit SHAs are immutable: a SHA always refers to exactly the code that was published at that point.

```yaml
# Bad — tag can be silently moved to malicious code
- uses: actions/checkout@v4

# Good — SHA is immutable; tag comment explains what version this is
- uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4
```

Keep the version tag in a comment next to the SHA so it is still human-readable and so Dependabot can propose updates. Dependabot supports SHA-pinned actions and will open a PR updating both the SHA and the comment when a new version is released.

To resolve the commit SHA for a tag without cloning the repo:

```bash
git ls-remote https://github.com/actions/checkout.git refs/tags/v4 'refs/tags/v4^{}'
# The ^{} line is the dereferenced commit SHA for annotated tags — use that one
```

## Least-privilege permissions

By default, GitHub grants the `GITHUB_TOKEN` broad permissions that vary by organisation settings. Always declare `permissions:` explicitly at the workflow level to set a safe baseline, then grant additional permissions at the job level only where needed.

```yaml
# Workflow-level baseline — read-only across the board
permissions:
  contents: read

jobs:
  release:
    # Override only what this job needs
    permissions:
      contents: write       # push a release tag
      packages: write       # push a container image
      id-token: write       # request an OIDC token
```

Common scopes and when they are needed:

| Scope | Minimum use case |
|---|---|
| `contents: read` | Checkout — sufficient for most CI jobs |
| `contents: write` | Push commits, create/update tags or releases |
| `packages: write` | Publish to GitHub Container Registry |
| `id-token: write` | OIDC authentication to cloud providers |
| `pull-requests: write` | Post or update comments on PRs |
| `issues: write` | Create or update issues |
| `checks: write` | Publish check run annotations |
| `security-events: write` | Upload SARIF results to the Security tab |

If a job does not need `secrets` access or elevated permissions, consider running it with `permissions: {}` (no permissions at all) to isolate it completely.

## Runtime egress control with Harden-Runner

See [harden-runner.md](harden-runner.md) for full configuration guidance. The short version: add `step-security/harden-runner` as the first step of every job, start in `audit` mode to discover what endpoints the job actually contacts, then tighten to `block` with an explicit allowlist.

```yaml
steps:
  - uses: step-security/harden-runner@6c3c2f2c1c457b00c10c4848d6f5491db3b629df # v2
    with:
      egress-policy: block
      disable-sudo: true
      allowed-endpoints: >
        api.github.com:443
        github.com:443
        objects.githubusercontent.com:443
        pypi.org:443
        files.pythonhosted.org:443
```

Jobs that reach arbitrary external URLs (link checkers, scanners) cannot use `block` mode — use `audit` and review the logs periodically.

## Pin tool installs in CI steps

Workflow steps that run `pip install <tool>`, `npm install -g <tool>`, or `npx <tool>` are subject to the same supply chain risks as application dependencies. Pin the version explicitly:

```yaml
# Bad
- run: pip install ruff

# Good
- run: pip install ruff==0.11.2
```

For a more robust setup, use a lockfile committed to the repo and install from it:

```yaml
- run: pip install -r ci-requirements.txt  # generated with pip-compile --generate-hashes
```

`npx --yes <package>` fetches and runs whatever is currently published under that name. Prefer a pinned local install:

```yaml
# Bad
- run: npx --yes markdownlint-cli2 "**/*.md"

# Better — installs a pinned version, then runs it
- run: |
    npm install markdownlint-cli2@0.17.0
    npx markdownlint-cli2 "**/*.md"
```

## Don't use `pull_request_target` without careful review

`pull_request_target` runs in the context of the base branch (with write permissions and access to secrets) even when triggered by a PR from a fork. This is intentionally powerful but dangerous: if the workflow checks out the fork's code and runs it, an attacker can exfiltrate secrets via a malicious PR.

Use `pull_request` for code that runs untrusted contributor code. Only use `pull_request_target` if you need write access or secrets, and ensure you never run code from the PR head in that context.

## Prevent expression injection

Workflow expressions like `${{ github.event.issue.title }}` or `${{ github.head_ref }}` are substituted as literal strings before the shell interprets the command. An attacker who controls the issue title, branch name, or PR body can inject shell commands:

```yaml
# Vulnerable — attacker controls github.head_ref
- run: echo "Branch: ${{ github.head_ref }}"

# Safe — pass through an environment variable; the shell never interprets the expression
- env:
    BRANCH: ${{ github.head_ref }}
  run: echo "Branch: $BRANCH"
```

Always pass untrusted context values (event inputs, issue/PR metadata, user-controlled strings) through environment variables rather than interpolating them directly into `run:` blocks.

## Restrict `workflow_dispatch` inputs

Workflows with `workflow_dispatch` inputs can be triggered manually with arbitrary input values. Validate inputs before using them:

```yaml
on:
  workflow_dispatch:
    inputs:
      environment:
        type: choice
        options: [staging, production]   # constrained to known values
```

Avoid free-form string inputs where possible; use `choice` or `boolean` types.

## Use OIDC instead of long-lived credentials

For deployments to AWS, GCP, Azure, or other cloud providers, use OpenID Connect (OIDC) token exchange rather than storing long-lived API keys as secrets. OIDC tokens are short-lived, scoped to a specific workflow run, and automatically rotated:

```yaml
permissions:
  id-token: write
  contents: read

steps:
  - uses: aws-actions/configure-aws-credentials@...
    with:
      role-to-assume: arn:aws:iam::123456789012:role/MyRole
      aws-region: us-east-1
```

Long-lived credentials stored as secrets are valid indefinitely if leaked. OIDC tokens expire in minutes.

## Protect workflow files with CODEOWNERS

Workflow files define what runs in CI and have access to all repository secrets. Require review from a specific team before any change to `.github/workflows/` is merged:

```text
# .github/CODEOWNERS
.github/workflows/ @your-org/security-team
```

Without CODEOWNERS, a contributor with write access to a branch can add a malicious step to a workflow and merge it without additional review.

## Disable credential persistence in checkouts

By default, `actions/checkout` writes the `GITHUB_TOKEN` into `.git/config` after fetching, so subsequent steps in the same job can `git push` or otherwise use the token. Any compromised dependency build, lint plugin, or post-install script in a later step can then exfiltrate or abuse it. Unless the job genuinely needs to push back to the repo (release tagging, automated commits), set `persist-credentials: false` on every checkout:

```yaml
# Default — token is left in .git/config for the rest of the job
- uses: actions/checkout@<sha> # v4

# Safe — token is wiped after the fetch completes
- uses: actions/checkout@<sha> # v4
  with:
    persist-credentials: false
```

This is one of zizmor's most common findings (`artipacked`).

## Cancel superseded runs (concurrency)

Without a workflow-level `concurrency:` block, rapid pushes to the same PR or branch stack overlapping runs. They burn Actions minutes, can create races between deploy jobs, and amplify the blast radius of a compromised dependency (more concurrent runs = more secret-bearing processes alive at once). Add:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

For release / deploy workflows where in-flight runs should complete, set `cancel-in-progress: false` instead, but always set the `group`.

## Pin the runner image

`runs-on: ubuntu-latest` is a moving target. GitHub rolls it forward when a new Ubuntu LTS reaches general availability, and has historically changed pre-installed tool versions silently mid-lifecycle. Builds that worked yesterday can fail or, worse, succeed against a different toolchain than you expected. Pin to a specific runner image:

```yaml
# Bad
runs-on: ubuntu-latest

# Good
runs-on: ubuntu-24.04
```

The same applies to `windows-latest` and `macos-latest`. Bump explicitly when a new image is GA and you've validated your matrix against it. Dependabot does not propose runner-image bumps, so add a calendar reminder or track it in your dependency-review process.

## Block vulnerable / disallowed dependencies on PRs

[`actions/dependency-review-action`](https://github.com/actions/dependency-review-action) compares the PR head against the base branch and fails the check if the diff introduces:

- A dependency with a known vulnerability at or above the configured severity
- A package on a denylist (e.g. known-malicious or internal-fork-required packages)
- A license on a denylist (e.g. copyleft licenses incompatible with your project)

It's PR-only, free, and requires no infrastructure. It also writes a summary comment on the PR describing what changed.

```yaml
  dependency-review:
    name: Dependency review
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-24.04
    permissions:
      contents: read
      pull-requests: write  # for the summary comment
    steps:
      - uses: step-security/harden-runner@<sha> # v2
        with:
          egress-policy: block
          disable-sudo: true
          allowed-endpoints: >
            api.github.com:443
            github.com:443
            objects.githubusercontent.com:443
      - uses: actions/checkout@<sha> # v4
        with:
          persist-credentials: false
      - uses: actions/dependency-review-action@<sha> # v4
        with:
          fail-on-severity: high
          comment-summary-in-pr: on-failure
          deny-licenses: GPL-2.0, GPL-3.0, AGPL-1.0, AGPL-3.0
```

Make the job a required status check on `main` so it cannot be merged around. Tune `fail-on-severity` (`critical | high | moderate | low`) to your project's risk tolerance.

**Prerequisite**: `dependency-review-action` requires Dependabot security updates to be enabled on the repo (not just the always-on dependency graph). Without it, every run fails with `Dependency review is not supported on this repository. Please ensure that Dependency graph is enabled`. Enable via Settings → Code security → "Dependabot security updates", or:

```bash
gh api -X PATCH repos/<owner>/<repo> \
  -f 'security_and_analysis[dependabot_security_updates][status]=enabled'
```

This is free for public repos and included with GitHub Advanced Security for private repos.

## OpenSSF Scorecard

[OpenSSF Scorecard](https://github.com/ossf/scorecard) automatically scores a repository against ~20 supply-chain best practices (branch protection, signed releases, pinned dependencies, token permissions, fuzzing, vulnerability response, etc.) and uploads results as SARIF to the Security tab. The score is the de-facto external benchmark and a Scorecard badge is now common on hardened OSS projects.

Add it as a separate workflow file (not an additional job in `ci.yml`), so the schedule + permissions stay isolated:

```yaml
# .github/workflows/scorecard.yml
name: Scorecard
on:
  branch_protection_rule:
  schedule:
    - cron: "37 5 * * 1"
  push:
    branches: [main]
permissions: {}
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
jobs:
  analysis:
    runs-on: ubuntu-24.04
    permissions:
      security-events: write  # SARIF upload
      id-token: write         # publish results to OpenSSF (badge)
      contents: read
      actions: read
    steps:
      - uses: step-security/harden-runner@<sha> # v2
        with:
          egress-policy: audit  # scorecard hits many endpoints; block is impractical
          disable-sudo: true
      - uses: actions/checkout@<sha> # v4
        with:
          persist-credentials: false
      - uses: ossf/scorecard-action@<sha> # v2
        with:
          results_file: results.sarif
          results_format: sarif
          publish_results: true
      - uses: github/codeql-action/upload-sarif@<sha> # v3
        with:
          sarif_file: results.sarif
```

Add the badge to your README so the score is publicly visible:

```markdown
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/<owner>/<repo>/badge)](https://scorecard.dev/viewer/?uri=github.com/<owner>/<repo>)
```

Scorecard's `egress-policy` must be `audit`, not `block` — the analyser legitimately contacts dozens of endpoints (deps.dev, OSV, npm, PyPI, etc.) to score your project against the ecosystem.

## SECURITY.md and private vulnerability reporting

Every repository should have a `SECURITY.md` at the root, and should enable GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability) under Settings → Code security. Together they give security researchers a clearly documented, non-public channel to disclose vulnerabilities, with a built-in workflow for coordinated disclosure, CVE assignment, and patch publication.

Minimum `SECURITY.md` content:

- A link to the "Report a vulnerability" form at `https://github.com/<owner>/<repo>/security/advisories/new`
- An explicit "do not file public issues" line
- What to include in a report (repro, affected versions, impact)
- Response-time expectations (acknowledgement and patch SLOs)
- Scope (what is and isn't covered)

Without this, researchers either file public issues (worst case) or never report at all.

## Static analysis with zizmor

[`zizmor`](https://docs.zizmor.sh) is a static analyser for GitHub Actions workflows. It catches the issues described above plus dozens more (template injection, unpinned actions, dangerous triggers, missing `permissions:`, mutable reusable-workflow refs, secrets exposed to forks, and so on). Run it locally and in CI:

```bash
# Local
uvx zizmor .                              # default persona, medium+ findings
uvx zizmor --persona=auditor .            # adds informational + low findings
```

In CI, install via `astral-sh/setup-uv` (already SHA-pinned for the Python jobs) and pin the zizmor version:

```yaml
  zizmor:
    name: GitHub Actions security (zizmor)
    runs-on: ubuntu-24.04
    permissions:
      contents: read
    steps:
      - uses: step-security/harden-runner@<sha> # v2
        with:
          egress-policy: block
          disable-sudo: true
          allowed-endpoints: >
            api.github.com:443
            github.com:443
            objects.githubusercontent.com:443
            pypi.org:443
            files.pythonhosted.org:443
            astral.sh:443
            release-assets.githubusercontent.com:443
            raw.githubusercontent.com:443
      - uses: actions/checkout@<sha> # v4
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@<sha> # v8.x
        with:
          version: "0.11.11"
      - run: uvx zizmor==1.24.1 --min-severity=medium .
```

Move the zizmor pin into `pyproject.toml [dependency-groups].dev` if you want Dependabot's `uv` ecosystem to keep it current automatically. `--min-severity=medium` mirrors the default persona's threshold; raise to `--persona=auditor --min-severity=low` for a stricter gate.

## Dependabot for action updates

Configure Dependabot to keep action SHAs and version comments current:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 7
      # Note: semver-*-days keys are unreliable for the github-actions
      # ecosystem because action tags (v4, v4.1.2) aren't always parsed
      # as SemVer by Dependabot. Rely on default-days, which always applies.
```

Dependabot understands SHA-pinned actions and will propose updates with both the new SHA and the updated version comment.

## Summary checklist

| Control | How |
|---|---|
| Pin actions to SHAs | `uses: owner/action@<full-sha> # vX` |
| Pin runner images | `runs-on: ubuntu-24.04`, never `ubuntu-latest` |
| Least-privilege token | `permissions: contents: read` at workflow level |
| Runtime egress control | `step-security/harden-runner` on every job |
| Pin tool installs | `pip install tool==x.y.z`, not bare `pip install tool` |
| Disable credential persistence | `with: persist-credentials: false` on every `actions/checkout` |
| Cancel superseded runs | `concurrency: { group: ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress: true }` |
| Block vulnerable PR deps | `actions/dependency-review-action` as required check on PRs |
| External posture scoring | `ossf/scorecard-action` weekly + on push to main, with badge |
| Vulnerability disclosure | `SECURITY.md` + GitHub private vulnerability reporting enabled |
| Static analysis | `zizmor` job in CI; SHA-pinned, `--min-severity=medium` |
| Avoid `pull_request_target` | Use `pull_request` unless write access is explicitly needed |
| Prevent expression injection | Pass untrusted values via `env:`, not `${{ }}` in `run:` |
| OIDC for cloud auth | `id-token: write` + federated identity; no long-lived keys |
| Protect workflow files | `.github/CODEOWNERS` pointing to a security team |
| Keep actions current | Dependabot `github-actions` ecosystem with cooldown |
