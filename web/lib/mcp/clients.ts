/**
 * MCP client setup catalog: one entry per popular agent, each with a hosted
 * (remote) snippet and a self-host (stdio) snippet, plus the exact config file
 * and steps. Shared by the marketing /mcp-server page and the API playground so
 * the instructions can never drift apart.
 *
 * Remote snippets point at the hosted server and pass the key as a Bearer token;
 * every client's exact remote field is verified against its own docs (Windsurf
 * uses `serverUrl`, Gemini CLI `httpUrl`, VS Code needs `type: "http"`, OpenCode
 * `type: "remote"` + `oauth: false`, Codex needs the rmcp flag, and Claude
 * Desktop has no config-file remote support so it uses the `mcp-remote` bridge).
 */

export type McpTransport = "remote" | "stdio";

export interface McpSnippetOptions {
	/** Hosted MCP endpoint (Bearer-authenticated). */
	remoteUrl: string;
	/** API key value or placeholder to show in the snippet. */
	apiKey: string;
	/** Corvos backend URL a self-hosted server should call. */
	baseUrl: string;
	/** Absolute path to the mcp directory (self-host). */
	serverDir: string;
}

export interface McpSnippet {
	/** Where the snippet goes: a file path or "Terminal". */
	configFile: string;
	language: "json" | "toml" | "bash";
	steps: string[];
	build: (options: McpSnippetOptions) => string;
}

export interface McpClient {
	id: string;
	label: string;
	remote: McpSnippet;
	stdio: McpSnippet;
}

export const REMOTE_URL = "https://mcp.corvos.com/mcp";
export const DEFAULT_SERVER_DIR = "/path/to/Corvos/mcp";
export const API_KEY_PLACEHOLDER = "ss_pat_your_key_here";

function json(value: unknown): string {
	return JSON.stringify(value, null, 2);
}

function bearer(apiKey: string): string {
	return `Bearer ${apiKey}`;
}

function serverArgs(serverDir: string): string[] {
	return ["run", "--directory", serverDir, "python", "-m", "mcp_server"];
}

/** The `mcpServers` remote shape shared by Cursor, Windsurf, and Gemini CLI. */
function remoteMcpServers(urlField: "url" | "serverUrl" | "httpUrl") {
	return ({ remoteUrl, apiKey }: McpSnippetOptions): string =>
		json({
			mcpServers: {
				corvos: {
					[urlField]: remoteUrl,
					headers: { Authorization: bearer(apiKey) },
				},
			},
		});
}

/** The `mcpServers` stdio shape shared by Cursor, Claude Desktop, Windsurf, Gemini CLI. */
function stdioMcpServers({ baseUrl, apiKey, serverDir }: McpSnippetOptions): string {
	return json({
		mcpServers: {
			corvos: {
				command: "uv",
				args: serverArgs(serverDir),
				env: { CORVOS_BASE_URL: baseUrl, CORVOS_API_KEY: apiKey },
			},
		},
	});
}

