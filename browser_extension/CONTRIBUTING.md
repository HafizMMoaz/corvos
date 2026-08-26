# Contributing to the Corvos Browser Extension

Thanks for your interest in contributing! This document covers setup and
conventions specific to `browser_extension/`. For the repo-wide process
(branching, PR checklist, issue triage), see the root
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Development Setup

**Prerequisites:** Node.js 18+, pnpm

```bash
git checkout dev && git pull origin dev
git checkout -b feature/your-feature-name

cd browser_extension
pnpm install
pnpm dev
```

Load the unpacked development build (e.g. `build/chrome-mv3-dev` for Chrome)
in your browser's extensions page. See [README.md](./README.md) for the full
[Plasmo](https://docs.plasmo.com/) workflow.

## Code Style

- TypeScript, formatted and linted with Biome
- Keep content scripts, background workers, and popup UI logic separated per
  Plasmo's conventions (`content.ts`, `background.ts`, `popup.tsx`)

## Pull Requests

Follow the root [Pull Request Checklist](../CONTRIBUTING.md#pull-request-checklist).
All PRs target `dev`. Include a screen recording or screenshots for UI/UX changes.

## License

By contributing, you agree your contributions are licensed under the
[MIT License](./LICENSE).
