<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Agent Instructions: Terraform / OpenTofu Dependency Management

This file contains mandatory guidelines for managing provider and module dependencies in this Terraform or OpenTofu project. Follow these rules whenever adding, updating, or removing providers and modules, or modifying CI configuration.

<!-- terraform | opentofu -->
Delete the line above and keep only the tool that applies to this project.

## Hash Verification: Never Fabricate

**AI agents must never invent, guess, autocomplete, or extrapolate a `.terraform.lock.hcl` `h1:` or `zh:` hash, a module checksum, or any other cryptographic hash.** A fabricated hash either fails `terraform init` verification or silently allows the wrong provider binary to be installed.

All `.terraform.lock.hcl` entries must be produced by the CLI itself — run `terraform providers lock -platform=...` (or `tofu providers lock`) for every CI/dev platform and commit the resulting file. Do not hand-edit `hashes = [...]` blocks.

To confirm a provider version actually exists on the registry before pinning to it:

**Preferred:** if the `harden-packages` skill is available, use its helper:

```bash
python {SKILL_DIR}/verify_hash.py tf-provider <namespace>/<name>              # list all versions
python {SKILL_DIR}/verify_hash.py tf-provider <namespace>/<name> <version>   # verify exists
python {SKILL_DIR}/verify_hash.py tf-provider <namespace>/<name> --opentofu  # OpenTofu registry
```

**Fallback:** `curl -fsSL https://registry.terraform.io/v1/providers/<namespace>/<name>/versions | jq '.versions[].version'` (or `registry.opentofu.org` for OpenTofu).

If you cannot verify a hash with any of the above, **stop and ask the user**. Do not insert a placeholder or a "likely correct" value.

## Provider and Module Addresses: Never Guess

**AI agents must never add a provider or module whose exact source address they have not verified against the registry in the current session.** The namespace segment is the trust anchor — `hashicorp/aws` is the real AWS provider; a look-alike namespace serving a same-named provider is an attack.

Before adding any new provider or module:

1. Verify the exact source address on <https://registry.terraform.io/> (or the OpenTofu registry) and confirm the tier badge: prefer Official and Partner providers; for modules, confirm the owning namespace is the project's real organisation.
2. Treat as red flags: a community-tier provider shadowing an official name, a namespace one or two characters off a well-known one, and a very recently published module with names matching popular ones.

If the lookup is ambiguous or the address cannot be confidently identified, **stop and ask the user** — do not choose between similar addresses on intuition.

## Dependency Rules

**Always pin providers to exact versions** using the `=` operator in `required_providers`. Never use `~>`, `>=`, or open ranges for production providers:

```hcl
# correct
terraform {
  required_version = "= 1.9.8"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.84.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "= 6.18.0"
    }
  }
}

# incorrect — do not use
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"     # allows any 5.x — do not use
    }
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0"     # unbounded upper range — do not use
    }
  }
}
```

**Always pin `required_version`** for the Terraform/OpenTofu CLI itself in each root module. Use `=` for exact pinning, not `~>` or `>=`.

**Never add a provider version published within the last 7 days.** Check the provider's page on the Terraform Registry (registry.terraform.io) or OpenTofu Registry (registry.opentofu.org) before adding any new provider or version. If a version was published less than 7 days ago, defer the addition until the cooldown has elapsed.

**For modules**: treat module source references the same way. Pin all `source` references that use a registry module to an exact `version`. For Git module sources, pin to a specific tag — never use `ref=main` or `ref=master`.

```hcl
# correct
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "= 5.9.0"
}

# incorrect
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
}
```

## Lockfile Management

**Always commit `.terraform.lock.hcl`** to version control. It records the exact provider versions and their hash signatures — it is the primary mechanism for reproducible provider installs.

**Pre-populate hashes for all CI platforms** using `terraform providers lock`. If your CI runs on Linux (AMD64/ARM64) and your developers use macOS (ARM64), the lockfile must include all platform hashes:

```bash
# run this locally after any provider version change
terraform providers lock \
  -platform=linux/amd64 \
  -platform=linux/arm64 \
  -platform=darwin/arm64 \
  -platform=darwin/amd64 \
  -platform=windows/amd64
```

