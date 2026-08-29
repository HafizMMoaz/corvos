# Corvos - Explainer Scripts

Two spoken-word scripts for explaining this project. Part 1 is a ~90 second pitch.
Part 2 is the deep version that traces the system end to end.

---

# Script 1 - Short version (~90 seconds)

Corvos is an open-source, self-hostable AI research assistant. MIT licensed.

Think NotebookLM, but you run it, and it can reach the live web.

Two halves. First, a knowledge base: you drop in PDFs, Office docs, images, audio,
or sync a cloud drive, and it parses, chunks, embeds, and indexes everything into
Postgres with PGVector. Then you chat with it and get answers with citations back
to the source.

Second, live web connectors: Reddit, YouTube, Instagram, TikTok, Amazon, Walmart,
Google Maps, Google Search, Indeed, and any URL on the open web. Each one is a
typed REST endpoint that returns structured JSON, not a blob of scraped HTML.

Both halves are exposed three ways: through the web UI, through the REST API, and
through an MCP server, so Claude, Cursor, or your own agent can call
`corvos_reddit_scrape` or `corvos_search_knowledge_base` as a native tool.

On top of that it generates deliverables: reports as PDF, DOCX, HTML, LaTeX or
EPUB, plus podcasts, slide decks, and images from your own sources. Automations
run agents on a schedule or on an event, described in plain English. And
collaboration is real-time: shared chats, comments, role-based access.

The stack is a FastAPI backend with Celery workers, a Next.js frontend, and
clients for desktop, browser, and Obsidian. Models are pluggable through LiteLLM,
so 100-plus hosted LLMs or your own local vLLM or Ollama.

To run it: `cd docker`, copy the env file, `docker compose up`. That's the whole
install.

---

# Script 2 - Deep version

## Part 1 - What problem it solves

Research tools today force a split. Tools like NotebookLM are good at reasoning
over documents you already have, but they're walled gardens and they don't see the
live web. Scraping tools can reach the live web, but they hand you raw data with
no memory and no reasoning on top.

Corvos collapses that split into one system you own. Your documents and the
live web land in the same index, get searched the same way, and get cited the same
way. And because it's MIT licensed and self-hostable, your research corpus never
leaves your infrastructure unless you choose a hosted model provider.

## Part 2 - The shape of the repo

It's a monorepo with eight top-level pieces.

`backend/` is the brain: Python 3.12, FastAPI, Celery, Alembic, PostgreSQL with
PGVector, managed with `uv`.

`web/` is the Next.js frontend: Next 16 App Router, React 19, TypeScript,
Tailwind 4.

Then four clients and two support projects. `desktop/` is an Electron app.
`browser_extension/` is built on Plasmo. `obsidian/` is a vault plugin. `mcp/` is
a standalone MCP server. `evals/` is an evaluation harness. `docker/` holds the
compose files that tie it all together.

The important structural fact: the backend is the only thing that owns data.
Every client is a thin shell over the same REST API.

## Part 3 - The ingestion pipeline

Ingestion is two stages, and they're deliberately separate directories in the
code.

Stage one is `backend/app/etl_pipeline/` - turning a file into text. A
`file_classifier` decides what the file is, then hands it to one of the parsers in
`etl_pipeline/parsers/`. There are seven: `docling`, `unstructured`, `llamacloud`,
`azure_doc_intelligence`, `vision_llm`, `audio`, and `plaintext`, plus a
`direct_convert` fast path. Which document parser is used is a single env var,
`ETL_SERVICE`, set to `DOCLING`, `UNSTRUCTURED`, or `LLAMACLOUD`. Docling is the
default and runs entirely locally.

Audio goes through `faster-whisper` for transcription. Images and scanned pages
can go through `vision_llm` or a `picture_describer` that has an LLM write a
description of each figure, so charts and diagrams become searchable text instead
of dead pixels.

There's a cache layer under `etl_pipeline/cache/` with its own eligibility rules,
storage, persistence, and eviction. Parsing a 400-page PDF is expensive;
re-parsing the same file twice is waste.

Stage two is `backend/app/indexing_pipeline/`. `document_hashing` fingerprints
content, `document_chunker` splits it - the repo uses `chonkie` for chunking -
`document_embedder` produces vectors, and `document_persistence` writes them.
`chunk_reconciler` is the interesting one: when a document changes, it diffs
chunks instead of blowing away and re-embedding the whole document.

Embeddings are pluggable through `EMBEDDING_MODEL`. Default is local
`sentence-transformers/all-MiniLM-L6-v2`. You can point it at OpenAI, Cohere, or
an Ollama endpoint with a URL-style prefix.

## Part 4 - Retrieval

