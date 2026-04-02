# harden-packages Skill

This repository also includes a [Cowork](https://claude.ai) / [Claude Code](https://claude.ai/claude-code) skill that actively audits a repository's package manager configuration and applies fixes interactively. Where the `AGENTS.md` files give an AI agent *standing instructions* to follow as it works, the skill is something you invoke on demand to get an immediate audit report and remediation.

## What it does

When invoked, the skill will:

1. **Detect** which ecosystems are present (Node.js, Python, Go, Rust, Terraform/OpenTofu) and which CI workflows exist
2. **Audit** each ecosystem against the hardening checklist, marking each item ✅ / ⚠️ / ❌
3. **Report** findings with a prioritised list of what poses the most supply chain risk
4. **Fix** gaps interactively — it will ask before writing any files, and you can approve all fixes or pick and choose

## Installation

The skill lives in `skills/harden-packages/` in this repo. Copy it into your Claude skills directory:

```bash
# Claude Code (default skills location)
cp -r skills/harden-packages ~/.claude/skills/

# Or clone the repo and copy
git clone https://github.com/jordanconway/package-manager-hardening
cp -r package-manager-hardening/skills/harden-packages ~/.claude/skills/
```

Verify it's available by checking your skills list in Claude Code:

```bash
claude skills list
```

## Usage

Once installed, open a repository in Claude Code or Cowork and say any of the following — the skill will trigger automatically:

- `harden my repo`
- `audit my package manager config`
- `check my dependencies for supply chain issues`
- `set up Dependabot and Harden-Runner`
- `are my packages safe?`
- `apply package manager hardening`

You can also be specific about scope:

- `audit just the Python dependencies`
- `check if my GitHub Actions workflows have Harden-Runner configured`
- `set up Dependabot cooldowns for this pnpm project`

## What it checks

The skill audits all of the following, where applicable to the detected stack:

| Area | Checks |
|------|--------|
| Lockfiles | Present and committed, not gitignored |
| Version pinning | Exact versions, no `^` / `~` / `>=` / `~>` ranges |
| Minimum release age | Native client config (npm, pnpm, yarn, bun, uv) |
| Build script control | pnpm `onlyBuiltDependencies`, Bun `lifecycleScripts` |
| CI install commands | Frozen/locked install flags enforced |
| Terraform lockfile | `.terraform.lock.hcl` committed, multi-platform hashes, `-lockfile=readonly` in CI |
| Dependabot | Cooldown blocks present for each ecosystem (Terraform cooldown bug flagged) |
| Harden-Runner | Present in all workflows, `block` vs `audit` mode, `allowed-endpoints` |
| Vulnerability scanning | `cargo audit`, `govulncheck`, `pip-audit` in CI |

## Notes

- The skill never downgrades an existing security setting — if you already have a stricter cooldown than the recommended 7 days, it leaves it alone.
- It starts Harden-Runner additions in `audit` mode, not `block`. Switching to block requires reviewing egress logs first, and the skill will explain how.
- It will not change version numbers in package manifests without explicit instruction — pinning existing ranges is a breaking change that deserves separate review.

