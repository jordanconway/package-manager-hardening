<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Helm

**Configuration files:** `Chart.yaml`, `Chart.lock`, `values.yaml`, `requirements.yaml` (Helm 2 only — deprecated)

Helm charts pull subchart dependencies from HTTP chart repositories or OCI registries. Both transports use SemVer ranges by default, both are subject to maintainer-account compromise, and the registry layer is largely unauthenticated unless you opt in to provenance/signature verification. The hardening story is similar to npm/Cargo: pin exactly, commit a lockfile, enforce it in CI, and verify provenance where possible.

Helm's tooling story is also weaker than most ecosystems on this list: there is **no native minimum-release-age / cooldown** support, and **Dependabot does not manage Helm chart dependencies**. Renovate is currently the only off-the-shelf option for cooldowns on Helm charts.

## Chart.lock

Running `helm dependency update` resolves `Chart.yaml` `dependencies[].version` ranges, downloads the matching chart archives into `charts/`, and writes `Chart.lock` containing each dependency's resolved version, repository URL, and SHA256 `digest`.

```yaml
# Chart.lock (generated)
dependencies:
- name: postgresql
  repository: https://charts.bitnami.com/bitnami
  version: 15.5.20
- name: redis
  repository: oci://registry-1.docker.io/bitnamicharts
  version: 20.6.2
digest: sha256:8f5c3...
generated: "2026-01-15T10:32:14.123456789Z"
```

**Always commit `Chart.lock`.** It is the only artefact that records the exact subchart versions and digests your chart was built and tested against.

In CI, use `helm dependency build` (not `helm dependency update`):

| Command | Reads | Writes | Behaviour |
|---------|-------|--------|-----------|
| `helm dependency update` | `Chart.yaml` | `Chart.lock`, `charts/` | Re-resolves ranges; **silently updates** to newer versions allowed by the range |
| `helm dependency build` | `Chart.lock` | `charts/` | Installs strictly from `Chart.lock`; **fails** if `Chart.lock` is missing or out of sync with `Chart.yaml` |

This mirrors the `npm install` vs `npm ci` distinction. CI must use `build`.

```bash
helm dependency build           # CI: lockfile-strict
helm dependency update          # local: regenerate Chart.lock when changing deps
```

## Version Pinning

In `Chart.yaml`, use exact versions for every dependency. Avoid `^`, `~`, `>=`, and bare major/minor strings:

```yaml
# Chart.yaml
apiVersion: v2
name: my-app
version: 1.0.0

dependencies:
  - name: postgresql
    version: 15.5.20                     # exact pin
    repository: https://charts.bitnami.com/bitnami

  - name: redis
    version: 20.6.2                      # exact pin
    repository: oci://registry-1.docker.io/bitnamicharts

  # incorrect — do not use
  # - name: postgresql
  #   version: ^15.5.0
  #   version: ~15.5
  #   version: ">=15.0.0"
  #   version: 15.x.x
```

Range specifiers in `Chart.yaml` are resolved by `helm dependency update` and the resolved version is captured in `Chart.lock`. The lockfile protects subsequent `helm dependency build` runs, but anyone running `update` will silently pull the latest matching version. Exact pins eliminate that ambiguity.

## Repository and Registry Pinning

### HTTP chart repositories

`helm repo add` registers a remote `index.yaml`. The repo URL is referenced from `Chart.yaml` `dependencies[].repository`. Only add repositories from sources you trust, and prefer HTTPS URLs operated by the upstream project.

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
```

### OCI registries

OCI is the recommended transport for new charts. Reference charts using the `oci://` scheme; pull-by-digest is supported and should be preferred where the registry exposes it:

```bash
# Pull by tag (mutable — tag can be re-pushed)
helm pull oci://registry-1.docker.io/bitnamicharts/redis --version 20.6.2

# Pull by digest (immutable — strongest integrity guarantee)
helm pull oci://registry-1.docker.io/bitnamicharts/redis@sha256:abc123...
```

Digest references in `Chart.yaml` `dependencies[].version` are not currently supported by Helm itself; the digest is recorded in `Chart.lock` after `helm dependency update`. Treat the digest in `Chart.lock` as authoritative and review changes to it during code review the same way you would review a lockfile diff for any other ecosystem.

## Provenance and Signature Verification

### Provenance files (PGP)

Helm supports PGP-signed `.prov` files alongside chart archives. Use `--verify` to require a valid signature:

```bash
helm install my-release ./mychart-1.0.0.tgz --verify --keyring ~/.gnupg/pubring.kbx
helm pull oci://registry.example.com/charts/mychart --version 1.0.0 --verify
```

`--verify` fails the install/pull if no `.prov` file is present or the signature does not match a key in the keyring. Coverage is uneven — many public charts are not signed — so this is most useful for first-party charts you publish yourself.

