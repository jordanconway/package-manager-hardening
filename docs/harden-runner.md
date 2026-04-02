# Harden-Runner: Runtime CI Hardening


It is free for open source repositories.

## Recommended Rollout: Audit First, Then Block

Start every new workflow in `audit` mode to observe what outbound connections are actually made during a normal build. After a week or two of clean runs, review the generated policy in the [StepSecurity portal](https://app.stepsecurity.io) and switch to `block` mode with an explicit allowlist.

```yaml
# .github/workflows/ci.yml
steps:
  - uses: step-security/harden-runner@v2
    with:
      egress-policy: audit   # start here; switch to 'block' once allowlist is stable
      disable-sudo: true     # prevent privilege escalation on the runner
```

## Block Mode with Explicit Allowlists

Once the egress policy is stable, switch to `block` and enumerate only the endpoints your build actually needs. Examples per ecosystem:

**Node.js (npm / pnpm / yarn / bun):**

```yaml
- uses: step-security/harden-runner@v2
  with:
    egress-policy: block
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      registry.npmjs.org:443
      npm.pkg.github.com:443
```

**Python (pip / uv):**

```yaml
- uses: step-security/harden-runner@v2
  with:
    egress-policy: block
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      pypi.org:443
      files.pythonhosted.org:443
```

**Go:**

```yaml
- uses: step-security/harden-runner@v2
  with:
    egress-policy: block
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      proxy.golang.org:443
      sum.golang.org:443
      storage.googleapis.com:443
```

**Cargo (Rust):**

```yaml
- uses: step-security/harden-runner@v2
  with:
    egress-policy: block
    disable-sudo: true
    allowed-endpoints: >
      api.github.com:443
      github.com:443
      objects.githubusercontent.com:443
      crates.io:443
      index.crates.io:443
      static.crates.io:443
```

## Notes on Configuration

- `disable-sudo: true` prevents a compromised build step from escalating privileges to install persistent tooling on the runner. Safe for most workflows; disable only if your build genuinely requires sudo.
- The `allowed-endpoints` list is additive — add only what your build legitimately contacts. Any unlisted outbound connection is dropped in block mode, and an alert is raised.
- For private registries or GitHub Enterprise, add your registry hostname to the allowlist alongside the public endpoints.
- If using GitHub-hosted runners across multiple OSes, note that Harden-Runner supports Linux, macOS, and Windows runners with a unified policy view in the portal.
- The StepSecurity portal (`app.stepsecurity.io`) can auto-generate an `allowed-endpoints` policy from audit mode logs, which is the recommended way to build the initial allowlist rather than writing it by hand.

---

