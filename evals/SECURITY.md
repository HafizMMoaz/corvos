# Security Policy - Evals

This policy covers the `evals/` component of Corvos (the benchmark
harness). For the repo-wide policy, see the root [SECURITY.md](../SECURITY.md).

## Supported Versions

The eval harness is under active development. Security fixes are applied to
the latest release on the `main` branch.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, report them privately using GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
feature (the **Security** tab → **Report a vulnerability**), or open a private
security advisory.

When reporting, please include:

- A description of the vulnerability and its potential impact
- Steps to reproduce, or a proof of concept
- Affected benchmark/suite under `evals/`
- Any relevant logs or environment details

## What to Expect

- We will acknowledge your report as soon as we are able.
- We will investigate and keep you informed of our progress.
- Once resolved, we will publish a fix and credit you, unless you prefer to
  remain anonymous.

## Best Practices

- Never commit secrets. Use `evals/.env` (gitignored) for
  `Corvos_API_KEY`, `OPENROUTER_API_KEY`, and login credentials.
- Point `Corvos_API_BASE` at a non-production backend when running
  benchmarks against untrusted datasets.
- Datasets and rendered PDFs are cached under `data/` - do not commit them.
