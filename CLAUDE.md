# Corvos - CLAUDE.md

## Project Overview

Corvos is an open-source AI-powered research assistant. MIT licensed.

## Repository Structure

```
backend/          # Python FastAPI backend (uv, Alembic, Celery)
web/              # Next.js frontend (TypeScript, Drizzle ORM, Tailwind)
browser_extension/ # Browser extension (TypeScript, Plasmo)
desktop/          # Electron desktop app
mcp/              # MCP server (Python)
obsidian/         # Obsidian plugin (TypeScript)
evals/            # Evaluation harness (Python)
docker/           # Docker Compose configs and scripts
docs/             # Documentation
scripts/          # Version bump scripts
```

## Tech Stack

- **Backend**: Python, FastAPI, Celery, Alembic, PostgreSQL, uv
- **Frontend**: Next.js, TypeScript, Tailwind CSS, Drizzle ORM
- **Extension**: Plasmo framework, TypeScript
- **Desktop**: Electron
- **Infra**: Docker, OpenTelemetry, Caddy proxy

## Development

### Backend
```bash
cd backend
uv sync
uv run main.py
```

### Frontend
```bash
cd web
npm install
npm run dev
```

### Docker (full stack)
```bash
cd docker
docker compose up
```

## Conventions

- Python: follow existing style in `backend/app/`
- TypeScript: Biome for linting/formatting (`biome.json` at root and per-package)
- Migrations: Alembic in `backend/alembic/versions/`
- Env vars: copy `.env.example` files, never commit secrets

## License

MIT - see [LICENSE](./LICENSE)
