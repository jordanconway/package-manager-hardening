<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Agent Instructions: Ruby/Bundler Dependency Management

This file contains mandatory guidelines for managing dependencies in this Ruby project. Follow these rules whenever adding, updating, or removing gems, or modifying CI configuration.

## Hash Verification: Never Fabricate

**AI agents must never invent, guess, autocomplete, or extrapolate a `Gemfile.lock` checksum, `bundler-checksums` entry, gem `.gem` SHA256, or commit SHA for a git-sourced gem.** A fabricated hash either fails verification or silently pins to the wrong artifact.

All `Gemfile.lock` entries (and any `Gemfile.lock.checksums` produced by the `bundler-checksums` plugin) must be produced by Bundler itself — run `bundle install` / `bundle update <gem>` and commit the result. Do not hand-edit checksum or `revision:` fields.

To confirm a published gem's checksum or a git revision:

**Preferred:** if the `harden-packages` skill is available, use its helper:

```bash
python {SKILL_DIR}/verify_hash.py gem <gem> <version>             # → SHA256
python {SKILL_DIR}/verify_hash.py gh-action <owner>/<repo> <ref>  # for git-sourced gems
```

**Fallback:** `curl -fsSL https://rubygems.org/api/v2/rubygems/<gem>/versions/<version>.json | jq '{sha, number, platform}'`.

If you cannot verify a hash with any of the above, **stop and ask the user**. Do not insert a placeholder or a "likely correct" value.

## Gem Names: Never Guess

**AI agents must never add a gem whose exact name they have not verified against RubyGems in the current session.** Typosquatting and slopsquatting — attackers registering names that language models tend to invent — are actively exploited vectors. A guessed name either fails to resolve or resolves to a malicious look-alike.

Before adding any new gem:

1. Verify the exact name and confirm it is the gem you intend: `gem info -r <gem>` or check `https://rubygems.org/gems/<gem>` — the description and linked repository must match the stated purpose.
2. Treat as red flags: a very recent first release, a name one or two characters off a popular gem (hyphen/underscore swaps are a classic RubyGems squat), a missing or unrelated repository link, and low download counts for a supposedly well-known gem.

If the lookup is ambiguous or the gem cannot be confidently identified, **stop and ask the user** — do not choose between similar names on intuition.

## Dependency Rules

**Always pin exact versions** in `Gemfile`. Never use `~>`, `>=`, or open range constraints for production dependencies:

```ruby
# Correct — exact version
gem 'rails', '7.1.3'
gem 'pg', '1.5.4'
```

```ruby
# Incorrect — do not use
gem 'rails', '~> 7.1.3'   # allows patch updates
gem 'rails', '~> 7.1'     # allows minor updates
gem 'rails', '>= 7.0'     # open range
```

**Never add a gem version published within the last 7 days.** Check the publication date on rubygems.org before adding any new dependency. If a version was published less than 7 days ago, defer the addition until the cooldown has elapsed.

**Always commit `Gemfile.lock`** to version control. It ensures reproducible installs across development, CI, and production environments.

**Never run `bundle update` in CI or production.** Use `bundle install` only — it installs exactly what is in `Gemfile.lock`. Always set `BUNDLE_FROZEN=true` in CI to enforce this.

## Configuration to Verify

**`bundler-audit`** must be installed and run in CI to check gems against the Ruby Advisory Database:

```bash
gem install bundler-audit
bundle audit check --update
```

**Bundler version** should be 2.x. The `Gemfile` should specify a `ruby` version directive (or a `.ruby-version` file should be committed) to ensure consistent interpreter versions:

```ruby
ruby '3.3.0'
```

## CI Commands

```bash
export BUNDLE_FROZEN=true

bundle install --jobs 4 --retry 3      # install from lockfile; fail if it would change
bundle exec bundle-audit check --update  # fail on known gem vulnerabilities
ruby-audit check                       # check Ruby interpreter CVEs (optional)
```

**`BUNDLE_FROZEN=true`** causes `bundle install` to fail if the `Gemfile.lock` would change. This prevents CI from silently re-resolving to a different set of gems than what was reviewed.

## CI Configuration

### Dependabot

`.github/dependabot.yml` must include a cooldown for the `bundler` ecosystem. If the file does not exist or lacks a cooldown block, add it:

```yaml
version: 2
updates:
  - package-ecosystem: "bundler"
    directory: "/"
    schedule:
      interval: "daily"
    cooldown:
      default-days: 7
      semver-major-days: 30
      semver-minor-days: 7
      semver-patch-days: 3
```

Security update PRs from Dependabot bypass the cooldown automatically and should be reviewed and merged promptly.

### Harden-Runner

Every GitHub Actions workflow that runs `bundle install` must include `step-security/harden-runner` as its first step. New workflows must not be added without it.

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
      rubygems.org:443
      api.rubygems.org:443
      index.rubygems.org:443
```

Add `codeload.github.com:443` if any gems are sourced directly from GitHub repositories. Add `raw.githubusercontent.com:443` if `bundle audit update` runs in CI (the advisory database is on GitHub). Add your private registry hostname if using Gemfury, Gemstash, or a private Bundler source.

## What Requires Human Review

The following changes must not be made autonomously and require explicit human approval before proceeding:

- Adding a new gem not previously present in `Gemfile`
- Upgrading a major version
- Changing exact version pins to `~>` or range constraints
- Modifying `.github/dependabot.yml` cooldown values downward
- Removing or modifying Harden-Runner from a workflow
- Removing `BUNDLE_FROZEN=true` from CI
- Running `bundle update` (always flag this — prefer targeted `bundle update gem-name` or explicit version pin change)
- Adding gems with native extensions (flag for security review — they run C compilation at install time)
