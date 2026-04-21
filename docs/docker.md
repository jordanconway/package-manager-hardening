<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Container Images

Container images are a dependency like any other: an unpinned base image can silently pull in a different set of packages on every build, and an image from an unverified source can contain malicious code or known vulnerabilities before your application code even runs. The controls here focus on provenance, pinning, and scanning — the same concerns that apply to package managers.

## Base Image Pinning

Docker image tags are mutable. `FROM node:20` today and `FROM node:20` next month may resolve to entirely different layer contents. Pin base images to their immutable digest instead:

```dockerfile
# Mutable — do not use in production builds
FROM node:20

# Pinned to a specific digest — reproducible
FROM node:20@sha256:a1b2c3d4e5f6...
```

To find the current digest for an image:

```bash
docker buildx imagetools inspect node:20 --format '{{json .Manifest}}' | jq .digest
# or
docker pull node:20 && docker inspect node:20 --format '{{index .RepoDigests 0}}'
```

Record the tag alongside the digest in a comment so it remains human-readable:

```dockerfile
FROM node:20@sha256:a1b2c3d4e5f6...  # node:20 as of 2026-01-15
```

## Use Official and Verified Images

Prefer images from sources with strong provenance guarantees, in roughly this order:

- **Docker Official Images** — maintained by Docker, Inc. and vetted library authors, reviewed before publication. Identifiable by the short name with no namespace (e.g. `node`, `python`, `postgres`).
- **Docker Verified Publishers** — ISVs whose images are scanned and must meet Docker's publishing standards.
- **GitHub Container Registry (`ghcr.io`)** — images built by GitHub Actions workflows, with a direct audit trail to the source repository and workflow run.

Avoid images from arbitrary Docker Hub namespaces where build provenance is unknown.

## Minimal Base Images

Fewer packages in the base image means a smaller attack surface and fewer CVEs to manage. Prefer:

- **Distroless images** (`gcr.io/distroless/*`) — contain only the runtime and its direct dependencies, no shell, no package manager. See [GoogleContainerTools/distroless](https://github.com/GoogleContainerTools/distroless).
- **`-slim` variants** — official images offer `node:20-slim`, `python:3.12-slim` etc. that strip build tools and documentation from the full image.
- **Alpine-based images** — very small footprint, though musl libc can cause compatibility issues with some native extensions.

Multi-stage builds let you use a full image for compilation and a minimal image for the final artifact:

```dockerfile
FROM golang:1.22@sha256:... AS build
WORKDIR /src
COPY . .
RUN CGO_ENABLED=0 go build -o /app .

FROM gcr.io/distroless/static-debian12@sha256:...
COPY --from=build /app /app
ENTRYPOINT ["/app"]
```

## Image Signing and Verification

[Docker Content Trust](https://docs.docker.com/engine/security/trust/) (DCT) provides image signing via Notary. Enable it for push and pull:

```bash
export DOCKER_CONTENT_TRUST=1
docker pull node:20       # verifies signature before pulling
docker push myorg/myapp   # signs on push
```

For more flexible signing workflows — particularly for images built in CI — [Sigstore Cosign](https://docs.sigstore.dev/cosign/) can sign images and attach attestations (SBOM, provenance) to the registry:

```bash
# Sign after push
cosign sign --key cosign.key myregistry/myimage@sha256:...

# Verify before use
cosign verify --key cosign.pub myregistry/myimage@sha256:...
```

Cosign supports keyless signing via OIDC (e.g. GitHub Actions identity), which avoids managing long-lived signing keys.

## Scanning

Run image scanning in CI before pushing or deploying. Docker Scout is Docker's built-in scanner and integrates directly with `docker build`:

```bash
# Compare image against policy
docker scout cves myimage:latest

# Quick vulnerability summary
docker scout quickview myimage:latest
```

Docker Scout can be [configured as a GitHub Actions step](https://docs.docker.com/scout/integrations/ci/gha/) and will block a push if the image exceeds a defined CVE threshold.

## Dependabot for Base Images

Dependabot can track base image updates in Dockerfiles and open PRs when new digests are available:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: docker
    directory: /
    schedule:
      interval: weekly
    open-pull-requests-limit: 5
```

Combine with a cooldown review process: let Dependabot open the PR, but require a manual review before merging base image updates, particularly for major version bumps.

## References

- [Docker Official Images](https://hub.docker.com/search?image_filter=official)
- [Docker Verified Publishers](https://hub.docker.com/search?image_filter=store)
- [Docker Content Trust documentation](https://docs.docker.com/engine/security/trust/)
- [Docker Scout documentation](https://docs.docker.com/scout/)
- [Sigstore Cosign](https://docs.sigstore.dev/cosign/)
- [GoogleContainerTools/distroless](https://github.com/GoogleContainerTools/distroless)
- [Dependabot: Docker ecosystem](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file#package-ecosystem)
- [OpenSSF: Sigstore: Simplifying Code Signing for Open Source Ecosystems](https://openssf.org/blog/2023/11/21/sigstore-simplifying-code-signing-for-open-source-ecosystems/)
