# Contributing to the Corvos Backend

Thanks for your interest in contributing to the backend! This document covers
setup and conventions specific to `backend/`. For the repo-wide process
(branching, PR checklist, issue triage), see the root
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Development Setup

**Prerequisites:** Python 3.12+, [uv](https://github.com/astral-sh/uv), PostgreSQL with PGVector

```bash
git checkout dev && git pull origin dev
git checkout -b feature/your-feature-name

cd backend
uv sync
cp .env.example .env
uv run alembic upgrade head
uv run main.py
```

## Code Style

- Follow PEP 8, formatted with Black
- Follow existing patterns in `app/` for new routes, connectors, and agent tools
- Database schema changes go through an Alembic migration in `alembic/versions/`
- Never commit secrets - use `.env` (gitignored) for API keys and credentials

## Tests

```bash
uv run pytest
```

Add or update tests under `tests/` for any behavior change.

## Pull Requests

Follow the root [Pull Request Checklist](../CONTRIBUTING.md#pull-request-checklist).
All PRs target `dev`.

## License

By contributing, you agree your contributions are licensed under the
[MIT License](./LICENSE).
