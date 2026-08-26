# Contributing to the Corvos Desktop App

Thanks for your interest in contributing! This document covers setup and
conventions specific to `desktop/`. For the repo-wide process (branching, PR
checklist, issue triage), see the root [CONTRIBUTING.md](../CONTRIBUTING.md).

## Development Setup

**Prerequisites:** Node.js 18+, pnpm 10+, the `web` project dependencies
installed (`pnpm install` in `web/`)

```bash
git checkout dev && git pull origin dev
git checkout -b feature/your-feature-name

cd desktop
pnpm install
pnpm dev
```

See [README.md](./README.md) for the full build and packaging workflow
(`pnpm dist:mac` / `pnpm dist:win` / `pnpm dist:linux`).

## Code Style

- TypeScript, formatted and linted with Biome
- Keep main-process (Electron) and renderer (Next.js) concerns separated
- Never commit secrets - use `.env` (gitignored) for API keys and OAuth config

## Pull Requests

Follow the root [Pull Request Checklist](../CONTRIBUTING.md#pull-request-checklist).
All PRs target `dev`. Note the platform(s) you tested on (macOS/Windows/Linux)
for any packaging or native-integration change.

## License

By contributing, you agree your contributions are licensed under the
[MIT License](./LICENSE).
