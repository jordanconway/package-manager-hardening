# Agent Instructions: PHP/Composer Dependency Management

This file contains mandatory guidelines for managing dependencies in this PHP project. Follow these rules whenever adding, updating, or removing packages, or modifying CI configuration.

## Dependency Rules

**Always pin exact versions** in `composer.json`. Never use `^`, `~`, `>=`, or wildcard constraints for production dependencies:

```json
{
  "require": {
    "vendor/package": "1.2.3",
    "another/package": "4.5.6"
  }
}
```

```json
// incorrect — do not use
{
  "require": {
    "vendor/package": "^1.2.3",
    "another/package": "~4.5.0",
    "third/package": ">=2.0"
  }
}
```

**Never add a package version published within the last 7 days.** Check the publication date on packagist.org before adding any new dependency. If a version was published less than 7 days ago, defer the addition until the cooldown has elapsed.

**Always commit `composer.lock`** to version control. It ensures reproducible installs across development, CI, and production environments.

**Never run `composer update` in CI or production.** Use `composer install` only — it installs exactly what is in `composer.lock`.

## Configuration to Verify

**`roave/security-advisories`** should be present as a dev dependency. It prevents installation of packages with known vulnerabilities at dependency resolution time:

```bash
composer require --dev roave/security-advisories:dev-latest
```

**Composer version** must be 2.7 or later. Composer 1.x is EOL.

## CI Commands

```bash
export COMPOSER_NO_INTERACTION=1

composer validate --strict               # validate composer.json is well-formed
composer install \
  --no-scripts \
  --no-plugins \
  --prefer-dist                          # install from lockfile; no scripts or plugins
composer audit --locked                  # fail on known vulnerabilities
composer check-platform-reqs             # verify platform extensions and PHP version
```

**`--no-scripts`** prevents lifecycle scripts from running at install time. **`--no-plugins`** prevents Composer plugins from activating. Both eliminate vectors for arbitrary code execution during CI dependency installation.

## CI Configuration

### Dependabot

`.github/dependabot.yml` must include a cooldown for the `composer` ecosystem. If the file does not exist or lacks a cooldown block, add it:

```yaml
version: 2
updates:
  - package-ecosystem: "composer"
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

Every GitHub Actions workflow that runs `composer install` must include `step-security/harden-runner` as its first step. New workflows must not be added without it.

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
      packagist.org:443
      repo.packagist.org:443
```

Add `codeload.github.com:443` if any packages are sourced directly from GitHub repositories. Add your private registry hostname if using Private Packagist or Satis.

## What Requires Human Review

The following changes must not be made autonomously and require explicit human approval before proceeding:

- Adding a new package not previously present in `composer.json`
- Upgrading a major version
- Changing exact version pins to `^` or `~` ranges
- Adding or modifying Composer scripts (`post-install-cmd`, `post-update-cmd`, etc.)
- Modifying `.github/dependabot.yml` cooldown values downward
- Removing or modifying Harden-Runner from a workflow
- Removing `--no-scripts` or `--no-plugins` from CI install commands
- Running `composer update` (always flag this — prefer targeted `composer require vendor/package:X.Y.Z`)
