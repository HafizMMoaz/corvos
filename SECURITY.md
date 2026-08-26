# Security Policy

## Supported Versions

Corvos is under active development. Security fixes are applied to the latest
release on the `main` branch. Please ensure you are running the most recent
version before reporting an issue.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, report them privately using GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
feature (the **Security** tab → **Report a vulnerability**), or open a private
security advisory.

When reporting, please include:

- A description of the vulnerability and its potential impact
- Steps to reproduce, or a proof of concept
- Affected component(s) (`backend`, `web`, `mcp`, `desktop`, etc.)
- Any relevant logs, versions, or environment details

## What to Expect

- We will acknowledge your report as soon as we are able.
- We will investigate and keep you informed of our progress.
- Once resolved, we will publish a fix and credit you, unless you prefer to
  remain anonymous.

## Scope

This policy covers the Corvos codebase in this repository. When
self-hosting, you are responsible for securing your own deployment, including
API keys, database access, network exposure, and any third-party services or
model providers you connect.

## Best Practices for Self-Hosters

- Never commit secrets. Use `.env` files (already gitignored) for API keys.
- Restrict network access to the backend and database in production.
- Keep dependencies and the base Docker images up to date.
- Rotate API keys and credentials regularly.
