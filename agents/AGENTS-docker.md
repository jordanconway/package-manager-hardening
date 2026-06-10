<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Agent Instructions: Container Image Hardening

This file contains mandatory guidelines for working with Dockerfiles and container images in this project. Follow these rules whenever modifying Dockerfiles, updating base images, or adding container-related CI steps.

## Hash Verification: Never Fabricate

**AI agents must never invent, guess, autocomplete, or extrapolate an image digest (`sha256:...`) or any other cryptographic hash.** A fabricated digest either fails the pull (best case) or silently pins to an unintended image if it collides with anything in the registry. Treat any digest you did not just look up as unknown.

Every `@sha256:...` written into a Dockerfile, Compose file, Kubernetes manifest, or CI step must come from an authoritative registry lookup performed in this session.

**Preferred:** if the `harden-packages` skill is available, use its helper:

```bash
python {SKILL_DIR}/verify_hash.py oci <image>:<tag>          # → sha256: digest
```

**Fallback if the helper isn't present:** `crane digest <image>:<tag>`, `skopeo inspect docker://<image>:<tag> --format '{{.Digest}}'`, or `docker buildx imagetools inspect <image>:<tag> --format '{{json .Manifest}}' | jq -r .digest`.

If you cannot verify a digest with any of the above, **stop and ask the user**. Do not insert a placeholder, a truncated digest, or a "likely correct" value.

## Image Names: Never Guess

**AI agents must never reference an image whose exact name and namespace they have not verified against the registry in the current session.** A guessed image name either fails to resolve or resolves to a look-alike under a squatted namespace — user namespaces mimicking official images are a known Docker Hub attack pattern.

Before referencing any new image:

1. Verify the exact name on Docker Hub (or the relevant registry) and confirm the publisher: prefer Docker Official Images (`docker.io/library/*`), Verified Publisher, or Sponsored OSS badges. For other registries (`ghcr.io`, `quay.io`), confirm the owning organisation is the project's real organisation.
2. Treat as red flags: a user namespace serving what looks like an official image (`someuser/node` vs `library/node`), a recently created repository with few pulls, and image names differing from popular images by one character.

If the lookup is ambiguous or the image cannot be confidently identified, **stop and ask the user** — do not choose between similar names on intuition.

## Base Image Rules

**Always pin base images to their immutable digest.** Never use a mutable tag alone:

```dockerfile
# Correct — digest-pinned with tag comment
FROM node:20@sha256:a1b2c3d4e5f6...  # node:20 as of 2026-01-15

# Incorrect — mutable, do not use
FROM node:20
FROM node:latest
```

To resolve the current digest before updating a base image:

```bash
docker buildx imagetools inspect <image>:<tag> --format '{{json .Manifest}}' | jq .digest
```

**Use official or verified images only.** Prefer Docker Official Images (short name, no namespace) or Docker Verified Publishers. Do not introduce base images from arbitrary Docker Hub namespaces without explicit human approval.

**Use minimal base images.** Prefer distroless, `-slim`, or Alpine variants. Use multi-stage builds to separate build-time and runtime dependencies.

## Cooldown

**Do not update a base image digest published within the last 7 days** without human approval. Check the image's published date via `docker buildx imagetools inspect` before proposing an update.

## Dependabot

If the repository has a `.github/dependabot.yml`, ensure a `docker` ecosystem block is present covering all Dockerfile locations. Do not remove or disable the `docker` block.

## What Requires Human Review

Always pause and ask before:

- Changing the base image to a different image name or namespace
- Merging a base image update that is less than 7 days old
- Disabling `DOCKER_CONTENT_TRUST` or removing cosign verification steps
- Adding a `RUN` step that downloads and executes remote content (curl | sh patterns)
- Granting a container elevated privileges (`--privileged`, `CAP_SYS_ADMIN`)
