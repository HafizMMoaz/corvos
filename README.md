<div align="center">

# Corvos

**The open-source, self-hostable AI research assistant.**

Turn your documents and the live web into a searchable knowledge base - then chat with it and get cited answers.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2)](https://discord.gg/Ggf9PxDNQ2)

</div>

---

## The Name

**Corvos** - from the Latin genus for ravens and crows (*Corvus*). Two syllables,
KOR-vos. The hard velar onset signals decisiveness; the rhotic carries depth;
the terminal *-vos* owns its phonemic space. Nothing else on a developer's
screen sounds like this.

In Norse mythology, Odin kept two ravens, **Huginn** (thought) and **Muninn**
(memory), that flew across the entire world each day, gathering intelligence
from every source and returning it to a single sovereign owner. That is
literally what this product does. Documents, Reddit, YouTube, Google, TikTok:
it sends agents out across everything and brings structured intelligence back
to you. Ravens are the most intelligent birds on earth: they use tools, cache
resources in hidden locations, and remember faces. Every one of those maps to a
feature.

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
| [`backend/`](./backend) | Python FastAPI backend - agents, connectors, REST API (Celery, Alembic, PostgreSQL + PGVector) |
| [`web/`](./web) | Next.js web frontend (TypeScript, Tailwind CSS, Drizzle ORM) |
| [`browser_extension/`](./browser_extension) | Cross-browser extension for saving web content (Plasmo) |
| [`desktop/`](./desktop) | Electron desktop app |
| [`mcp/`](./mcp) | MCP server exposing connectors as agent tools |
| [`obsidian/`](./obsidian) | Obsidian plugin for vault sync |
| [`evals/`](./evals) | Evaluation harness for benchmarking |
| [`docker/`](./docker) | Docker Compose configs for production and development |
| [`scripts/`](./scripts) | Native run scripts and utilities |

## Architecture

```mermaid
graph TB
    subgraph Clients["Clients"]
        Web["Web App<br/>Next.js + Zero-cache"]
        Desktop["Desktop<br/>Electron"]
        Extension["Browser Extension<br/>Plasmo"]
        MCP["MCP Clients<br/>Claude / Cursor"]
        Messaging["Messaging<br/>Telegram · WhatsApp<br/>Slack · Discord"]
    end

    subgraph API["API Layer"]
        Caddy["Caddy<br/>Reverse Proxy"]
        FastAPI["FastAPI<br/>REST + SSE Streaming"]
    end

    subgraph Core["Application Core"]
        Agents["Agent System<br/>LangChain · LangGraph<br/>Multi-Agent Orchestration"]
        Services["Services<br/>LLM Router · Streaming<br/>Memory · Billing"]
        Connectors["Connectors<br/>OAuth Sync · 15+ Platforms"]
        Platforms["Platform Scrapers<br/>YouTube · Reddit · Google<br/>Instagram · TikTok"]
    end

    subgraph Workers["Background Processing"]
        Celery["Celery Workers<br/>Document Processing<br/>Connector Indexing"]
        Beat["Celery Beat<br/>Scheduled Tasks<br/>Automations"]
        Gateway["Messaging Gateway<br/>Long-poll · Webhooks"]
    end

    subgraph Data["Data Layer"]
        PG["PostgreSQL 17<br/>+ PGVector"]
        Redis["Redis<br/>Broker · Cache"]
        Files["File Storage<br/>Local · Azure"]
        Zero["Zero-cache<br/>Real-time Sync"]
    end

    subgraph External["External"]
        LLM["100+ LLMs<br/>OpenAI · Anthropic<br/>Ollama · OpenRouter"]
        WebData["Live Web Data<br/>Reddit · YouTube<br/>Google · Amazon"]
        OAuth["OAuth Providers<br/>Google · Notion · Slack<br/>GitHub · Microsoft"]
    end

    Web & Desktop & Extension -->|HTTP / WS| Caddy
    MCP -->|MCP Protocol| Caddy
    Messaging -->|Webhook / Poll| Gateway

    Caddy --> FastAPI
    FastAPI --> Agents & Services & Connectors & Platforms

    Agents --> LLM
    Services --> PG & Redis
    Connectors --> OAuth
    Platforms --> WebData

    Agents & Services -->|enqueue| Redis
    Redis --> Celery & Beat
    Celery --> PG & Files
    Beat -->|schedule| Celery

    Zero -->|sync| PG
    Web -->|real-time| Zero

    Gateway --> FastAPI
```

For the full architectural blueprint covering every subsystem, data flow,
database schema, agent orchestration pattern, and deployment topology, see
[**docs/ARCHITECTURE_BLUEPRINT.md**](./docs/ARCHITECTURE_BLUEPRINT.md).

---

## Prerequisites

### Required for all setups

| Tool | Version | Install |
|---|---|---|
| **Git** | Any recent | [git-scm.com](https://git-scm.com/) |
| **Python** | 3.12+ | [python.org](https://www.python.org/downloads/) |
| **uv** | Latest | [docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) |
| **Node.js** | 20+ | [nodejs.org](https://nodejs.org/) |
| **pnpm** | 10.x | [pnpm.io/installation](https://pnpm.io/installation) |
| **PostgreSQL** | 17 + pgvector | [pgvector/pgvector](https://github.com/pgvector/pgvector) |
| **Redis** | 7+ | [redis.io](https://redis.io/docs/latest/operate/oss_and_stack/install/) |

### Additional for Docker setups

| Tool | Version | Install |
|---|---|---|
| **Docker Desktop** | Latest | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **NVIDIA Container Toolkit** | *(optional, GPU)* | [NVIDIA docs](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/) |

> **Platform notes**
> - **Windows:** Memurai is a drop-in Redis replacement. WSL2 is recommended for the native path.
> - **macOS:** Postgres.app + `brew install redis` is the simplest local setup.
> - **Linux:** Use your distro's package manager or the upstream apt/yum repos.

---

## Quick start

### Option A - Docker (recommended for self-hosting)

Docker is the fastest way to get the full stack running. All infrastructure
(PostgreSQL, Redis, zero-cache, Caddy reverse proxy) is handled automatically.

```bash
cd docker
cp .env.example .env        # edit the required values (see below)
docker compose up -d
```

Open **http://localhost:3929** - Caddy routes to the frontend, backend, and
zero-cache internally.

For development with hot reload, pgAdmin, and Grafana observability:

```bash
docker compose -f docker/docker-compose.dev.yml up --build
```

See [Docker development](#docker-development) for GPU and dev tool details.

---

### Option B - Native development (recommended for contributors)

Native development gives you hot reload on both the backend and frontend
without container rebuilds. You run PostgreSQL and Redis yourself, then start
the Corvos services directly.

#### 1. Clone and configure

```bash
git clone https://github.com/HafizMMoaz/Corvos.git
cd Corvos
```

**Backend** - copy the env template and fill in the required variables:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env - see Environment Variables below for what to set
```

**Web** - copy the env template:

```bash
cp web/.env.example web/.env
# Edit web/.env - at minimum set CORVOS_BACKEND_INTERNAL_URL=http://localhost:8000
```

#### 2. Install dependencies

```bash
# Backend (Python)
cd backend
uv sync
cd ..

# Frontend (Node.js)
cd web
pnpm install
cd ..
```

#### 3. Run database migrations

```bash
cd backend
uv run alembic upgrade head
cd ..
```

#### 4. Start all services

<details>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
.\scripts\start-native.ps1           # all services
.\scripts\start-native.ps1 -Service api  # just one
```

Logs are written to `scripts/logs/*.out` and `scripts/logs/*.err`.

> The Windows script uses `--pool=threads` for Celery because the prefork
> pool relies on `fork()`, which is not available on Windows.

</details>

<details>
<summary><strong>macOS & Linux (Bash)</strong></summary>

Make the script executable once, then run it:

```bash
chmod +x scripts/start-native.sh
./scripts/start-native.sh            # all services
./scripts/start-native.sh --api      # just one
./scripts/start-native.sh --stop     # stop all running services
```

Logs are written to `scripts/logs/<service>.{out,err}`.
PID files are written to `scripts/logs/<service>.pid` so you can stop
individual services with `kill $(cat scripts/logs/api.pid)`.

> On Linux/macOS the Celery worker uses the default prefork pool with
> `--autoscale=4,1`, which is more efficient than the thread pool used on
> Windows.

</details>

<details>
<summary><strong>Manual (any platform)</strong></summary>

Open separate terminals for each service:

```bash
# Terminal 1 - Backend API
cd backend && uv run python main.py

# Terminal 2 - Celery worker
cd backend && uv run celery -A app.celery_app worker \
  --loglevel=info --autoscale=4,1 --prefetch-multiplier=1 -Ofair \
  --queues=corvos,corvos.connectors,corvos.gateway

# Terminal 3 - Celery beat
cd backend && uv run celery -A app.celery_app beat --loglevel=info

# Terminal 4 - Zero-cache (real-time sync)
cd web && pnpm exec zero-cache

# Terminal 5 - Next.js dev server
cd web && pnpm dev
```

On Windows, replace `--autoscale=4,1` with `--pool=threads --concurrency=4`.

</details>

Once running:

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Zero-cache | http://localhost:4848 |

---

## Environment variables reference

Each component has its own `.env.example`. The tables below cover the
**backend** variables, which is where the bulk of the configuration lives.

### Legend

- **Required** - the app will not start or will misbehave without this.
- **Optional** - safe defaults are built in; set only to override.
- **Conditional** - required only when a specific feature is enabled.

---

### Always required

| Variable | Example | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@localhost:5432/corvos` | PostgreSQL connection string with the `asyncpg` driver. |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis endpoint for the Celery broker, result backend, and app cache. |
| `SECRET_KEY` | *(random 32+ char string)* | Session signing key. Generate with `openssl rand -base64 32`. |

---

### Core settings (optional but commonly overridden)

| Variable | Default | Description |
|---|---|---|
| `CORVOS_ENV` | `dev` | Deployment environment: `dev` or `production`. |
| `AUTH_TYPE` | `LOCAL` | Auth method: `LOCAL` (email/password) or `GOOGLE` (OAuth). |
| `REGISTRATION_ENABLED` | `TRUE` | Allow new user sign-ups. Set `FALSE` to lock to existing users. |
| `NEXT_FRONTEND_URL` | `http://localhost:3000` | Frontend URL for OAuth callbacks and CORS. |
| `BACKEND_URL` | *(unset)* | Public backend URL - set when behind a reverse proxy with HTTPS. |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model for vector search. Supports `openai://`, `cohere://`, `litellm://ollama/` prefixes. |
| `EMBEDDING_BASE_URL` | *(unset)* | Custom endpoint for OpenAI-compatible embedding APIs (e.g. Ollama). |
| `ETL_SERVICE` | `DOCLING` | Document parser: `DOCLING` (free, local), `UNSTRUCTURED`, or `LLAMACLOUD`. |
| `FILE_STORAGE_BACKEND` | `local` | Where to persist uploaded file bytes: `local` or `azure`. |

---

### Authentication - Google OAuth *(set when `AUTH_TYPE=GOOGLE`)*

| Variable | Required | Enables |
|---|---|---|
| `GOOGLE_OAUTH_CLIENT_ID` | Yes | Google sign-in |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Yes | Google sign-in |
| `GOOGLE_DESKTOP_CLIENT_ID` | For desktop app | Desktop app Google sign-in |
| `GOOGLE_DESKTOP_CLIENT_SECRET` | For desktop app | Desktop app Google sign-in |
| `GOOGLE_PICKER_API_KEY` | For Google Drive connector | Google Drive file picker |

---

### Connector OAuth credentials *(optional - set the ones you use)*

Each connector enables a live data source. Omit any you don't need.

| Connector | Variables | What it enables |
|---|---|---|
| **Google Calendar** | `GOOGLE_CALENDAR_REDIRECT_URI` + Google OAuth creds | Sync calendar events |
| **Gmail** | `GOOGLE_GMAIL_REDIRECT_URI` + Google OAuth creds | Sync emails |
| **Google Drive** | `GOOGLE_DRIVE_REDIRECT_URI` + Google OAuth creds + `GOOGLE_PICKER_API_KEY` | Sync Drive files |
| **Notion** | `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`, `NOTION_REDIRECT_URI` | Sync Notion pages |
| **Slack** | `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_REDIRECT_URI` | Sync Slack messages |
| **Discord** | `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`, `DISCORD_BOT_TOKEN` | Sync Discord messages |
| **Atlassian (Jira + Confluence)** | `ATLASSIAN_CLIENT_ID`, `ATLASSIAN_CLIENT_SECRET`, `JIRA_REDIRECT_URI`, `CONFLUENCE_REDIRECT_URI` | Sync Jira issues + Confluence pages |
| **Linear** | `LINEAR_CLIENT_ID`, `LINEAR_CLIENT_SECRET`, `LINEAR_REDIRECT_URI` | Sync Linear issues |
| **ClickUp** | `CLICKUP_CLIENT_ID`, `CLICKUP_CLIENT_SECRET`, `CLICKUP_REDIRECT_URI` | Sync ClickUp tasks |
| **Airtable** | `AIRTABLE_CLIENT_ID`, `AIRTABLE_CLIENT_SECRET`, `AIRTABLE_REDIRECT_URI` | Sync Airtable bases |
| **Microsoft (Teams + OneDrive)** | `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `TEAMS_REDIRECT_URI`, `ONEDRIVE_REDIRECT_URI` | Sync Teams + OneDrive |
| **Dropbox** | `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_REDIRECT_URI` | Sync Dropbox files |
| **Composio** | `COMPOSIO_API_KEY`, `COMPOSIO_ENABLED`, `COMPOSIO_REDIRECT_URI` | 100+ app integrations via Composio |

---

### TTS / STT *(optional - enables voice features)*

| Variable | Default | Enables |
|---|---|---|
| `TTS_SERVICE` | `local/kokoro` | Text-to-speech engine. Use `local/kokoro` for free local TTS, or `elevenlabs/eleven_turbo_v2_5` for cloud. |
| `TTS_SERVICE_API_KEY` | *(unset)* | API key for cloud TTS providers (ElevenLabs, OpenAI). |
| `STT_SERVICE` | `local/base` | Speech-to-text. Use `local/base` (Faster-Whisper) for local, or `openai/whisper-1` for cloud. |
| `STT_SERVICE_API_KEY` | *(unset)* | API key for cloud STT providers. |
| `ELEVENLABS_API_KEY` | *(unset)* | Enables ElevenLabs voice agent (high-quality multilingual TTS + voice chat). |

---

### Rerankers *(optional - improves search relevance)*

| Variable | Default | Description |
|---|---|---|
| `RERANKERS_ENABLED` | `FALSE` | Enable semantic reranking on search results. |
| `RERANKERS_MODEL_NAME` | `ms-marco-MiniLM-L-12-v2` | Reranker model name. |
| `RERANKERS_MODEL_TYPE` | `flashrank` | Reranker backend (`flashrank`, `cross-encoder`, etc.). |

---

### Messaging gateway *(optional - enables chat integrations)*

Set `GATEWAY_ENABLED=TRUE` and configure the channels you want:

| Channel | Key variables | Enables |
|---|---|---|
| **Telegram** | `TELEGRAM_SHARED_BOT_TOKEN`, `TELEGRAM_SHARED_BOT_USERNAME`, `TELEGRAM_WEBHOOK_SECRET` | Chat with Corvos via Telegram bot |
| **WhatsApp** | `WHATSAPP_SHARED_BUSINESS_TOKEN`, `WHATSAPP_SHARED_PHONE_NUMBER_ID`, `WHATSAPP_SHARED_WABA_ID` | Chat via WhatsApp (Meta Cloud API) |
| **Slack** | `GATEWAY_SLACK_ENABLED`, `GATEWAY_SLACK_SIGNING_SECRET` | Chat via Slack app |
| **Discord** | `GATEWAY_DISCORD_ENABLED`, `DISCORD_BOT_TOKEN` | Chat via Discord bot |

---

### Billing / credit wallet *(optional - for hosted/SaaS deployments)*

| Variable | Default | Enables |
|---|---|---|
| `STRIPE_SECRET_KEY` | *(unset)* | Stripe payments for credit packs |
| `STRIPE_WEBHOOK_SECRET` | *(unset)* | Stripe webhook verification |
| `STRIPE_CREDIT_BUYING_ENABLED` | `FALSE` | Allow users to buy credit packs |
| `ETL_CREDIT_BILLING_ENABLED` | `FALSE` | Debit wallet for document processing |
| `DEFAULT_CREDIT_MICROS_BALANCE` | `5000000` | Starting balance for new users ($5.00) |

---

### Web crawling / proxy *(optional - improves connector reliability)*

| Variable | Default | Enables |
|---|---|---|
| `PROXY_URL` | *(unset)* | HTTP proxy for web crawling. Leave unset to crawl directly. |
| `PROXY_URLS` | *(unset)* | Comma-separated proxy pool for rotation. |
| `PROXY_PROVIDER` | `custom` | Proxy provider: `custom` or `dataimpulse`. |
| `CAPTCHA_SOLVING_ENABLED` | `FALSE` | Enable automated captcha solving (Capsolver / 2Captcha). |
| `CAPTCHA_SOLVER_PROVIDER` | `capsolver` | Captcha solving vendor. |
| `CAPTCHA_SOLVER_API_KEY` | *(unset)* | API key for the captcha solver. |

---

### Observability *(optional)*

| Variable | Default | Enables |
|---|---|---|
| `LANGSMITH_TRACING` | *(unset)* | LangSmith trace export for agent debugging. |
| `LANGSMITH_API_KEY` | *(unset)* | LangSmith API key. |
| `CORVOS_ENABLE_OTEL` | *(unset)* | OpenTelemetry traces and metrics. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | *(unset)* | OTel collector endpoint (e.g. `http://otel-collector:4317`). |
| `POSTHOG_API_KEY` | *(unset)* | PostHog product analytics (server-side). |

---

### Feature flags *(optional - advanced agent capabilities)*

| Variable | Default | Description |
|---|---|---|
| `CORVOS_ENABLE_SKILLS` | `false` | Enable agent skills system |
| `CORVOS_ENABLE_SPECIALIZED_SUBAGENTS` | `false` | Enable multi-agent orchestration |
| `CORVOS_ENABLE_PERMISSION` | `false` | Enable tool-call permission prompts |
| `CORVOS_ENABLE_CONTEXT_EDITING` | `false` | Enable in-chat context editing |
| `CORVOS_ENABLE_COMPACTION_V2` | `false` | Enable conversation compaction |
| `CORVOS_ENABLE_MODEL_FALLBACK` | `false` | Auto-fallback to cheaper models |
| `CORVOS_ENABLE_ACTION_LOG` | `false` | Enable action logging for snapshot/revert |

---

## Docker development

### Development compose (with dev tools)

The dev compose file builds from source, includes hot reload via volume
mounts, and adds pgAdmin and a Grafana OTel LGTM stack:

```bash
docker compose -f docker/docker-compose.dev.yml up --build
```

| Tool | URL |
|---|---|
| Frontend (dev) | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| pgAdmin | http://localhost:5050 |
| Grafana (OTel) | http://localhost:3001 |

### GPU acceleration

For faster local embeddings, TTS, and STT, enable GPU support:

```bash
# Linux / macOS
CORVOS_VARIANT=cuda COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml docker compose up -d

# Windows (note the semicolon separator)
set CORVOS_VARIANT=cuda
set COMPOSE_FILE=docker-compose.yml;docker-compose.gpu.yml
docker compose up -d
```

Requires the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/) on the host. Use `cuda126` for older NVIDIA driver stacks.

---

## MCP server

Expose every Corvos connector as a native tool for Claude, Cursor, or any
MCP-compatible client:

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

Your agent can then call tools like `corvos_reddit_scrape`,
`corvos_google_search`, `corvos_youtube_transcript`, and more.
See [`mcp/`](./mcp) for setup and the full tool list.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `asyncpg` connection refused | PostgreSQL not running | Start Postgres: `pg_ctl start` / `brew services start postgresql` |
| `redis.exceptions.ConnectionError` | Redis not running | Start Redis: `redis-server` / `brew services start redis` |
| Celery worker exits on Windows | Using prefork pool | Add `--pool=threads --concurrency=4` (the start script handles this) |
| `alembic` migration fails | Schema out of sync | Run `uv run alembic upgrade head` from `backend/` |
| Zero-cache EACCES on Windows | Hyper-V port reservation | The start script uses port 6848 to avoid this; or run `netsh interface ipv4 show excludedportrange protocol=tcp` |
| Port 4848 in use | Another service on that port | Set `ZERO_PORT=6848` (or any free port) before starting zero-cache |

---

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

---

<div align="center">

### Philosophy

> *"If I had 60 minutes to solve a problem, I would spend 59 minutes
> understanding it and 1 minute resolving it."*
> attributed to Albert Einstein

Corvos was built on this principle. **90% of the effort went into understanding
and planning**, mapping every data flow, every edge case, every integration
boundary, and **10% went into building it.** The construction was delegated to
AI subagents, each scoped to a well-defined task with clear inputs, outputs,
and constraints. The same multi-agent orchestration that powers Corvos for
end-users powered its own development: an orchestrator decomposed the problem,
specialist subagents executed, and the result was reviewed and integrated by a
human in the loop.

Understanding first. Building second. That's the Corvos way.

</div>
