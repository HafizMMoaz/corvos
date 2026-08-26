# Contributing to the Corvos Obsidian Plugin

Thanks for your interest in contributing! This document covers setup and
conventions specific to `obsidian/`. For the repo-wide process (branching, PR
checklist, issue triage), see the root [CONTRIBUTING.md](../CONTRIBUTING.md).

## Development Setup

```bash
git checkout dev && git pull origin dev
git checkout -b feature/your-feature-name

cd obsidian
npm install
npm run dev   # esbuild in watch mode -> main.js
```

Symlink the folder into a test vault's `.obsidian/plugins/Corvos/`, enable
the plugin, then reload Obsidian whenever `main.js` rebuilds. See
[README.md](./README.md) for the full setup and sync behavior.

## Code Style

- TypeScript
- Run `npm run lint` before opening a PR
- Follow Obsidian's [developer policies](https://github.com/obsidianmd/obsidian-developer-docs/blob/main/en/Developer%20policies.md),
  especially around network requests (`requestUrl` only) and mobile support

## Releases

The release pipeline is triggered by tags of the form `obsidian-v0.1.0` and is
documented in [README.md](./README.md#development).

## Pull Requests

Follow the root [Pull Request Checklist](../CONTRIBUTING.md#pull-request-checklist).
All PRs target `dev`.

## License

By contributing, you agree your contributions are licensed under the
[MIT License](./LICENSE).
