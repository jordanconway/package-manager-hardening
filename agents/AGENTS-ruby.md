<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Agent Instructions: Ruby/Bundler Dependency Management

This file contains mandatory guidelines for managing dependencies in this Ruby project. Follow these rules whenever adding, updating, or removing gems, or modifying CI configuration.

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
- uses: step-security/harden-runner@v2
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
