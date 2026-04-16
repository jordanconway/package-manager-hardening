<!--
SPDX-FileCopyrightText: 2026 The Linux Foundation

SPDX-License-Identifier: MIT
-->

# Ruby Ecosystem

## Bundler

**Configuration files:** `Gemfile`, `Gemfile.lock`, `.bundle/config`

Bundler is the standard dependency manager for Ruby. All Ruby applications (Rails, Sinatra, CLI tools) should use Bundler to manage gem versions and reproduce builds reliably.

### Lockfile

Bundler generates `Gemfile.lock` on first install. Always commit it for applications. In CI, enforce the lockfile so that builds cannot silently resolve to a different set of versions:

```bash
# Bundler 2.x — set frozen mode for the project
bundle config set --local frozen true
bundle install

# Or enforce via environment variable (CI-friendly)
BUNDLE_FROZEN=true bundle install

# Never run in CI — re-resolves and can update Gemfile.lock
bundle update
```

`BUNDLE_FROZEN=true` causes Bundler to fail if `Gemfile.lock` would need to change. This is the equivalent of `npm ci` or `composer install` (not `composer update`).

The legacy `--frozen` flag (Bundler 1.x) and `--deployment` mode still work but `BUNDLE_FROZEN=true` is the recommended approach for Bundler 2.x.

### Version Pinning

When you run `bundle add gem-name`, Bundler defaults to a pessimistic constraint (`~>`), which allows patch or minor releases depending on the specificity of the version. Use explicit exact versions to prevent silent drift:

```ruby
# Gemfile — exact version (recommended)
gem 'rails', '7.1.3'
gem 'rails', '= 7.1.3'  # equivalent explicit form
```

The `~>` pessimistic constraint behaves as follows:

| Syntax | Meaning | Equivalent range |
|--------|---------|-----------------|
| `'7.1.3'` | Exact — only this version | `= 7.1.3` |
| `'= 7.1.3'` | Exact — explicit form | `= 7.1.3` |
| `'~> 7.1.3'` | Patch-only | `>= 7.1.3, < 7.2.0` |
| `'~> 7.1'` | Minor + patch | `>= 7.1, < 8.0` |
| `'>= 7.1.3'` | Open range | Any version ≥ 7.1.3 |
| `'>= 7.1.3', '< 8.0'` | Explicit range | — |

`~> 7.1.3` (three-component form) is safer than `~> 7.1` (two-component form), but only exact pinning eliminates the risk of adopting a newly published version.

### Security: No Native Minimum Release Age

Bundler and RubyGems have no built-in cooldown or minimum release age mechanism. The recommended approach is:

- Use Dependabot with `cooldown` blocks to delay automatic update PRs
- Pin exact versions in `Gemfile` so no new version can be adopted without an explicit change

### Security: bundler-audit

`bundler-audit` checks your `Gemfile.lock` against the [Ruby Advisory Database](https://github.com/rubysec/ruby-advisory-db) and exits non-zero if vulnerabilities are found:

```bash
# Install
gem install bundler-audit

# Update the advisory database and check
bundle audit check --update

# Check without network (use cached DB)
bundle audit check

# Check from CI without updating (update DB separately)
bundle audit check
```

Run `bundle audit check` in every CI build. The advisory database can be updated separately via `bundle audit update` if network access to the advisory DB endpoint needs to be allowlisted.

### Security: ruby_audit

`ruby_audit` checks the Ruby interpreter itself (not gems) against known CVEs:

```bash
gem install ruby_audit
ruby-audit check
```

Useful as a complementary check, particularly when the Ruby runtime version is managed via a lockfile like `.ruby-version` or `Gemfile`'s `ruby` directive.

### Security: Native Extensions

Some gems compile native C extensions during install (`extconf.rb`). This runs arbitrary code at install time, analogous to npm postinstall scripts. There is no native allowlist mechanism in Bundler (unlike pnpm's `onlyBuiltDependencies`).

Mitigations:

- Use `--no-cache` in CI to avoid reusing cached builds of potentially compromised versions
- Review gems with native extensions before adding them
- Pin exact versions so compiled artifacts correspond to a reviewed version
- Use `bundler-audit` to catch known-vulnerable gems before they reach production

### CI Recommended Configuration

```bash
# Enforce lockfile — fail if Gemfile.lock would change
export BUNDLE_FROZEN=true

# Install gems
bundle install --jobs 4 --retry 3

# Check for known vulnerabilities
bundle exec bundle-audit check --update

# Optional: check Ruby interpreter CVEs
ruby-audit check
```

For the `bundle-audit check --update` step to work, the advisory database endpoint must be reachable. If running in a strict egress environment, update the database separately and cache it:

```bash
bundle audit update              # update DB (requires network)
bundle audit check               # check without network
```

### Gemfile `ruby` Directive

Pin the Ruby version in the `Gemfile` to ensure consistent interpreter across environments:

```ruby
ruby '3.3.0'
```

Alternatively manage via `.ruby-version` (used by rbenv, rvm, asdf). Bundler reads `.ruby-version` if no `ruby` directive is present in the `Gemfile`.

## Dependabot

Dependabot supports the `bundler` ecosystem. Configure cooldowns in `.github/dependabot.yml`:

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

## Harden-Runner

Every GitHub Actions workflow that runs `bundle install` must include `step-security/harden-runner`:

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

If using gems sourced directly from GitHub, add `codeload.github.com:443`. For gems from a private Gemfury or Gemstash registry, add that hostname. For `bundle audit update`, also add `raw.githubusercontent.com:443` (the advisory database is hosted on GitHub).

Start in `audit` mode for new workflows and switch to `block` after reviewing audit logs to build a confirmed allowlist.
