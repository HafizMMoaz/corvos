<div align="center">

# Corvos

**The open-source, self-hostable AI research assistant.**

Turn your documents and the live web into a searchable knowledge base - then chat with it and get cited answers.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2)](https://discord.gg/Ggf9PxDNQ2)

</div>

---

Corvos pairs a NotebookLM-style research workspace with live web-data
connectors - Reddit, YouTube, Google Search, Google Maps, and any page on the
open web - exposed through a REST API and an MCP server so your own agents
can research alongside you.

## Why Corvos

- **Own your stack.** Self-host the whole platform for free, or use the
  hosted cloud version. No lock-in either way.
- **Ask the live web, not a stale index.** Connectors query platforms in
  real time and return typed, structured data - not scraped HTML.
- **Bring your own model.** 100+ LLMs via the OpenAI spec and LiteLLM, plus
  local/private models through vLLM or Ollama.

## Features

| | |
|---|---|
| **Knowledge base** | Upload PDFs, Office docs, images, and audio, or sync cloud drives. Hybrid semantic + full-text search with cited, Perplexity-style answers. |
| **Live web connectors** | Structured data from Reddit, YouTube, Instagram, TikTok, Amazon, Walmart, Google Maps, Google Search, Indeed, and any page on the open web - each a typed REST endpoint returning structured JSON. |
| **MCP server** | Every connector exposed as a native agent tool for Claude, Cursor, or any MCP-compatible client. |
| **Deliverables** | AI-generated reports (PDF, DOCX, HTML, LaTeX, EPUB), podcasts, slide decks, and images from your sources. |
| **Automations** | Scheduled and event-triggered agent runs, described in plain English. |
| **Collaboration** | Real-time shared chats with comments and role-based access control. |
| **Desktop app** | Native assist - global shortcut, text selection, screenshots, local folder sync. |

## Repository layout

| Directory | Description |
|---|---|
| [`backend/`](./backend) | Python FastAPI backend - agents, connectors, API (Celery, Alembic, PostgreSQL/PGVector) |
| [`web/`](./web) | Next.js web frontend (TypeScript, Tailwind, Drizzle ORM) |
| [`browser_extension/`](./browser_extension) | Browser extension for saving web content (Plasmo) |
| [`desktop/`](./desktop) | Electron desktop app |
| [`mcp/`](./mcp) | MCP server exposing connectors as agent tools |
| [`obsidian/`](./obsidian) | Obsidian plugin |
| [`evals/`](./evals) | Evaluation harness |
| [`docker/`](./docker) | Docker Compose configs and install scripts |

## Quick start (self-host)

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

```bash
cd docker
cp .env.example .env      # fill in your model API keys
docker compose up
```

The web app is served at `http://localhost:3000` and the backend API at
`http://localhost:8000` by default. See [`docker/`](./docker) for
development, GPU, and proxy variants.

## Local development

**Backend**
```bash
cd backend
uv sync
uv run main.py
```

**Frontend**
```bash
cd web
pnpm install
pnpm dev
```

Each component under `backend/`, `web/`, `browser_extension/`, `desktop/`,
`mcp/`, `obsidian/`, and `evals/` has its own README with setup details. See
[CLAUDE.md](./CLAUDE.md) for repo-wide conventions.

## Use the connectors over MCP

Add the MCP server to any MCP-compatible client:

```json
{
  "mcpServers": {
    "corvos": {
      "url": "http://localhost:8080/mcp",
      "headers": { "Authorization": "Bearer ${CORVOS_API_KEY}" }
    }
  }
}
```

Your agent can then call every connector as a native tool
(`corvos_reddit_scrape`, `corvos_google_search`, and more). Run the
server from [`mcp/`](./mcp).

## Community

- [Discord](https://discord.gg/Ggf9PxDNQ2) - chat with the team and other users
- [GitHub Discussions](https://github.com/HafizMMoaz/Corvos/discussions) - questions, ideas, roadmap
- [Twitter/X](https://x.com/HafizMMoaz) · [Reddit](https://www.reddit.com/r/Corvos/)

## Contributing

Contributions are welcome - see [CONTRIBUTING.md](./CONTRIBUTING.md). Please
also read our [Code of Conduct](./CODE_OF_CONDUCT.md) and
[Security Policy](./SECURITY.md).

## License

[MIT](./LICENSE) © Corvos Contributors
