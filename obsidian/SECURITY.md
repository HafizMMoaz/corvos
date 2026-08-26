# Security Policy - Obsidian Plugin

This policy covers the `obsidian/` component of Corvos (the Obsidian
community plugin). For the repo-wide policy, see the root
[SECURITY.md](../SECURITY.md).

## Supported Versions

The plugin is under active development. Security fixes are applied to the
latest published release. Please ensure you are running the most recent
version (via BRAT or manual sideload) before reporting an issue.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, report them privately using GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
feature (the **Security** tab → **Report a vulnerability**), or open a private
security advisory.

When reporting, please include:

- A description of the vulnerability and its potential impact (e.g. token
  storage, vault data exposure, unsafe network requests)
- Steps to reproduce, or a proof of concept
- Plugin version and platform (desktop/iOS/Android)
- Any relevant logs or environment details

## What to Expect

- We will acknowledge your report as soon as we are able.
- We will investigate and keep you informed of our progress.
- Once resolved, we will publish a fix and credit you, unless you prefer to
  remain anonymous.

## Data Handling

See [README.md § Privacy & safety](./README.md#privacy--safety) for the full
list of what the plugin sends and stores. In short: all network traffic goes
only to the **Server URL** you configure, over `requestUrl` (no `fetch`,
no `node:http`), and the API token is set per-request - never read from
cookies or other Obsidian state.

## Best Practices for Self-Hosters

- Never commit secrets. Personal access tokens are entered in plugin
  settings, not stored in the repo.
- Rotate your Corvos API token if you suspect it was exposed.
- Keep the plugin updated to pick up security fixes.
