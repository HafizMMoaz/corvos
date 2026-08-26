# Contributing to the Corvos Web App

Thanks for your interest in contributing to the frontend! This document covers
setup and conventions specific to `web/`. For the repo-wide process (branching,
PR checklist, issue triage), see the root [CONTRIBUTING.md](../CONTRIBUTING.md).

## Development Setup

**Prerequisites:** Node.js 18+, pnpm

```bash
git checkout dev && git pull origin dev
git checkout -b feature/your-feature-name

cd web
pnpm install
pnpm dev
```

## Code Style

- TypeScript, formatted and linted with Biome (`biome.json` at root and per-package)
- Tailwind CSS for styling - follow existing component patterns before adding new ones
- Run `pnpm lint` and `pnpm format` before opening a PR

## Docs, Blog, and Changelog

- Docs live in `content/docs/` (MDX)
- Blog posts live in `blog/content/` (MDX)
- Changelog entries live in `changelog/content/` (MDX) - one file per release

## Pull Requests

Follow the root [Pull Request Checklist](../CONTRIBUTING.md#pull-request-checklist).
All PRs target `dev`. Include screenshots for UI changes.

## License

By contributing, you agree your contributions are licensed under the
[MIT License](./LICENSE).
