# Corvos MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes
Corvos to MCP clients like **Claude Code**, **Cursor**, and **Claude Desktop**.
It talks to a Corvos backend purely over its REST API using a Corvos API
key - it imports no backend code.

Connect it two ways:

- **Hosted** (recommended) - point your client at `https://mcp.corvos.com/mcp`
  and pass your API key in a header. Nothing to install or keep running.
- **Self-host (stdio)** - run the server yourself against any backend (cloud or
  your own). Best for self-hosters and clients without remote-server support.

## Tools

**Search-space selector**
- `corvos_list_workspaces` - list the workspaces (search spaces) you can access
- `corvos_select_workspace` - pick the active workspace by name or id

**Scrapers (all platforms)**
- `web_crawl`, `corvos_google_search`, `corvos_reddit_scrape`,
  `corvos_youtube_scrape`, `corvos_youtube_comments`,
  `corvos_instagram_scrape`, `corvos_instagram_details`,
  `corvos_tiktok_scrape`, `corvos_tiktok_comments`,
  `corvos_tiktok_user_search`, `corvos_tiktok_trending`,
  `corvos_google_maps_scrape`, `corvos_google_maps_reviews`,
  `corvos_indeed_scrape`, `corvos_amazon_scrape`,
  `corvos_walmart_scrape`, `corvos_walmart_reviews`
- `corvos_list_scraper_runs`, `corvos_get_scraper_run` - retrieve past
  results in full (useful when a large result was truncated inline)

**Knowledge base**
- `corvos_search_knowledge_base` - semantic + keyword search over stored content
- `corvos_list_documents`, `corvos_get_document`
- `corvos_add_document`, `corvos_upload_file`
- `corvos_update_document`, `corvos_delete_document`

Workspace-scoped tools default to the active workspace; pass `workspace` (a name
or id) to override for a single call. Ids never need to be typed by hand - the
model carries them between calls.

## Get an API key

1. Corvos → **API Playground → API Keys**: create a personal key (`ss_pat_…`).
   It is shown only once.
2. Toggle **API key access** on for the workspace(s) you want to use.

## Connect (hosted)

Point your client at the hosted server and send the key as a Bearer token. For
clients that read an `mcpServers` map (Cursor, Claude Desktop, and others):

```json
{
  "mcpServers": {
    "corvos": {
      "url": "https://mcp.corvos.com/mcp",
      "headers": { "Authorization": "Bearer ss_pat_your_key_here" }
    }
  }
}
```

Claude Code, from a terminal:

```bash
claude mcp add --transport http corvos https://mcp.corvos.com/mcp \
  --header "Authorization: Bearer ss_pat_your_key_here"
```

Most MCP clients accept this `url` + `headers` form; check your client's docs for
its exact remote-server field.

## Self-host (stdio)

Run the server yourself when you host your own backend or use a client without
remote support. It uses [uv](https://github.com/astral-sh/uv):

```bash
cd mcp
uv sync
uv run python -m mcp_server.selfcheck   # verify tools register correctly
```

Then add it to your client. Cursor (`~/.cursor/mcp.json` or a project
`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "corvos": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/Corvos/mcp", "python", "-m", "mcp_server"],
      "env": {
        "CORVOS_BASE_URL": "http://localhost:8000",
        "CORVOS_API_KEY": "ss_pat_your_token_here"
      }
    }
  }
}
```

Claude Code:

```bash
claude mcp add corvos \
  -e CORVOS_BASE_URL=http://localhost:8000 \
  -e CORVOS_API_KEY=ss_pat_your_token_here \
  -- uv run --directory /absolute/path/to/Corvos/mcp python -m mcp_server
```

Claude Desktop: add the same `mcpServers` block as Cursor to
`claude_desktop_config.json` (Settings → Developer → Edit Config).

## Configuration

See `.env.example`. For self-host, secrets are passed as environment variables by
the client; never commit tokens.

## Backend dependency

`corvos_search_knowledge_base` calls `POST /api/v1/documents/search-semantic`,
a thin endpoint that exposes the backend's existing hybrid retriever over REST.
All other tools use pre-existing Corvos endpoints.
