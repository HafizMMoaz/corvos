# Security Policy - Browser Extension

This policy covers the `browser_extension/` component of Corvos. For the
repo-wide policy, see the root [SECURITY.md](../SECURITY.md).

## Supported Versions

The extension is under active development. Security fixes are applied to the
latest release on the `main` branch. Please ensure you are running the most
recent published build before reporting an issue.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, report them privately using GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
feature (the **Security** tab → **Report a vulnerability**), or open a private
security advisory.

When reporting, please include:

- A description of the vulnerability and its potential impact (permission
  scope abuse, content-script injection, message-passing spoofing, etc.)
- Steps to reproduce, or a proof of concept
- Browser and extension version
- Any relevant logs or environment details

## What to Expect

- We will acknowledge your report as soon as we are able.
- We will investigate and keep you informed of our progress.
- Once resolved, we will publish a fix and credit you, unless you prefer to
  remain anonymous.

## Best Practices for Self-Hosters

- Never commit secrets. Use `.env` (already gitignored) for API keys.
- Review requested permissions in `manifest.json` before installing an
  unpacked build from a fork.
- Keep dependencies up to date and rebuild before submitting to a webstore.
