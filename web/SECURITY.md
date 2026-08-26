# Security Policy - Web

This policy covers the `web/` component of Corvos (the Next.js frontend,
including the marketing site, docs, and app UI). For the repo-wide policy, see
the root [SECURITY.md](../SECURITY.md).

## Supported Versions

The web app is under active development. Security fixes are applied to the
latest release on the `main` branch. Please ensure you are running the most
recent version before reporting an issue.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, report them privately using GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
feature (the **Security** tab → **Report a vulnerability**), or open a private
security advisory.

When reporting, please include:

- A description of the vulnerability and its potential impact (XSS, CSRF,
  auth bypass, etc.)
- Steps to reproduce, or a proof of concept
- Affected route(s) or component(s) in `web/`
- Any relevant logs, browser, or environment details

## What to Expect

- We will acknowledge your report as soon as we are able.
- We will investigate and keep you informed of our progress.
- Once resolved, we will publish a fix and credit you, unless you prefer to
  remain anonymous.

## Best Practices for Self-Hosters

- Never commit secrets. Use `.env` (already gitignored) for API keys and
  session secrets.
- Serve the app over HTTPS in production; several auth flows require it.
- Keep dependencies up to date (`pnpm audit`).
- Restrict `NEXT_PUBLIC_API_URL` and CORS configuration to trusted origins.