Retrieval lives in `backend/app/retriever/`, and it's just two files:
`chunks_hybrid_search.py` and `documents_hybrid_search.py`.

Hybrid means two signals combined: vector similarity through PGVector for semantic
matching, and Postgres full-text search for exact keyword matching. Pure vector
search misses literal strings like a product SKU or an error code. Pure keyword
search misses paraphrase. You want both.

Results then pass through `services/reranker_service.py` - the backend pulls in
the `rerankers` library with FlashRank - which reorders candidates by actual
relevance to the question before any of it reaches the model's context. That's the
step that turns "twenty vaguely related chunks" into "the five that answer the
question."

## Part 5 - The agent layer

This is the most sophisticated part of the codebase.

Under `backend/app/agents/chat/` there's `anonymous_chat/` for public
unauthenticated chats and `multi_agent_chat/` for the real thing. The stack is
LangChain 1.x, LangGraph 1.x, and `deepagents`, with `langchain-litellm`
underneath so any provider LiteLLM supports is available.

The architecture is a main agent plus a registry of subagents.
`multi_agent_chat/subagents/builtins/` has fourteen entries: `reddit`, `youtube`,
`instagram`, `tiktok`, `amazon`, `walmart`, `google_search`, `google_maps`,
`indeed`, `web_crawler`, `knowledge_base`, `memory`, `deliverables`, and
`mcp_discovery`. Alongside those, `subagents/connectors/` covers your integrated
SaaS tools and `subagents/mcp_tools/` covers external MCP servers you've
connected.

Why subagents instead of one agent with fifty tools? Context. A single agent
holding every tool schema for every platform burns its window before it starts
thinking. Delegating a task to a focused subagent keeps the main agent's context
clean and lets each subagent carry a deep, platform-specific prompt.

`multi_agent_chat/runtime/` handles the machinery: `checkpointer.py` persists
graph state - the backend uses `langgraph-checkpoint-postgres`, so a conversation
survives a restart. `prompt_caching.py` cuts token cost on repeated system
prompts. `mention_resolver.py` and `references/` resolve `@`-mentions of documents
and folders into real context. And `ToolOutputSpill` in the schema is a scratch
table for when a tool returns more than the context can hold - the agent spills it
and reads back what it needs.

`shared/middleware/` wraps tool calls. Two things there matter:
`AgentPermissionRule` means the agent asks before it does things you haven't
approved, and `AgentActionLog` plus `DocumentRevision` and `FolderRevision` mean
every mutating tool call is snapshotted first. There's a `revert_service` and an
`agent_revert_route` - the agent's file operations are undoable. That is not a
common thing to find in an agent codebase.

## Part 6 - Connectors and capabilities

There are two different things in this repo that both get called "connectors," and
it's worth separating them.

`backend/app/capabilities/` is the live web scraping layer: `reddit`, `youtube`,
`instagram`, `tiktok`, `amazon`, `walmart`, `google_search`, `google_maps`,
`indeed`, and generic `web`. Each is a typed capability returning structured JSON.
`capabilities/core/` gives all of them shared infrastructure: `runs.py` and
`store.py` record every invocation as a `Run` row, `progress.py` streams status,
`billing.py` meters usage, `validation.py` checks inputs, and `access/` enforces
who can call what. Under the hood the scraping uses `scrapling` with fetchers,
Playwright-family browser automation, `trafilatura` for article extraction, and
`youtube-transcript-api` for transcripts.

Because every run is persisted, a truncated result isn't lost - you can fetch it
back in full later. The MCP server exposes exactly that as
`corvos_list_scraper_runs` and `corvos_get_scraper_run`.

`backend/app/connectors/` is the other kind: your own accounts. Slack, Notion,
Jira, Confluence, Linear, ClickUp, Airtable, Discord, Teams, Luma, GitHub,
BookStack, Elasticsearch, Google Drive, Gmail, Calendar, Dropbox, OneDrive, and
Composio as a meta-connector for the long tail. Several have a paired
`_history.py` file for incremental sync - you re-index what changed, not the whole
workspace. Indexers live in `backend/app/tasks/connector_indexers/`, and OAuth
flows share `routes/oauth_connector_base.py`.

## Part 7 - Deliverables and automations

Research output isn't always a chat reply, so there's a generation layer.

Reports go through `services/export_service.py` using `typst` and `pypandoc` to
produce PDF, DOCX, HTML, LaTeX, and EPUB. Podcasts use `kokoro` for
text-to-speech in `services/kokoro_tts_service.py`, with `backend/app/podcasts/`
orchestrating script generation. `image_generation_routes.py` and
`services/image_gen_router_service.py` handle images.
`video_presentations_routes.py` plus `agents/video_presentation/` produce
slide-deck-style video presentations, tracked by a `VideoPresentation` model with
its own status enum.