### Sigstore / cosign for OCI charts

For OCI-distributed charts, use cosign keyless signing (the same workflow used for container images, covered in [docker.md](docker.md)):

```bash
# Signing (publisher side)
cosign sign registry.example.com/charts/mychart:1.0.0

# Verification (consumer side)
cosign verify registry.example.com/charts/mychart:1.0.0 \
  --certificate-identity-regexp 'https://github.com/myorg/.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

This works because OCI Helm charts are stored as OCI artefacts and inherit the same signing/verification flow as container images.

## Security: Minimum Release Age

Helm has **no native cooldown support**. Options, in order of preference:

1. **Renovate** with a `minimumReleaseAge` rule (see below) — the only tool that natively understands Helm chart deps and supports cooldowns.
2. **Manual review** of `Chart.lock` diffs against publication timestamps in the chart repository's `index.yaml` (`created:` field) or OCI registry metadata.
3. **Internal mirror** that withholds new versions until they have aged out — same approach used for Go modules behind a private proxy.

Dependabot **does not support Helm chart dependencies** as of early 2026. It supports `helm` only insofar as a `helm-values` ecosystem exists for image tags inside `values.yaml`, which is unrelated to chart dependency cooldowns.

## Renovate Configuration

Renovate has first-class Helm support across `Chart.yaml` chart dependencies, `values.yaml` image tags, and `helmfile.yaml` releases.

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended"],
  "helm-values": { "enabled": true },
  "helmfile": { "enabled": true },
  "packageRules": [
    {
      "description": "7-day cooldown on all Helm chart updates",
      "matchManagers": ["helmv3", "helm-values", "helmfile"],
      "minimumReleaseAge": "7 days"
    },
    {
      "description": "30-day cooldown on Helm chart major updates",
      "matchManagers": ["helmv3", "helmfile"],
      "matchUpdateTypes": ["major"],
      "minimumReleaseAge": "30 days"
    },
    {
      "description": "Security advisories bypass cooldown",
      "matchPackageNames": ["*"],
      "matchUpdateTypes": ["patch"],
      "vulnerabilityAlerts": {
        "minimumReleaseAge": "0 days"
      }
    }
  ],
  "vulnerabilityAlerts": {
    "enabled": true,
    "minimumReleaseAge": "0 days"
  }
}
```

Key Renovate managers relevant to Helm:

| Manager | What it updates |
|---------|------------------|
| `helmv3` | `Chart.yaml` `dependencies[].version` (subchart deps) |
| `helm-values` | image tags inside `values.yaml` |
| `helmfile` | `helmfile.yaml` release versions |
| `helm-requirements` | legacy Helm 2 `requirements.yaml` |

`minimumReleaseAge` is enforced against the chart's publication timestamp in the source repository or OCI registry.

## Plugin Hygiene

`helm plugin install <url>` clones a repository and runs its `install` hook — arbitrary code execution by design. Treat plugin installs the same way you treat npm postinstall scripts:

- Pin plugin versions explicitly (`--version` flag) rather than tracking the default branch.
- Vendor or mirror trusted plugins; do not install plugins from arbitrary URLs in CI.
- Audit `~/.local/share/helm/plugins/` (or `$HELM_PLUGINS`) periodically.

```bash
helm plugin install https://github.com/databus23/helm-diff --version v3.9.11
helm plugin list
```

## CI Recommended Configuration

```bash
# CI commands
helm dependency build                                    # strict, fails if Chart.lock stale
helm lint .
helm template . --values values.yaml > /dev/null         # render-only sanity check
helm package . --version "$VERSION" --app-version "$APP_VERSION"

# Optional: verify subchart provenance if .prov files are published
helm dependency build --verify --keyring ./trusted-keys.kbx
```

For Harden-Runner allowed-endpoints, include the chart repositories you depend on, e.g.:

```yaml
allowed-endpoints: >
  api.github.com:443
  github.com:443
  charts.bitnami.com:443
  registry-1.docker.io:443
  ghcr.io:443
  get.helm.sh:443
```

## Helmfile

[Helmfile](https://github.com/helmfile/helmfile) declares releases across multiple charts. Pin every release to an exact `version`, and commit any generated lockfiles (`helmfile.lock` when using `helmfile deps`):

```yaml
# helmfile.yaml
repositories:
  - name: bitnami
    url: https://charts.bitnami.com/bitnami

releases:
  - name: postgres
    namespace: data
    chart: bitnami/postgresql
    version: 15.5.20                  # exact pin
  - name: redis
    namespace: cache
    chart: oci://registry-1.docker.io/bitnamicharts/redis
    version: 20.6.2                   # exact pin
```

```bash
helmfile deps                         # update helmfile.lock
helmfile --file helmfile.yaml apply   # apply with locked versions
```

---
