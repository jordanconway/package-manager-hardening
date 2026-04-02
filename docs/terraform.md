# Infrastructure as Code: Terraform and OpenTofu


Terraform and OpenTofu manage cloud infrastructure via *providers* (plugins that talk to APIs) and *modules* (reusable configuration bundles). Both are distributed through registries rather than language-specific package indexes, but the supply chain risks are similar: a compromised provider or module version can exfiltrate credentials, modify infrastructure state, or create backdoors.

## Terraform

**Configuration files:** `*.tf` files, `.terraform.lock.hcl`, `.terraformrc`

### Lockfile

Terraform generates `.terraform.lock.hcl` on `terraform init`. Always commit it — it records exact provider versions and multi-platform cryptographic hashes, providing strong integrity guarantees.

```bash
terraform init              # creates/updates .terraform.lock.hcl
terraform init -upgrade     # re-resolves within constraints and updates lock
```

The lock file stores two hash schemes per provider:
- `zh:` — hash of the zip archive (populated from registry metadata on first init)
- `h1:` — hash of the extracted binary (added when actually installed on a platform)

For teams working across multiple OS/arch combinations, pre-populate hashes for all target platforms before committing:

```bash
# Pre-populate hashes for all platforms your team and CI use
terraform providers lock \
  -platform=linux_amd64 \
  -platform=linux_arm64 \
  -platform=darwin_amd64 \
  -platform=darwin_arm64 \
  -platform=windows_amd64
```

This prevents lock file churn from developers on different architectures each adding their platform's hashes.

### Version Pinning

Terraform supports several version constraint operators in `required_providers` and module `version` arguments:

| Operator | Behaviour | Example |
|---|---|---|
| `=` | Exact version — use for maximum security | `= 5.31.0` |
| `~>` | Pessimistic — allows only rightmost component to increment | `~> 5.31.0` (patch only), `~> 5.31` (minor+patch) |
| `>=` | Minimum — any version at or above | `>= 5.0` |
| `>=, <` | Range — bounded minimum + maximum | `>= 5.0, < 6.0` |

For supply chain hardening, use `=` (exact) for providers in root modules. The `~>` operator is a reasonable compromise for modules that are consumed by others (where pinning too tightly creates friction for downstream users), but exact pinning is always safer for deployed infrastructure.

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.31.0"    # exact — recommended for root modules
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6.0"    # patch-only — acceptable for well-maintained providers
    }
  }
}
```

### Security: No Native Minimum Release Age

Neither Terraform nor OpenTofu has a native cooldown or minimum release age mechanism. The best available options are:

- **Exact version pinning (`=`):** The strongest control — a provider version can only enter your infrastructure by an explicit change to `*.tf` files, which goes through code review.
- **Dependabot with cooldown:** See the caveat below — the cooldown feature has a known bug for Terraform providers.
- **Private registry mirror:** Route provider fetches through a controlled mirror where new versions can be reviewed before they become available.

### Provider Signing

Providers installed from the Terraform Registry are signed with GPG keys. Terraform verifies these signatures during `terraform init`. Providers signed by HashiCorp or verified partners carry a trust chain; community providers are self-signed.

The lock file's hash values are derived from the signed package, so a tampered provider binary will produce a hash mismatch and fail to install. This is a strong integrity control, but it operates on trust-on-every-use from the registry's public key — a registry compromise would affect all downloads.

### CI Configuration

```hcl
# Use -lockfile=readonly in CI to prevent accidental lock file updates
terraform init -lockfile=readonly
terraform plan
terraform apply
```

```ini
# .terraformrc — configure a network mirror for air-gapped or controlled environments
provider_installation {
  network_mirror {
    url     = "https://your-mirror.example.com/providers/"
    include = ["registry.terraform.io/*/*"]
  }
}
```

### Dependabot

`.github/dependabot.yml` supports Terraform via the `terraform` ecosystem:

```yaml
version: 2
updates:
  - package-ecosystem: "terraform"
    directory: "/"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 7
      semver-major-days: 30
```

> **Known issue:** Dependabot's `cooldown` setting has a [documented bug for Terraform providers](https://github.com/dependabot/dependabot-core/issues/13715) — despite respecting the cooldown when selecting a version, it then re-runs `terraform lock` which upgrades to the latest available version. The cooldown constraint is effectively ignored for providers. Module updates (Git-sourced) are not affected. Exact pinning (`=`) in `required_providers` is the more reliable control until this is fixed.

### Harden-Runner

```yaml
- uses: step-security/harden-runner@v2
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

Add your cloud provider API endpoints (e.g. `*.amazonaws.com:443`) as needed for plan/apply steps.

---

## OpenTofu

**Configuration files:** `*.tf` or `*.tofu` files, `.terraform.lock.hcl`, `.tofurc`

OpenTofu is the open-source fork of Terraform maintained by the Linux Foundation. Its dependency management is largely identical to Terraform's, with a few meaningful differences.

### What's the same

- `.terraform.lock.hcl` format — same file, same structure, same hash schemes (`h1:`, `zh:`)
- Version constraint syntax — `=`, `~>`, `>=`, `>=, <` work identically
- `tofu providers lock` for multi-platform hash pre-population (same flags as `terraform providers lock`)
- `-lockfile=readonly` flag in CI
- Dependabot support (added December 2025 via the `terraform` ecosystem — `.tofu` files are detected automatically)

### What's different

**Registry and signing keys:** OpenTofu uses its own registry (`registry.opentofu.org`) with independent GPG signing keys. If you migrate a project from Terraform to OpenTofu, your `.terraform.lock.hcl` hashes will need to be regenerated — the same provider version will produce different hashes because the signing keys differ.

**Dependabot compatibility:** OpenTofu v1.8+ introduced early variable evaluation, which breaks Dependabot's version parsing. Projects on OpenTofu v1.8 or later may see Dependabot failures until this is resolved upstream.

**State encryption:** OpenTofu 1.7+ includes native client-side state encryption, reducing reliance on backend-level controls (e.g. S3 server-side encryption). This is not directly a provider/module supply chain feature, but it limits the blast radius of a compromised provider that attempts to exfiltrate state.

**SBOM support:** Under active development (RFC #2494) — OpenTofu's registry will support SBOM artifacts and provider attestations. Not yet available.

### CI Recommended Configuration

```bash
# OpenTofu CI — mirrors Terraform best practices
tofu init -lockfile=readonly
tofu providers lock \
  -platform=linux_amd64 \
  -platform=darwin_arm64
tofu plan
```

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "terraform"   # covers both .tf and .tofu files
    directory: "/"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 7
      semver-major-days: 30
```

> **Note:** Apply the same Dependabot provider cooldown caveat from the Terraform section — the bug affects OpenTofu equally. Exact version pinning remains the more reliable control.

---