Automations are in `backend/app/automations/`, and the design is clean:
`triggers/builtin/` has `schedule/` (cron, via `croniter`) and `event/`.
`actions/builtin/` currently has `agent_task/`. A `runtime/executor.py` with
`retries.py` and `step.py` runs them, and `templating/` is a sandboxed Jinja
environment with an explicit `allowlist.py` - so template expressions in an
automation can't reach arbitrary Python. That's the right instinct for
user-authored templates.

## Part 8 - Data model and access control

`backend/app/db.py` holds around thirty-five SQLAlchemy models. The core set:
`Workspace`, `Folder`, `Document`, `DocumentVersion`, `Chunk`, `NewChatThread`,
`NewChatMessage`, `Report`, `Prompt`, `Connection`, `Model`.

Access control is workspace-scoped RBAC: `WorkspaceRole`, `WorkspaceMembership`,
`WorkspaceInvite`, and a `Permission` enum, served by `rbac_routes.py`.

Auth is `fastapi-users` with JWT and `RefreshToken` rows, `AUTH_TYPE` switching
between local email/password and Google OAuth. For programmatic access there's
`PersonalAccessToken` - keys prefixed `ss_pat_` - which is what the MCP server,
the browser extension, and the Obsidian plugin authenticate with. There's a
middleware that tags PAT and MCP traffic separately in analytics, so machine calls
are distinguishable from human ones.

Collaboration: `ChatComment` and `ChatCommentMention` for threaded comments,
`ChatVisibility` and `PublicChatSnapshot` for sharing a chat publicly,
`ChatSessionState` for live session state.

## Part 9 - The frontend and real-time sync

The web app is Next.js 16 App Router with React 19, Tailwind 4, and
`@assistant-ui/react` for the chat surface.

The routes under `web/app/dashboard/[workspace_id]/` map to the feature set:
`chats` and `new-chat`, `connectors`, `artifacts` for generated deliverables,
`automations`, `logs`, `playground` for the API, `team`, `workspace-settings`,
`user-settings`, and an `onboard` flow.

The notable architectural choice is Rocicorp Zero. `zero-cache` replicates a
restricted set of Postgres tables - controlled by a logical-replication
publication called `zero_publication` - into a local replica and pushes changes to
the browser. So the frontend gets live data without polling and without the
backend writing a WebSocket layer by hand. The Next.js side owns almost no domain
data; there's a Drizzle setup but it covers only a marketing contact form. Query
authorization is resolved by the app itself at `/api/zero/query`, which is why the
compose file sets `ZERO_QUERY_URL` and forwards session cookies.

Note that `zero_publication` is validated at deploy time, not assumed - more on
that in a moment.

## Part 10 - The clients

Three clients, three different jobs, three different auth models.

The Electron desktop app in `desktop/src/` is unusual: there's no React renderer.
`modules/server.ts` forks the Next.js standalone build as a child process on a
local port, then points a window at it. So the desktop app is the web app, plus
native capabilities the browser can't offer: `quick-ask.ts` for a global shortcut
prompt, `general-assist.ts` for acting on selected text, `screen-capture/` for
screenshots, `folder-watcher.ts` using `chokidar` to sync local folders into the
knowledge base, `agent-filesystem.ts` for agent access to local files, `tray.ts`,
`auto-launch.ts`, `auto-updater.ts` via electron-updater, and `permissions.ts`
with `node-mac-permissions` for macOS screen-recording and accessibility prompts.
Auth is a loopback PKCE OAuth flow in `modules/oauth.ts` with tokens in
`secret-store.ts`.

The browser extension is Plasmo: `content.ts`, `popup.tsx`, and a small route set
including an `ApiKeyForm`. You paste a PAT, then save pages into the knowledge
base by POSTing to `/api/v1/documents`.

The Obsidian plugin has its own endpoint family, `/api/v1/obsidian/*`, with
`services/obsidian_plugin_indexer.py` on the backend. It turns a vault into a
searchable index, also PAT-authenticated.

## Part 11 - The MCP server

`mcp/` is a standalone project built on the official Python SDK's `FastMCP`. It
imports zero backend code - it talks to the REST API with an API key, which means
it can point at the hosted instance or at your own.

Two transports, selected by `RESEARCHOS_MCP_TRANSPORT`: `stdio` for local clients,
and `streamable-http` for remote. It runs stateless with SSE-style streaming
responses rather than buffered JSON, specifically so headers flush early and a
two-minute scrape doesn't trip a client timeout.

