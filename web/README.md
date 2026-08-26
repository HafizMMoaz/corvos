# Corvos Web

Next.js frontend for Corvos - the chat and knowledge base UI, connector
management, marketing site, and docs.

## Stack

- **Next.js** (App Router) + TypeScript
- **Tailwind CSS**
- **Drizzle ORM**
- **Biome** for linting/formatting
- **Fumadocs** for `/docs`, `/blog`, and `/changelog`

## Development

**Prerequisites:** Node.js 18+, pnpm

```bash
cd web
pnpm install
pnpm dev
```

The app runs at `http://localhost:3000`. It expects the backend
(see [`backend/`](../backend)) running at `http://localhost:8000` - set
`NEXT_PUBLIC_API_URL` in `.env` if it's running elsewhere.

## Scripts

```bash
pnpm dev       # dev server
pnpm build     # production build
pnpm lint      # Biome check
pnpm format    # Biome format
```

## Layout

| Path | Description |
|---|---|
| `app/` | Routes (App Router) |
| `components/` | UI components |
| `content/docs/` | Documentation content (MDX) |
| `blog/content/` | Blog post content (MDX) |
| `changelog/content/` | Changelog entries (MDX) |
| `lib/` | Shared utilities, API clients |
| `hooks/` | React hooks |

See the root [CLAUDE.md](../CLAUDE.md) for repo-wide conventions.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md), [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md), and
[SECURITY.md](./SECURITY.md).

## License

[MIT](./LICENSE) © Corvos Contributors
