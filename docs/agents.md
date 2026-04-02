# AGENTS.md Files

This repository includes ready-made `AGENTS.md` files for each supported stack. These files are read by Claude Code and compatible AI coding assistants when they work inside a repository, giving the agent standing instructions on how to handle dependencies safely — enforcing version pinning, cooldown windows, audit requirements, and CI configuration.

## Available files

| File | Use for |
|------|---------|
| [`AGENTS-nodejs.md`](../agents/AGENTS-nodejs.md) | Projects using npm, pnpm, Yarn, or Bun |
| [`AGENTS-python.md`](../agents/AGENTS-python.md) | Projects using pip/pip-tools or uv |
| [`AGENTS-go.md`](../agents/AGENTS-go.md) | Go module projects |
| [`AGENTS-rust.md`](../agents/AGENTS-rust.md) | Rust/Cargo projects |
| [`AGENTS-terraform.md`](../agents/AGENTS-terraform.md) | Terraform or OpenTofu projects |
| [`AGENTS-php.md`](../agents/AGENTS-php.md) | PHP / Composer projects |

## Installation

Copy the appropriate file to the root of your repository and rename it `AGENTS.md`:

```bash
# Node.js project
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/agents/AGENTS-nodejs.md

# Python project
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/agents/AGENTS-python.md

# Go project
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/agents/AGENTS-go.md

# Rust project
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/agents/AGENTS-rust.md

# Terraform / OpenTofu project
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/agents/AGENTS-terraform.md

# PHP / Composer project
curl -o AGENTS.md https://raw.githubusercontent.com/jordanconway/package-manager-hardening/main/agents/AGENTS-php.md
```

Or clone and copy manually:

```bash
git clone https://github.com/jordanconway/package-manager-hardening
cp package-manager-hardening/agents/AGENTS-nodejs.md your-project/AGENTS.md
```

## Customisation

After copying, open the file and:

1. **Node.js only:** remove the package manager options that don't apply — the file has a `<!-- npm | pnpm | yarn | bun -->` comment near the top indicating which to keep.
2. **Terraform / OpenTofu only:** remove the tool indicator comment at the top (`<!-- terraform | opentofu -->`) and keep only the relevant tool name.
3. Update the Harden-Runner `allowed-endpoints` list to match your project's actual network requirements — the provided list is a safe starting point, not a complete allowlist.
4. Adjust cooldown values if your project has specific requirements (valid range: 1–90 days for Dependabot).
5. **Go only:** update the `GOPRIVATE` / `GONOSUMDB` values to match your organisation's internal module paths.

## Monorepos with multiple stacks

For a monorepo containing multiple ecosystems, place a stack-specific `AGENTS.md` in the relevant subdirectory alongside the package manager config file for that language:

```
/                        ← root AGENTS.md (general project context)
├── services/api/        ← AGENTS.md (Node.js rules)
├── services/worker/     ← AGENTS.md (Python rules)
└── tools/cli/           ← AGENTS.md (Go rules)
```

Claude Code reads `AGENTS.md` files from the repo root and from the current working directory, so subdirectory files apply automatically when the agent is working within that directory.