The tools split into three groups. Workspace selection:
`corvos_list_workspaces` and `corvos_select_workspace` - pick once, and
every later call defaults to it. Scrapers: `web_crawl`,
`corvos_google_search`, `corvos_reddit_scrape`,
`corvos_youtube_scrape` and `_comments`, `corvos_instagram_scrape` and
`_details`, four TikTok tools, two Google Maps tools, `corvos_indeed_scrape`,
`corvos_amazon_scrape`, `corvos_walmart_scrape` and `_reviews`, plus the
two run-history tools. Knowledge base: `corvos_search_knowledge_base`,
`corvos_list_documents`, `corvos_get_document`,
`corvos_add_document`, `corvos_upload_file`,
`corvos_update_document`, `corvos_delete_document`.

The server passes an `instructions` string to the model telling it to prefer these
typed tools over generic web search for those platforms - because structured
Reddit data beats a scraped Reddit page every time.

## Part 12 - Deployment

`docker/docker-compose.yml` defines the production stack under project name
`corvos`. Nine services, two commented out.

`db` is `pgvector/pgvector:pg17` with a tuned `postgresql.conf`. `redis:8-alpine`
with append-only persistence is the Celery broker and the app cache.

Then a detail worth calling out: `migrations` is a short-lived service that runs
`alembic upgrade head`, verifies the `zero_publication` replication publication
matches its canonical shape, and exits zero. Everything downstream gates on
`condition: service_completed_successfully`. So a failed migration halts the stack
rather than booting `zero-cache` against a drifted schema. That's a deliberate
choice to fail loudly instead of corrupting sync state.

The application services all run the same image with different `SERVICE_ROLE`
values: `backend` as `api`, `celery_worker` as `worker`, `celery_beat` as `beat`.
`frontend` is the Next.js image. `zero-cache` is `rocicorp/zero:1.6.0`.

The only thing published to your host is `proxy`, a Caddy container on port 3929
by default. Set `RESEARCHOS_SITE_ADDRESS` to a domain and `CERT_EMAIL`, and you
get automatic HTTPS with no cert wrangling. Everything else stays on the internal
Docker network, so browser traffic is same-origin and there are no CORS
gymnastics.

Compose overlays cover the variants: `.dev.yml`, `.deps-only.yml` for running app
code on your host against containerized Postgres and Redis, `.gpu.yml`,
`.proxy.yml`, and two e2e files. GPU support is a combination of
`RESEARCHOS_VARIANT` set to `cuda` or `cuda126` - which appends a suffix to the
image tag - plus the GPU overlay and the NVIDIA Container Toolkit on the host.
`docs/chinese-llm-setup.md` covers Chinese provider setup, and the `torch` extras
in `pyproject.toml` are split into `cpu`, `cu126`, and `cu128` as
mutually-exclusive uv extras.

Observability: OpenTelemetry instrumentation for FastAPI, SQLAlchemy, psycopg,
Redis, httpx, Celery, and logging is a hard dependency, with an `otel-collector`
service ready behind an `observability` profile. PostHog handles product
analytics.

Two self-hosting cautions worth flagging from the config. The compose defaults use
`corvos`/`corvos` for the Postgres credentials and a fixed default
`ZERO_ADMIN_PASSWORD`. Fine on a laptop, not fine on anything reachable. And
`TRUSTED_PROXIES` defaults to `0.0.0.0/0`; narrow it if you put a CDN or load
balancer in front. Both are called out in `.env.example`, but they're easy to skip
past.

## Part 13 - Evaluation

`evals/` is a separate uv project with real benchmark suites, not smoke tests.
Under `evals/src/evals/suites/`: `research/crag` and `research/frames` for
retrieval-augmented research quality, `medical/cure`, `medical/medxpertqa`, and
`medical/mirage` for domain QA, and `multimodal_doc/mmlongbench` plus
`multimodal_doc/parser_compare` for long multimodal documents.

`parser_compare` is the one to notice. Given that `ETL_SERVICE` lets you swap
between Docling, Unstructured, and LlamaCloud, there's a suite whose whole job is
measuring which parser actually gives better downstream answers on your
documents. The pluggability is backed by measurement rather than left as a shrug.

## Part 14 - Closing

So the through-line: one Postgres instance holding documents, chunks, vectors,
chat state, agent audit logs, and automation runs. A FastAPI layer that reads and
writes it. A Celery fleet doing the slow work - parsing, embedding, scraping,
generating. An agent runtime that fans out to focused subagents and logs every
action it takes so you can undo it. And four surfaces on top: web, desktop,
browser, and MCP.

The deliberate design choice is that no layer is a lock-in point. The models are
swappable through LiteLLM, down to fully local vLLM or Ollama. The parser is an
env var. The embedding model is an env var. The data is in your Postgres. The
license is MIT. If you stop liking any single piece, you replace that piece, not
the system.

Install is `cd docker`, `cp .env.example .env`, fill in your model keys,
`docker compose up`.
