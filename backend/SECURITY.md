# Security Policy - Backend

This policy covers the `backend/` component of Corvos (the FastAPI API,
Celery workers, agents, and connectors). For the repo-wide policy, see the root
[SECURITY.md](../SECURITY.md).

## Supported Versions

The backend is under active development. Security fixes are applied to the
latest release on the `main` branch. Please ensure you are running the most
recent version before reporting an issue.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, report them privately using GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
feature (the **Security** tab → **Report a vulnerability**), or open a private
security advisory.

When reporting, please include:

- A description of the vulnerability and its potential impact
- Steps to reproduce, or a proof of concept
- Affected endpoint(s), connector(s), or module(s) in `backend/`
- Any relevant logs, versions, or environment details

## What to Expect

- We will acknowledge your report as soon as we are able.
- We will investigate and keep you informed of our progress.
- Once resolved, we will publish a fix and credit you, unless you prefer to
  remain anonymous.

## Best Practices for Self-Hosters

- Never commit secrets. Use `.env` (already gitignored) for API keys, DB
  credentials, and OAuth secrets.
- Restrict network access to the backend and PostgreSQL instance in production.
- Keep dependencies (`uv.lock`) and the base Docker image up to date.
- Rotate API keys, connector OAuth credentials, and JWT signing secrets
  regularly.