export const MCP_CLIENTS: McpClient[] = [
	{
		id: "claude-code",
		label: "Claude Code",
		remote: {
			configFile: "Terminal",
			language: "bash",
			steps: [
				"Run this command in a terminal (any directory).",
				"Start Claude Code and run /mcp - corvos should be listed as connected.",
			],
			build: ({ remoteUrl, apiKey }) =>
				[
					`claude mcp add --transport http corvos ${remoteUrl} \\`,
					`  --header "Authorization: ${bearer(apiKey)}"`,
				].join("\n"),
		},
		stdio: {
			configFile: "Terminal",
			language: "bash",
			steps: [
				"Run this command in a terminal (any directory).",
				"Start Claude Code and run /mcp - corvos should be listed as connected.",
			],
			build: ({ baseUrl, apiKey, serverDir }) =>
				[
					"claude mcp add corvos \\",
					`  -e CORVOS_BASE_URL=${baseUrl} \\`,
					`  -e CORVOS_API_KEY=${apiKey} \\`,
					`  -- uv run --directory ${serverDir} python -m mcp_server`,
				].join("\n"),
		},
	},
	{
		id: "codex",
		label: "Codex",
		remote: {
			configFile: "~/.codex/config.toml",
			language: "toml",
			steps: [
				"Add this to ~/.codex/config.toml. The rmcp flag must sit above every [mcp_servers.*] table.",
				"Restart Codex; `codex mcp list` should show corvos.",
			],
			build: ({ remoteUrl, apiKey }) =>
				[
					"experimental_use_rmcp_client = true",
					"",
					"[mcp_servers.corvos]",
					`url = "${remoteUrl}"`,
					"",
					"[mcp_servers.corvos.http_headers]",
					`Authorization = "${bearer(apiKey)}"`,
				].join("\n"),
		},
		stdio: {
			configFile: "~/.codex/config.toml",
			language: "toml",
			steps: [
				"Add this to ~/.codex/config.toml (or run `codex mcp add corvos -- uv run --directory <dir> python -m mcp_server`).",
				"Restart Codex; `codex mcp list` should show corvos.",
			],
			build: ({ baseUrl, apiKey, serverDir }) =>
				[
					"[mcp_servers.corvos]",
					'command = "uv"',
					`args = ${JSON.stringify(serverArgs(serverDir))}`,
					"",
					"[mcp_servers.corvos.env]",
					`CORVOS_BASE_URL = "${baseUrl}"`,
					`CORVOS_API_KEY = "${apiKey}"`,
				].join("\n"),
		},
	},
	{
		id: "opencode",
		label: "OpenCode",
		remote: {
			configFile: "opencode.json",
			language: "json",
			steps: [
				"Add this to opencode.json in your project root (or ~/.config/opencode/opencode.json for all projects).",
				"`oauth: false` tells OpenCode to use the Bearer key instead of starting an OAuth flow.",
			],
			build: ({ remoteUrl, apiKey }) =>
				json({
					$schema: "https://opencode.ai/config.json",
					mcp: {
						corvos: {
							type: "remote",
							url: remoteUrl,
							enabled: true,
							oauth: false,
							headers: { Authorization: bearer(apiKey) },
						},
					},
				}),
		},
		stdio: {
			configFile: "opencode.json",
			language: "json",
			steps: [
				"Add this to opencode.json in your project root (or ~/.config/opencode/opencode.json for all projects).",
				"Note OpenCode's format: the key is `mcp`, the command is one array, and env vars go under `environment`.",
			],
			build: ({ baseUrl, apiKey, serverDir }) =>
				json({
					$schema: "https://opencode.ai/config.json",
					mcp: {
						corvos: {
							type: "local",
							command: ["uv", ...serverArgs(serverDir)],
							enabled: true,
							environment: { CORVOS_BASE_URL: baseUrl, CORVOS_API_KEY: apiKey },
						},
					},
				}),
		},
	},
	{
		id: "cursor",
		label: "Cursor",
		remote: {
			configFile: "~/.cursor/mcp.json",
			language: "json",
			steps: [
				"Add this to ~/.cursor/mcp.json (global, keeps the key out of your repo) or a project's .cursor/mcp.json.",
				"Refresh the server in Cursor Settings → MCP; its 18 tools should appear.",
			],
			build: remoteMcpServers("url"),
		},
		stdio: {
			configFile: "~/.cursor/mcp.json",
			language: "json",
			steps: [
				"Add this to ~/.cursor/mcp.json (global, keeps the key out of your repo) or a project's .cursor/mcp.json.",
				"Refresh the server in Cursor Settings → MCP; its 18 tools should appear.",
			],
			build: stdioMcpServers,
		},
	},
	{
		id: "claude-desktop",
		label: "Claude Desktop",
		remote: {
			configFile: "claude_desktop_config.json",
			language: "json",
			steps: [
				"Claude Desktop can't take a remote URL directly, so this uses the mcp-remote bridge (needs Node 18+).",
				"Open Settings → Developer → Edit Config, add this, and restart Claude Desktop.",
			],
			build: ({ remoteUrl, apiKey }) =>
				json({
					mcpServers: {
						corvos: {
							command: "npx",
							args: ["-y", "mcp-remote", remoteUrl, "--header", `Authorization: ${bearer(apiKey)}`],
						},
					},
				}),
		},
		stdio: {
			configFile: "claude_desktop_config.json",
			language: "json",
			steps: [
				"Open Settings → Developer → Edit Config to reach claude_desktop_config.json and add this.",
				"Restart Claude Desktop; corvos appears under the tools icon.",
			],
			build: stdioMcpServers,
		},
	},
	{
		id: "vscode",
		label: "VS Code",
		remote: {
			configFile: ".vscode/mcp.json",
			language: "json",
			steps: [
				"Add this to .vscode/mcp.json in your workspace (or run the MCP: Add Server command).",
				"VS Code requires an explicit `type` field - `http` for the hosted server.",
			],
			build: ({ remoteUrl, apiKey }) =>
				json({
					servers: {
						corvos: {
							type: "http",
							url: remoteUrl,
							headers: { Authorization: bearer(apiKey) },
						},
					},
				}),
		},
		stdio: {
			configFile: ".vscode/mcp.json",
			language: "json",
			steps: [
				"Add this to .vscode/mcp.json in your workspace (or run the MCP: Add Server command).",
				"Open Copilot Chat in agent mode and click the tools icon to confirm corvos is loaded.",
			],
			build: ({ baseUrl, apiKey, serverDir }) =>
				json({
					servers: {
						corvos: {
							type: "stdio",
							command: "uv",
							args: serverArgs(serverDir),
							env: { CORVOS_BASE_URL: baseUrl, CORVOS_API_KEY: apiKey },
						},
					},
				}),
		},
	},
	{
		id: "windsurf",
		label: "Windsurf",
		remote: {
			configFile: "~/.codeium/windsurf/mcp_config.json",
			language: "json",
			steps: [
				"Add this to ~/.codeium/windsurf/mcp_config.json (or Windsurf Settings → Cascade → MCP Servers).",
				"Windsurf uses `serverUrl` (not `url`) for remote servers; press refresh in the MCP panel.",
			],
			build: remoteMcpServers("serverUrl"),
		},
		stdio: {
			configFile: "~/.codeium/windsurf/mcp_config.json",
			language: "json",
			steps: [
				"Add this to ~/.codeium/windsurf/mcp_config.json (or Windsurf Settings → Cascade → MCP Servers).",
				"Press the refresh button in the MCP panel to pick up the server.",
			],
			build: stdioMcpServers,
		},
	},
	{
		id: "gemini-cli",
		label: "Gemini CLI",
		remote: {
			configFile: "~/.gemini/settings.json",
			language: "json",
			steps: [
				"Add this to ~/.gemini/settings.json (or .gemini/settings.json in a project).",
				"Gemini CLI uses `httpUrl` for streamable-HTTP servers; run /mcp to confirm corvos.",
			],
			build: remoteMcpServers("httpUrl"),
		},
		stdio: {
			configFile: "~/.gemini/settings.json",
			language: "json",
			steps: [
				"Add this to ~/.gemini/settings.json (or .gemini/settings.json in a project).",
				"Run /mcp inside Gemini CLI to confirm the corvos server and its tools.",
			],
			build: stdioMcpServers,
		},
	},
];