Commit the resulting `.terraform.lock.hcl`. Without this step, `terraform init` will fail in CI when the lockfile doesn't include the CI runner's platform hash.

## CI Commands

```bash
terraform init -input=false                # initialise; fails if lock is missing
terraform init -lockfile=readonly          # strictly enforce lock; do not update it
terraform validate                         # syntax/schema validation
terraform plan -input=false -lock=true     # plan with state locking
```

Use `-lockfile=readonly` in all CI pipelines so that a missing or outdated lockfile causes an explicit failure rather than silently pulling a different version.

For OpenTofu, substitute `terraform` with `tofu` in all commands above.

## Configuration to Verify

**State backend locking** must be enabled. Remote backends (S3, GCS, Terraform Cloud, OpenTofu Cloud) support locking by default — verify it is not explicitly disabled:

```hcl
# S3 backend — do not set use_lockfile = false
terraform {
  backend "s3" {
    bucket         = "my-tf-state"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    # use_lockfile defaults to true — do not override
  }
}
```

**Provider signing verification** is enforced automatically by the Terraform/OpenTofu CLI via the lockfile's `zh:` (HashiCorp-signed) and `h1:` (SHA-256 hash) entries. Do not add `--skip-provider-verification` flags to any init command.

## CI Configuration

### Dependabot

`.github/dependabot.yml` must include an entry for `terraform`. Note: Dependabot cooldown for the `terraform` ecosystem is affected by a known bug ([dependabot/dependabot-core#13715](https://github.com/dependabot/dependabot-core/issues/13715)) that may cause provider version updates to ignore the cooldown configuration. Use exact `= X.Y.Z` pinning as the primary defence; treat the Dependabot cooldown as a best-effort secondary layer until the bug is resolved.

```yaml
version: 2
updates:
  - package-ecosystem: "terraform"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30
      semver-minor-days: 7
      semver-patch-days: 3
```

If the project uses modules in subdirectories, add a separate entry per directory:

```yaml
  - package-ecosystem: "terraform"
    directory: "/modules/networking"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 7
```

Security update PRs from Dependabot bypass the cooldown automatically and should be reviewed and merged promptly.

### Harden-Runner

Every GitHub Actions workflow that runs `terraform init` or `tofu init` must include `step-security/harden-runner` as its first step. New workflows must not be added without it.

Start in `audit` mode for new workflows, then tighten to `block` once the egress policy is stable:

```yaml
- uses: step-security/harden-runner@6c3c2f2c1c457b00c10c4848d6f5491db3b629df # v2
  with:
    egress-policy: block
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      registry.terraform.io:443
      releases.hashicorp.com:443
      checkpoint-api.hashicorp.com:443
```

For OpenTofu, replace the HashiCorp-specific endpoints with:

```yaml
      registry.opentofu.org:443
      github.com:443
      objects.githubusercontent.com:443
```

Provider binaries are downloaded from provider-specific CDN URLs that vary by provider. Discover the actual endpoints for your provider set by running a workflow in `audit` mode first and reviewing the egress log before switching to `block`.

## OpenTofu Differences

If this project uses OpenTofu instead of Terraform, the following differences apply:

- Replace `terraform` CLI invocations with `tofu` in all commands
- Provider registry: `registry.opentofu.org` (not `registry.terraform.io`)
- Dependabot support: OpenTofu projects using Dependabot require **OpenTofu ≥ 1.8**. If the project is on an older version, Dependabot will not correctly parse the configuration — upgrade to ≥ 1.8 before enabling Dependabot
- State encryption: OpenTofu supports native state encryption via `encryption {}` blocks — consider enabling it if not already configured
- Signing keys: OpenTofu providers use different signing keys from HashiCorp providers. The lockfile's `zh:` hash scheme will reflect this. Do not copy lockfiles between Terraform and OpenTofu projects

## What Requires Human Review

The following changes must not be made autonomously and require explicit human approval before proceeding:

- Adding a new provider not previously present in `required_providers`
- Upgrading a provider's major version
- Changing `=` exact version pins to `~>` or `>=` ranges
- Adding a new remote backend or changing the backend type
- Modifying `.github/dependabot.yml` cooldown values downward
- Removing or modifying Harden-Runner from a workflow
- Removing `-lockfile=readonly` from CI init commands
- Adding `--skip-provider-verification` to any command
