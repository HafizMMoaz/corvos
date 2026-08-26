# Corvos Backend

Python FastAPI backend for Corvos - agents, connectors, knowledge base retrieval,
and the REST API consumed by `web/`, `desktop/`, `mcp/`, and `browser_extension/`.

## Stack

- **FastAPI** - HTTP API
- **Celery** - background jobs (indexing, connector sync, automations)
- **Alembic** - database migrations
- **PostgreSQL + PGVector** - relational storage and vector search
- **uv** - dependency management and task runner

## Layout

| Path | Description |
|---|---|
| `app/agents/` | Agent harness and tool-calling logic |
| `app/connectors/` | Live web and platform connectors (Reddit, YouTube, Google, etc.) |
| `app/retriever/` | Hybrid semantic + full-text retrieval over the knowledge base |
| `app/etl_pipeline/` | Document parsing, chunking, and embedding pipeline |
| `app/routes/` | FastAPI route definitions |
| `app/auth/` | Authentication and OAuth flows |
| `app/automations/` | Scheduled and event-triggered agent workflows |
| `app/proprietary/` | Platform-specific scraper implementations |
| `alembic/` | Database migrations |
| `tests/` | Test suite |

## Development

**Prerequisites:** Python 3.12+, [uv](https://github.com/astral-sh/uv), PostgreSQL with PGVector

```bash
cd backend
uv sync
cp .env.example .env   # fill in API keys and DB connection
uv run main.py
```

Run migrations:

```bash
uv run alembic upgrade head
```

Run the Celery worker (needed for indexing and background jobs):

```bash
uv run celery -A celery_app worker --loglevel=info
```

Run tests:

```bash
uv run pytest
```

See the root [CLAUDE.md](../CLAUDE.md) for conventions and the full local stack (Docker Compose).

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md), [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md), and
[SECURITY.md](./SECURITY.md).

## License

[MIT](./LICENSE) © Corvos Contributors
