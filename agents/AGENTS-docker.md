<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Agent Instructions: Container Image Hardening

This file contains mandatory guidelines for working with Dockerfiles and container images in this project. Follow these rules whenever modifying Dockerfiles, updating base images, or adding container-related CI steps.

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
