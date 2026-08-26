# Contributing to the Corvos MCP Server

Thanks for your interest in contributing! This document covers setup and
conventions specific to `mcp/`. For the repo-wide process (branching, PR
checklist, issue triage), see the root [CONTRIBUTING.md](../CONTRIBUTING.md).

## Development Setup

**Prerequisites:** Python 3.11+, [uv](https://github.com/astral-sh/uv), a
running Corvos backend (or a hosted API key)

```bash
git checkout dev && git pull origin dev
git checkout -b feature/your-feature-name

cd mcp
uv sync
cp .env.example .env
uv run python -m mcp_server.selfcheck   # verify tools register correctly
```

## Code Style

- Python, PEP 8, formatted with Black
- New tools call the backend REST API only - do not import backend code
  (the server ships in its own venv and must stay decoupled)
- Document new tools in [README.md](./README.md)'s tool list

## Pull Requests

Follow the root [Pull Request Checklist](../CONTRIBUTING.md#pull-request-checklist).
All PRs target `dev`.

## License

By contributing, you agree your contributions are licensed under the
[MIT License](./LICENSE).
