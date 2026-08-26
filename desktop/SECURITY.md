# Security Policy - Desktop

This policy covers the `desktop/` component of Corvos (the Electron app).
For the repo-wide policy, see the root [SECURITY.md](../SECURITY.md).

## Supported Versions

The desktop app is under active development. Security fixes are applied to
the latest release on the `main` branch. Please ensure you are running the
most recent published build before reporting an issue.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, report them privately using GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
feature (the **Security** tab → **Report a vulnerability**), or open a private
security advisory.

When reporting, please include:

- A description of the vulnerability and its potential impact (e.g. context
  isolation bypass, unsafe deep-link handling, local filesystem access)
- Steps to reproduce, or a proof of concept
- OS and app version
- Any relevant logs or environment details

## What to Expect

- We will acknowledge your report as soon as we are able.
- We will investigate and keep you informed of our progress.
- Once resolved, we will publish a fix and credit you, unless you prefer to
  remain anonymous.

## Best Practices for Self-Hosters

- Never commit secrets. Use `.env` (already gitignored) for API keys and
  OAuth configuration.
- Only install packaged builds from official releases; verify signatures
  where available.
- Keep dependencies and the bundled Electron runtime up to date.
