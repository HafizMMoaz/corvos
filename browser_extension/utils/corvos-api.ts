import { buildBackendUrl } from "./backend-url";

/**
 * Backend client for the Corvos browser extension.
 *
 * All calls authenticate with the user's Personal Access Token (PAT) as a
 * Bearer token - the same principal the popup already uses for
 * `/verify-token`, `/api/v1/workspaces` and `/api/v1/documents`.
 */

export interface CorvosWorkspace {
	id: number;
	name: string;
	description?: string | null;
}

export interface CorvosThread {
	id: number;
	title: string;
	workspace_id: number;
	archived: boolean;
	updated_at?: string;
	created_at?: string;
}

export interface CorvosMessage {
	id: number;
	role: string;
	content: unknown;
	created_at?: string;
}

export interface ExtensionDocumentItem {
	metadata: {
		BrowsingSessionId: string;
		VisitedWebPageURL: string;
		VisitedWebPageTitle: string;
		VisitedWebPageDateWithTimeInISOString: string;
		VisitedWebPageReffererURL: string;
		VisitedWebPageVisitDurationInMilliseconds: string;
	};
	pageContent: string;
}

/** SSE event shapes the sidepanel chat cares about (see web/lib/chat/streaming-state.ts). */
export type ChatStreamEvent =
	| { type: "text-delta"; delta: string }
	| { type: "reasoning-delta"; delta: string }
	| { type: "reasoning-end" }
	| { type: "start-step" }
	| { type: "finish-step" }
	| { type: "error"; errorText?: string; errorCode?: string };

async function authedRequest(
	token: string,
	path: string,
	init?: RequestInit
): Promise<Response> {
	const response = await fetch(await buildBackendUrl(path), {
		...init,
		headers: {
			...(init?.headers ?? {}),
			Authorization: `Bearer ${token}`,
		},
	});
	if (!response.ok) {
		let detail = `${response.status}`;
		try {
			const body = await response.json();
			if (body?.detail) detail = String(body.detail);
		} catch {
			// non-JSON error body
		}
		throw new Error(detail);
	}
	return response;
}

export async function verifyToken(token: string): Promise<boolean> {
	const response = await fetch(await buildBackendUrl("/verify-token"), {
		headers: { Authorization: `Bearer ${token}` },
	});
	return response.ok;
}

export async function listWorkspaces(token: string): Promise<CorvosWorkspace[]> {
	const response = await authedRequest(token, "/api/v1/workspaces");
	return (await response.json()) as CorvosWorkspace[];
}

export async function createThread(
	token: string,
	workspaceId: number,
	title: string
): Promise<CorvosThread> {
	const response = await authedRequest(token, "/api/v1/threads", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			workspace_id: workspaceId,
			title,
		}),
	});
	return (await response.json()) as CorvosThread;
}

export async function listThreads(
	token: string,
	workspaceId: number
): Promise<CorvosThread[]> {
	const response = await authedRequest(
		token,
		`/api/v1/threads?workspace_id=${workspaceId}`
	);
	const body = (await response.json()) as {
		threads: CorvosThread[];
		archived_threads: CorvosThread[];
	};
	return body.threads ?? [];
}

export async function loadThreadMessages(
	token: string,
	threadId: number
): Promise<CorvosMessage[]> {
	const response = await authedRequest(token, `/api/v1/threads/${threadId}`);
	const body = (await response.json()) as { messages: CorvosMessage[] };
	return body.messages ?? [];
}

export async function saveExtensionDocuments(
	token: string,
	workspaceId: number,
	content: ExtensionDocumentItem[]
): Promise<{ message?: string; status?: string }> {
	const response = await authedRequest(token, "/api/v1/documents", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			document_type: "EXTENSION",
			workspace_id: workspaceId,
			content,
		}),
	});
	return (await response.json()) as { message?: string; status?: string };
}

/**
 * Stream a chat turn from `POST /api/v1/new_chat`.
 *
 * Mirrors the web client's SSE reader (web/lib/chat/streaming-state.ts):
 * each `data: {...}` line is a JSON object with a `type` field. The
 * generator yields every parsed event; consumers pick the types they need
 * (`text-delta` for visible text, `error` to abort).
 */
export async function* streamChatTurn(
	token: string,
	request: {
		chat_id: number;
		user_query: string;
		workspace_id: number;
	},
	signal?: AbortSignal
): AsyncGenerator<ChatStreamEvent> {
	const response = await fetch(await buildBackendUrl("/api/v1/new_chat"), {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
		body: JSON.stringify({
			chat_id: request.chat_id,
			user_query: request.user_query,
			workspace_id: request.workspace_id,
			client_platform: "web",
		}),
		signal,
	});

	if (!response.ok) {
		let detail = `Server error ${response.status}`;
		try {
			const body = await response.json();
			if (body?.detail) detail = String(body.detail);
		} catch {
			// non-JSON error body
		}
		throw new Error(detail);
	}
	if (!response.body) {
		throw new Error("No response body");
	}

	const reader = response.body.getReader();
	const decoder = new TextDecoder();
	let buffer = "";

	try {
		while (true) {
			const { done, value } = await reader.read();
			if (done) break;

			buffer += decoder.decode(value, { stream: true });
			const events = buffer.split(/\r?\n\r?\n/);
			buffer = events.pop() || "";

			for (const event of events) {
				for (const line of event.split(/\r?\n/)) {
					if (!line.startsWith("data: ")) continue;
					const data = line.slice(6).trim();
					if (!data || data === "[DONE]") continue;
					try {
						yield JSON.parse(data) as ChatStreamEvent;
					} catch (e) {
						if (e instanceof SyntaxError) continue;
						throw e;
					}
				}
			}
		}
	} finally {
		reader.releaseLock();
	}
}

/** Extract the plain-text body from a persisted message's JSONB content. */
export function messageText(content: unknown): string {
	if (typeof content === "string") return content;
	if (Array.isArray(content)) {
		return content
			.filter(
				(part): part is { type: "text"; text: string } =>
					typeof part === "object" &&
					part !== null &&
					(part as { type?: string }).type === "text"
			)
			.map((part) => part.text)
			.join("");
	}
	return "";
}
