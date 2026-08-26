# Contributing to Corvos

Thanks for your interest in contributing! Whether it's fixing bugs, suggesting features, improving docs, or joining the conversation - every bit helps.

## Before You Start

Check existing issues and discussions before opening a new one. For questions, open a GitHub Discussion.

## What Can You Work On?

1. **Pick from the roadmap** - look for issues in `Backlog` or `Ready` status on the [project board](https://github.com/HafizMMoaz/Corvos/projects)
2. **Propose something new** - open an issue first, wait for maintainer feedback, then start a PR
3. **Report or fix bugs** - include steps to reproduce, expected vs actual behavior, and environment details

## Branching Workflow

| Branch | Purpose |
|--------|---------|
| `main` | Stable/release - maintainers only |
| `dev` | Active development - all PRs target here |
| `feature/*`, `fix/*` | Your work branches, created from `dev` |

**All PRs must target `dev`.** PRs targeting `main` will not be accepted.

## Development Setup

**Prerequisites:** Docker & Docker Compose, Node.js 18+, Python 3.11+, PostgreSQL with PGVector

```bash
# Fork and clone
git clone https://github.com/<your-username>/Corvos.git
cd Corvos

# Branch from dev
git checkout dev && git pull origin dev
git checkout -b feature/your-feature-name
```

See [CLAUDE.md](./CLAUDE.md) for per-component setup commands.

## Code Style

- Python: PEP 8, formatted with Black
- TypeScript: Biome (`biome.json` at root and per-package)
- Commits: `feat:`, `fix:`, `docs:`, `refactor:` prefixes

## Pull Request Checklist

- [ ] Targets `dev` branch
- [ ] Linked to a related issue
- [ ] CI passes
- [ ] Docs updated if needed
- [ ] Screenshots included for UI changes

## License

By contributing, you agree your contributions are licensed under the [MIT License](./LICENSE).
