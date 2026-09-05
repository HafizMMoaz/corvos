import icon from "data-base64:~assets/icon.png";
import { Storage } from "@plasmohq/storage";
import { ReloadIcon } from "@radix-ui/react-icons";
import { Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import "~tailwind.css";

import {
	createThread,
	listThreads,
	listWorkspaces,
	loadThreadMessages,
	messageText,
	saveExtensionDocuments,
	streamChatTurn,
	verifyToken,
	type CorvosThread,
	type CorvosWorkspace,
} from "~utils/corvos-api";
import {
	buildExtensionDocumentItem,
	buildPageContextQuery,
	captureActiveTabMarkdown,
} from "~utils/page-context";

type PanelMessage = {
	id: string;
	role: "user" | "assistant";
	text: string;
};

const storage = new Storage({ area: "local" });

function ChatBubble({ message }: { message: PanelMessage }) {
	const isUser = message.role === "user";
	return (
		<div className={isUser ? "flex justify-end" : "flex justify-start"}>
			<div
				className={`max-w-[85%] whitespace-pre-wrap break-words rounded-xl px-3 py-2 text-sm leading-relaxed ${
					isUser
						? "bg-teal-600 text-white"
						: "border border-gray-700 bg-gray-800/60 text-gray-100"
				}`}
			>
				{message.text || (isUser ? "" : "…")}
			</div>
		</div>
	);
}

function SidePanel() {
	const [token, setToken] = useState<string | null>(null);
	const [apiKeyInput, setApiKeyInput] = useState("");
	const [loginError, setLoginError] = useState("");
	const [loginLoading, setLoginLoading] = useState(false);
	const [bootLoading, setBootLoading] = useState(true);

	const [workspaces, setWorkspaces] = useState<CorvosWorkspace[]>([]);
	const [workspaceId, setWorkspaceId] = useState<number | null>(null);

	const [threads, setThreads] = useState<CorvosThread[]>([]);
	const [activeThreadId, setActiveThreadId] = useState<number | null>(null);
	const [threadPickerOpen, setThreadPickerOpen] = useState(false);

	const [messages, setMessages] = useState<PanelMessage[]>([]);
	const [input, setInput] = useState("");
	const [isStreaming, setIsStreaming] = useState(false);
	const [includePageContext, setIncludePageContext] = useState(false);
	const [statusLine, setStatusLine] = useState("");
	const abortRef = useRef<AbortController | null>(null);
	const messagesEndRef = useRef<HTMLDivElement | null>(null);

	useEffect(() => {
		messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [messages]);

	/** Boot: load token + workspace, validate, fetch workspaces + threads. */
	const boot = useCallback(async () => {
		setBootLoading(true);
		try {
			const storedToken = await storage.get("token");
			if (!storedToken) {
				setToken(null);
				return;
			}

			const valid = await verifyToken(storedToken);
			if (!valid) {
				await storage.remove("token");
				setToken(null);
				return;
			}
			setToken(storedToken);

			const spaces = await listWorkspaces(storedToken);
			setWorkspaces(spaces);

			const storedWorkspace = await storage.get("workspace_id");
			const parsed = parseInt(String(storedWorkspace ?? ""), 10);
			if (Number.isFinite(parsed) && spaces.some((s) => s.id === parsed)) {
				setWorkspaceId(parsed);
			}

			// "Ask Corvos about this page" context-menu handoff: the panel
			// opens with page context pre-armed for the first question.
			const askArmed = await storage.get<boolean>("ask_with_context");
			if (askArmed === true) {
				setIncludePageContext(true);
				await storage.remove("ask_with_context");
			}
		} catch (error) {
			console.error("Sidepanel boot failed:", error);
			setToken(null);
		} finally {
			setBootLoading(false);
		}
	}, []);

	useEffect(() => {
		boot();
	}, [boot]);

	/** Thread list refresh (workspace must be selected). */
	const refreshThreads = useCallback(
		async (wsId: number, t: string) => {
			try {
				const list = await listThreads(t, wsId);
				setThreads(list);
			} catch (error) {
				console.error("Failed to list threads:", error);
			}
		},
		[]
	);

	useEffect(() => {
		if (token && workspaceId) {
			refreshThreads(workspaceId, token);
		}
	}, [token, workspaceId, refreshThreads]);

	const handleLogin = async (event: { preventDefault: () => void }) => {
		event.preventDefault();
		if (!apiKeyInput.trim()) {
			setLoginError("Personal access token is required");
			return;
		}
		setLoginLoading(true);
		setLoginError("");
		try {
			const valid = await verifyToken(apiKeyInput.trim());
			if (!valid) {
				setLoginError("Invalid personal access token. Please check and try again.");
				return;
			}
			await storage.set("token", apiKeyInput.trim());
			setToken(apiKeyInput.trim());
			await boot();
		} catch {
			setLoginError("Could not reach the Corvos backend. Is it running?");
		} finally {
			setLoginLoading(false);
		}
	};

	const handleLogout = async () => {
		abortRef.current?.abort();
		await storage.remove("token");
		setToken(null);
		setWorkspaces([]);
		setWorkspaceId(null);
		setThreads([]);
		setActiveThreadId(null);
		setMessages([]);
	};

	const selectWorkspace = async (wsId: number) => {
		await storage.set("workspace_id", String(wsId));
		setWorkspaceId(wsId);
		setActiveThreadId(null);
		setMessages([]);
	};

	const startNewChat = () => {
		abortRef.current?.abort();
		setActiveThreadId(null);
		setMessages([]);
		setStatusLine("");
	};

	const openThread = async (threadId: number) => {
		if (!token) return;
		abortRef.current?.abort();
		setThreadPickerOpen(false);
		setActiveThreadId(threadId);
		setMessages([]);
		setStatusLine("Loading conversation…");
		try {
			const history = await loadThreadMessages(token, threadId);
			setMessages(
				history
					.filter((m) => m.role === "user" || m.role === "assistant")
					.map((m) => ({
						id: `msg-${m.id}`,
						role: m.role as "user" | "assistant",
						text: messageText(m.content),
					}))
					.filter((m) => m.text.length > 0)
			);
			setStatusLine("");
		} catch (error) {
			setStatusLine("Failed to load conversation");
			console.error(error);
		}
	};

	const saveCurrentPage = async () => {
		if (!token || !workspaceId) return;
		setStatusLine("Saving page to knowledge base…");
		try {
			const page = await captureActiveTabMarkdown();
			if (!page) {
				setStatusLine("No capturable page in this tab");
				return;
			}
			await saveExtensionDocuments(token, workspaceId, [
				buildExtensionDocumentItem({
					...page,
					sessionId: "sidepanel",
				}),
			]);
			setStatusLine(`Saved "${page.title}" to your knowledge base`);
		} catch (error) {
			console.error(error);
			setStatusLine("Failed to save page");
		}
	};

	const sendMessage = async () => {
		const question = input.trim();
		if (!question || !token || !workspaceId || isStreaming) return;

		setInput("");
		setStatusLine("");
		abortRef.current?.abort();
		const controller = new AbortController();
		abortRef.current = controller;

		// Ensure a thread exists for this conversation.
		let threadId = activeThreadId;
		if (!threadId) {
			setStatusLine("Creating conversation…");
			try {
				const thread = await createThread(token, workspaceId, "Extension chat");
				threadId = thread.id;
				setActiveThreadId(threadId);
				refreshThreads(workspaceId, token);
			} catch (error) {
				setStatusLine("Failed to create conversation");
				console.error(error);
				return;
			}
		}

		// Optionally attach the current page as inline context.
		let query = question;
		if (includePageContext) {
			setStatusLine("Reading this page…");
			const page = await captureActiveTabMarkdown();
			if (page) {
				query = buildPageContextQuery(page, question);
			}
		}

		const userMsgId = `local-user-${Date.now()}`;
		const assistantMsgId = `local-assistant-${Date.now()}`;
		setMessages((prev) => [
			...prev,
			{ id: userMsgId, role: "user", text: question },
			{ id: assistantMsgId, role: "assistant", text: "" },
		]);
		setIsStreaming(true);
		setStatusLine("Thinking…");

		try {
			for await (const event of streamChatTurn(
				token,
				{ chat_id: threadId, user_query: query, workspace_id: workspaceId },
				controller.signal
			)) {
				if (event.type === "text-delta") {
					setStatusLine("");
					setMessages((prev) =>
						prev.map((m) =>
							m.id === assistantMsgId
								? { ...m, text: m.text + event.delta }
								: m
						)
					);
				} else if (event.type === "error") {
					throw new Error(event.errorText || "Server error");
				}
			}
		} catch (error) {
			if (controller.signal.aborted) {
				setStatusLine("Response cancelled");
			} else {
				console.error(error);
				setStatusLine(`Error: ${error instanceof Error ? error.message : "stream failed"}`);
			}
		} finally {
			setIsStreaming(false);
			abortRef.current = null;
		}
	};

	const stopStreaming = () => {
		abortRef.current?.abort();
	};

	// ── Render ────────────────────────────────────────────────────────────

	if (bootLoading) {
		return (
			<div className="flex h-screen items-center justify-center bg-gray-900">
				<ReloadIcon className="h-6 w-6 animate-spin text-teal-400" />
			</div>
		);
	}

	if (!token) {
		return (
			<div className="flex h-screen flex-col items-center justify-center bg-gradient-to-br from-gray-900 to-gray-800 p-6">
				<div className="w-full max-w-sm space-y-6">
					<div className="flex flex-col items-center space-y-2">
						<div className="rounded-full bg-gray-800 p-3 ring-2 ring-gray-700">
							<img className="h-12 w-12" src={icon} alt="Corvos" />
						</div>
						<h1 className="text-2xl font-semibold text-white">Corvos</h1>
						<p className="text-sm text-gray-400">Chat with the web, capture knowledge.</p>
					</div>
					<form
						onSubmit={handleLogin}
						className="space-y-4 rounded-xl border border-gray-700 bg-gray-800/70 p-5"
					>
						<div className="space-y-2">
							<label htmlFor="sidepanel-pat" className="text-sm font-medium text-gray-300">
								Personal access token
							</label>
							<input
								id="sidepanel-pat"
								type="text"
								value={apiKeyInput}
								onChange={(e) => setApiKeyInput(e.target.value)}
								className="w-full rounded-md border border-gray-700 bg-gray-900/50 px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-teal-500"
								placeholder="Enter your personal access token"
							/>
							{loginError && <p className="text-sm text-red-400">{loginError}</p>}
						</div>
						<button
							type="submit"
							disabled={loginLoading}
							className="w-full rounded-md bg-teal-600 py-2 text-white transition-colors hover:bg-teal-500 disabled:opacity-50"
						>
							{loginLoading ? "Connecting…" : "Connect"}
						</button>
					</form>
				</div>
			</div>
		);
	}

	if (!workspaceId) {
		return (
			<div className="flex h-screen flex-col bg-gradient-to-br from-gray-900 to-gray-800 p-4">
				<div className="mb-4 flex items-center justify-between border-b border-gray-700 pb-3">
					<div className="flex items-center space-x-2">
						<img className="h-6 w-6" src={icon} alt="Corvos" />
						<h1 className="text-lg font-semibold text-white">Choose a workspace</h1>
					</div>
					<button
						type="button"
						onClick={handleLogout}
						className="text-xs text-gray-400 hover:text-white"
					>
						Log out
					</button>
				</div>
				<div className="flex-1 space-y-2 overflow-y-auto">
					{workspaces.length === 0 && (
						<p className="p-4 text-center text-sm text-yellow-300">
							No workspaces yet. Create one in the Corvos web app first.
						</p>
					)}
					{workspaces.map((ws) => (
						<button
							key={ws.id}
							type="button"
							onClick={() => selectWorkspace(ws.id)}
							className="w-full rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-3 text-left text-white transition-colors hover:border-teal-600 hover:bg-gray-800"
						>
							<span className="font-medium">{ws.name}</span>
						</button>
					))}
				</div>
			</div>
		);
	}

	return (
		<div className="flex h-screen flex-col bg-gradient-to-b from-gray-900 to-gray-850">
			{/* Header */}
			<div className="flex items-center justify-between border-b border-gray-700 px-3 py-2">
				<div className="flex items-center space-x-2">
					<img className="h-5 w-5" src={icon} alt="Corvos" />
					<div className="relative">
						<button
							type="button"
							onClick={() => setThreadPickerOpen((open) => !open)}
							className="max-w-[180px] truncate text-sm font-medium text-gray-200 hover:text-white"
							title="Switch conversation"
						>
							{activeThreadId
								? threads.find((t) => t.id === activeThreadId)?.title ?? "Conversation"
								: "New conversation"}
							{" ▾"}
						</button>
						{threadPickerOpen && (
							<div className="absolute left-0 top-7 z-10 max-h-72 w-72 overflow-y-auto rounded-lg border border-gray-700 bg-gray-800 p-1 shadow-xl">
								<button
									type="button"
									onClick={() => {
										setThreadPickerOpen(false);
										startNewChat();
									}}
									className="w-full rounded px-2 py-1.5 text-left text-sm text-teal-300 hover:bg-gray-700"
								>
									+ New conversation
								</button>
								{threads.map((t) => (
									<button
										key={t.id}
										type="button"
										onClick={() => openThread(t.id)}
										className={`w-full truncate rounded px-2 py-1.5 text-left text-sm ${
											t.id === activeThreadId
												? "bg-gray-700 text-white"
												: "text-gray-300 hover:bg-gray-700"
										}`}
									>
										{t.title}
									</button>
								))}
							</div>
						)}
					</div>
				</div>
				<div className="flex items-center gap-1">
					<button
						type="button"
						onClick={saveCurrentPage}
						className="rounded px-2 py-1 text-xs text-amber-300 hover:bg-gray-800"
						title="Save the current page to your knowledge base"
					>
						Save page
					</button>
					<button
						type="button"
						onClick={startNewChat}
						className="rounded px-2 py-1 text-xs text-gray-300 hover:bg-gray-800"
					>
						New chat
					</button>
					<button
						type="button"
						onClick={handleLogout}
						className="rounded px-2 py-1 text-xs text-gray-500 hover:text-white"
					>
						Log out
					</button>
				</div>
			</div>

			{/* Messages */}
			<div className="flex-1 space-y-3 overflow-y-auto p-3">
				{messages.length === 0 && !isStreaming && (
					<div className="flex h-full flex-col items-center justify-center space-y-2 text-center">
						<img className="h-10 w-10 opacity-60" src={icon} alt="Corvos" />
						<p className="text-sm text-gray-400">Ask anything about the page you're reading</p>
						<p className="text-xs text-gray-500">
							Toggle "Include page" to give the agent the full article
						</p>
					</div>
				)}
				{messages.map((message) => (
					<ChatBubble key={message.id} message={message} />
				))}
				<div ref={messagesEndRef} />
			</div>

			{/* Status line */}
			{statusLine && (
				<div className="px-3 pb-1 text-xs text-gray-400">{statusLine}</div>
			)}

			{/* Composer */}
			<div className="border-t border-gray-700 p-2">
				<button
					type="button"
					onClick={() => setIncludePageContext((on) => !on)}
					className={`mb-2 rounded-full border px-3 py-1 text-xs transition-colors ${
						includePageContext
							? "border-teal-500 bg-teal-500/20 text-teal-300"
							: "border-gray-600 bg-gray-800 text-gray-400 hover:text-gray-200"
					}`}
				>
					{includePageContext ? "✓ Include page" : "Include page"}
				</button>
				<div className="flex items-end gap-2">
					<textarea
						value={input}
						onChange={(e) => setInput(e.target.value)}
						onKeyDown={(e) => {
							if (e.key === "Enter" && !e.shiftKey) {
								e.preventDefault();
								sendMessage();
							}
						}}
						rows={2}
						placeholder="Ask about this page or your knowledge base…"
						className="flex-1 resize-none rounded-lg border border-gray-700 bg-gray-900/60 px-3 py-2 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-teal-500"
					/>
					{isStreaming ? (
						<button
							type="button"
							onClick={stopStreaming}
							className="rounded-lg bg-red-500/90 px-3 py-2 text-white hover:bg-red-600"
							title="Stop generating"
						>
							■
						</button>
					) : (
						<button
							type="button"
							onClick={sendMessage}
							disabled={!input.trim()}
							className="rounded-lg bg-teal-600 px-3 py-2 text-white transition-colors hover:bg-teal-500 disabled:opacity-40"
							title="Send"
						>
							<Send className="h-4 w-4" />
						</button>
					)}
				</div>
			</div>
		</div>
	);
}

export default SidePanel;
