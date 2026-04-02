# PHP Ecosystem

## Composer

**Configuration files:** `composer.json`, `composer.lock`, `auth.json`

Composer is the standard dependency manager for PHP. All modern PHP projects should use Composer 2.x (1.x is EOL).

### Lockfile

Composer generates `composer.lock` on first install. Always commit it for applications. In CI, always use `composer install` — it reads the lockfile exactly and fails if the lockfile is absent or inconsistent with `composer.json`. Never run `composer update` in CI or production.

```bash
composer install                      # strict: installs from composer.lock
composer update                       # re-resolves: updates composer.lock (dev only)
composer install --no-scripts \
  --no-plugins --prefer-dist          # recommended CI invocation (see below)
```

### Version Pinning

When you run `composer require vendor/package`, Composer defaults to a `^` (caret) constraint, which allows any compatible minor/patch release. Use exact version strings to prevent silent drift:

```json
{
  "require": {
    "vendor/package": "1.2.3"
  }
}
```

Caret and tilde behave slightly differently in Composer vs npm:

| Syntax | Meaning | Example range |
|--------|---------|---------------|
| `1.2.3` | Exact — only this version | `= 1.2.3` |
| `^1.2.3` | `>=1.2.3 <2.0.0` | Any `1.x` from 1.2.3 |
| `~1.2.3` | `>=1.2.3 <1.3.0` | Any `1.2.x` patch only |
| `>=1.0 <2.0` | Explicit range | — |
| `1.2.*` | Wildcard | Any `1.2.x` |

Prefer exact versions (`1.2.3`) or at most tilde (`~1.2.3`) for tight patch-only bounds. Avoid `^` for security-sensitive dependencies.

### Registry Configuration

Packagist (packagist.org) is the default public registry. For private packages:

```json
{
  "repositories": [
    {
      "type": "composer",
      "url": "https://your-private-packagist.example.com"
    }
  ]
}
```

Credentials go in `auth.json` (do not commit — add to `.gitignore`):

```json
{
  "http-basic": {
    "your-private-packagist.example.com": {
      "username": "token",
      "password": "${PACKAGIST_TOKEN}"
    }
  }
}
```

Composer 2.0+ added **canonical repository** behaviour: once a package is found in one repository, Composer stops searching others. This prevents dependency confusion attacks where an attacker publishes a higher version to a public registry that shadows an internal package.

### Security: No Native Minimum Release Age

Composer has no built-in cooldown or minimum release age mechanism as of early 2026 (open issues [#12552](https://github.com/composer/composer/issues/12552) and [#12633](https://github.com/composer/composer/issues/12633)). The recommended approach is:

- Use Dependabot with `cooldown` blocks (see [Dependabot](dependabot.md)) to delay automatic update PRs
- Pin exact versions in `composer.json` so no new version can be adopted without an explicit change

### Security: composer audit (Composer ≥ 2.4)

`composer audit` checks all installed packages against the PHP Security Advisories Database and exits non-zero if vulnerabilities are found:

```bash
composer audit                  # check installed packages
composer audit --locked         # check from composer.lock without installing
```

Run `composer audit` in CI on every build. Fail the pipeline on a non-zero exit code. Since Composer 2.7, `composer audit` also flags abandoned packages.

Since Composer 2.9, Composer automatically blocks updates to packages with known security advisories by default.

### Security: roave/security-advisories

A dev dependency that uses Composer's `conflicts` mechanism to prevent installation of packages with known vulnerabilities. Unlike `composer audit` (which reports after the fact), `roave/security-advisories` causes dependency resolution to fail before a vulnerable version is installed:

```bash
composer require --dev roave/security-advisories:dev-latest
```

Must use `dev-latest` — a pinned version would become stale. This is a dev dependency only; it has no effect on production installs when `--no-dev` is used.

### Security: Build Script Control

Composer plugins and package scripts (`post-install-cmd`, `post-update-cmd`, etc.) run arbitrary code at install time. Disable them in CI unless explicitly required:

```bash
composer install --no-scripts --no-plugins --prefer-dist
```

- `--no-scripts` — prevents lifecycle scripts (`post-install-cmd`, etc.) from running
- `--no-plugins` — prevents Composer plugins from activating
- `--prefer-dist` — downloads archives rather than cloning repositories; faster, smaller, excludes dev artifacts

If specific scripts or plugins are required, enable them selectively and audit what they do. Never run Composer as root in automated pipelines.

### Security: local-php-security-checker

A standalone binary that checks `composer.lock` against the PHP security advisories database without requiring Composer to be installed:

```bash
# Install
curl -L https://github.com/fabpot/local-php-security-checker/releases/latest/download/local-php-security-checker_linux_amd64 \
  -o local-php-security-checker && chmod +x local-php-security-checker

# Run
./local-php-security-checker
```

An alternative to `composer audit` for pipelines where Composer itself is not installed.

### CI Recommended Configuration

```bash
# Set in CI environment
export COMPOSER_NO_INTERACTION=1

# Install dependencies
composer install --no-scripts --no-plugins --prefer-dist

# Audit for vulnerabilities
composer audit --locked

# Validate platform requirements
composer check-platform-reqs
```

Verify your `composer.json` is well-formed and consistent with the lockfile:

```bash
composer validate --strict
```

## Dependabot

Dependabot supports the `composer` ecosystem. Configure cooldowns in `.github/dependabot.yml`:

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

## Harden-Runner

Every workflow that runs `composer install` must include `step-security/harden-runner`:

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

If using packages sourced from GitHub or GitLab directly, add `codeload.github.com:443` or the relevant GitLab hostname. For private Packagist add your registry hostname.

## PEAR and PECL

PEAR (PHP Extension and Application Repository) and PECL (PHP Extension Community Library) are legacy systems. PEAR's website was compromised in a supply chain attack in 2019. For new projects, use Composer exclusively. PECL extensions installed via `pecl install` should be pinned to specific versions and verified via checksums or system package managers (e.g., `apt`, `apk`) rather than installed from PECL in production CI pipelines.
