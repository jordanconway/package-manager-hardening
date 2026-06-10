<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Agent Instructions: Helm Chart Dependency Management

This file contains mandatory guidelines for managing Helm chart dependencies in this project. Follow these rules whenever adding, updating, or removing chart dependencies, or modifying CI configuration.

## Hash Verification: Never Fabricate

**AI agents must never invent, guess, autocomplete, or extrapolate a `Chart.lock` digest, an OCI image digest, or any other cryptographic hash.** A fabricated digest either fails verification or silently pins to the wrong artifact.

All `Chart.lock` digests must be produced by Helm itself — run `helm dependency update` and commit the resulting `Chart.lock`. Do not hand-edit `digest:` fields.

For OCI image digests referenced in `values.yaml`:

**Preferred:** if the `harden-packages` skill is available, use its helper:

```bash
python {SKILL_DIR}/verify_hash.py oci <registry>/<image>:<tag>
```

**Fallback:** `crane digest <registry>/<image>:<tag>` or `docker buildx imagetools inspect <image>:<tag> --format '{{json .Manifest}}' | jq -r .digest`. For OCI-hosted charts, also `helm pull oci://<registry>/<chart> --version <ver>` and inspect the downloaded artifact.

If you cannot verify a digest with any of the above, **stop and ask the user**. Do not insert a placeholder or a "likely correct" value.

## Chart Names: Never Guess

**AI agents must never add a chart whose exact name and repository they have not verified in the current session.** A guessed chart name or repository URL either fails to resolve or resolves to a look-alike — chart identity is the pair (repository URL, chart name), not the name alone.

Before adding any new chart dependency:

1. Verify the chart on <https://artifacthub.io/> and confirm the publisher: prefer charts with the Verified Publisher and Official badges, and confirm the repository URL matches the project's documented one.
2. Treat as red flags: a repository URL differing from the documented one, a chart republished under an unfamiliar repository, and a very recent first release of a supposedly established chart.

If the lookup is ambiguous or the chart cannot be confidently identified, **stop and ask the user** — do not choose between similar charts on intuition.

## Dependency Rules

**Always pin exact chart versions** in `Chart.yaml`. Never use `^`, `~`, `>=`, `x` wildcards, or bare major/minor strings:

```yaml
# correct
dependencies:
  - name: postgresql
    version: 15.5.20
    repository: https://charts.bitnami.com/bitnami
  - name: redis
    version: 20.6.2
    repository: oci://registry-1.docker.io/bitnamicharts

# incorrect — do not use
dependencies:
  - name: postgresql
    version: ^15.5.0
  - name: postgresql
    version: 15.x.x
  - name: postgresql
    version: ">=15.0.0"
```

**Never add a chart version published within the last 7 days.** Helm has no native cooldown enforcement. Check the chart's publication date in the upstream repository's `index.yaml` (`created:` field) or OCI registry metadata before adding any new dependency. If the version was published less than 7 days ago, defer the addition until the cooldown has elapsed. Renovate (configured below) enforces this automatically.

**Always commit `Chart.lock`.** It records resolved versions, repository URLs, and SHA256 digests. Treat changes to digests in `Chart.lock` as security-relevant during review.

**When updating dependencies, use `helm dependency update` locally and review the `Chart.lock` diff before committing.** Do not run `update` in CI.

## Repositories and Registries

**Only add chart repositories you trust.** Do not run `helm repo add` against arbitrary third-party URLs. Prefer HTTPS repositories operated by the upstream project, or OCI registries.

**Prefer OCI references** for new dependencies. Where the OCI registry exposes digest references, prefer pull-by-digest over pull-by-tag.

## Provenance Verification

If the upstream chart publishes `.prov` files or cosign signatures, enable verification:

```bash
helm dependency build --verify --keyring ./trusted-keys.kbx
helm install my-release oci://registry.example.com/charts/mychart \
  --version 1.0.0 --verify
```

For OCI charts signed with cosign, verify before pulling into production:

```bash
cosign verify registry.example.com/charts/mychart:1.0.0 \
  --certificate-identity-regexp 'https://github.com/myorg/.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

## Plugin Rules

**Do not install Helm plugins in CI from arbitrary URLs.** `helm plugin install` runs install hooks (arbitrary code execution). Pin plugin versions explicitly with `--version`, and prefer vendored or mirrored plugins:

```bash
helm plugin install https://github.com/databus23/helm-diff --version v3.9.11
```

## CI Commands

CI must use `helm dependency build` (lockfile-strict), never `helm dependency update`:

```bash
helm dependency build                          # fails if Chart.lock is missing or stale
helm lint .
helm template . --values values.yaml > /dev/null
helm package . --version "$VERSION" --app-version "$APP_VERSION"
```

## CI Configuration

### Renovate (preferred for Helm)

Helm chart cooldowns are not supported by Dependabot. Use Renovate. `renovate.json` must include `minimumReleaseAge` rules for Helm managers. If the file does not exist or lacks Helm cooldown rules, add them:

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended"],
  "helm-values": { "enabled": true },
  "helmfile": { "enabled": true },
  "packageRules": [
    {
      "description": "7-day cooldown on all Helm updates",
      "matchManagers": ["helmv3", "helm-values", "helmfile"],
      "minimumReleaseAge": "7 days"
    },
    {
      "description": "30-day cooldown on Helm chart majors",
      "matchManagers": ["helmv3", "helmfile"],
      "matchUpdateTypes": ["major"],
      "minimumReleaseAge": "30 days"
    }
  ],
  "vulnerabilityAlerts": {
    "enabled": true,
    "minimumReleaseAge": "0 days"
  }
}
```

Vulnerability alerts bypass the cooldown automatically and should be reviewed and merged promptly.

### Dependabot (image tags only)

Dependabot does **not** manage Helm chart dependencies. It can manage container image tags referenced in `values.yaml` via the `docker` ecosystem if those values are wired through. Do not rely on Dependabot for chart updates.

### Harden-Runner

Every GitHub Actions workflow that fetches Helm charts must include `step-security/harden-runner` as its first step. New workflows must not be added without it. Allowed endpoints must include the chart repositories and OCI registries the project depends on:

```yaml
- uses: step-security/harden-runner@6c3c2f2c1c457b00c10c4848d6f5491db3b629df # v2
  with:
    egress-policy: block
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      get.helm.sh:443
      charts.bitnami.com:443
      registry-1.docker.io:443
      ghcr.io:443
```

Update the endpoint list when adding a chart from a new repository.

## Helmfile

If this project uses Helmfile, every release must pin an exact `version`, and `helmfile.lock` (when generated by `helmfile deps`) must be committed.

## What Requires Human Review

The following changes must not be made autonomously and require explicit human approval before proceeding:

- Adding a chart from a repository not previously used in the project
- Adding a `helm repo add` for a new third-party repository
- Upgrading a chart major version
- Changing exact pins to ranges (`^`, `~`, `>=`, wildcards)
- Disabling `--verify` where it was previously enabled
- Installing a new Helm plugin
- Modifying Renovate `minimumReleaseAge` values downward
- Removing or modifying Harden-Runner from a workflow
- Replacing `helm dependency build` with `helm dependency update` in CI
