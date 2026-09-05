import { Storage } from "@plasmohq/storage";
import { convertHtmlToMarkdown } from "dom-to-semantic-markdown";
import { DOMParser } from "linkedom";

import { buildBackendUrl } from "~utils/backend-url";
import { getRenderedHtml, initQueues, initWebHistory } from "~utils/commons";
import { isCapturableUrl } from "~utils/page-context";
import type { WebHistory } from "~utils/interfaces";

// Service workers have no DOM - linkedom needs the Node type constants
// (mirrors background/messages/savesnapshot.ts).
// @ts-ignore
globalThis.Node = {
	ELEMENT_NODE: 1,
	ATTRIBUTE_NODE: 2,
	TEXT_NODE: 3,
	CDATA_SECTION_NODE: 4,
	PROCESSING_INSTRUCTION_NODE: 7,
	COMMENT_NODE: 8,
	DOCUMENT_NODE: 9,
	DOCUMENT_TYPE_NODE: 10,
	DOCUMENT_FRAGMENT_NODE: 11,
};

const storage = new Storage({ area: "local" });

// ── Researcher mode: auto-capture visited pages ─────────────────────────
//
// When "auto_capture" is toggled on, every completed page load is converted
// to markdown and queued into the selected workspace's knowledge base via
// POST /api/v1/documents (document_type=EXTENSION) - the researcher just
// browses and Corvos reads along.

const autoCapturedUrls = new Set<string>();

async function readCaptureSettings(): Promise<{
	enabled: boolean;
	token: string | null;
	workspaceId: number | null;
}> {
	const [enabled, token, workspaceId] = await Promise.all([
		storage.get<boolean>("auto_capture"),
		storage.get("token"),
		storage.get("workspace_id"),
	]);
	return {
		enabled: enabled === true,
		token: typeof token === "string" && token.length > 0 ? token : null,
		workspaceId: Number.isFinite(parseInt(String(workspaceId ?? ""), 10))
			? parseInt(String(workspaceId), 10)
			: null,
	};
}

async function autoCapturePage(tabId: number, url: string): Promise<void> {
	if (autoCapturedUrls.has(url)) {
		return;
	}
	autoCapturedUrls.add(url);

	try {
		const results = await chrome.scripting.executeScript({
			target: { tabId },
			// @ts-ignore - func must be a self-contained serializable function
			func: getRenderedHtml,
		});
		const page = results?.[0]?.result as
			| { url: string; title: string; renderedHtml: string }
			| undefined;
		if (!page?.renderedHtml) {
			return;
		}

		const markdown = convertHtmlToMarkdown(page.renderedHtml, {
			extractMainContent: true,
			enableTableColumnTracking: true,
			includeMetaData: false,
			overrideDOMParser: new DOMParser(),
		});

		const settings = await readCaptureSettings();
		if (!settings.token || !settings.workspaceId) {
			return;
		}

		const response = await fetch(await buildBackendUrl("/api/v1/documents"), {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				Authorization: `Bearer ${settings.token}`,
			},
			body: JSON.stringify({
				document_type: "EXTENSION",
				workspace_id: settings.workspaceId,
				content: [
					{
						metadata: {
							BrowsingSessionId: `auto-${tabId}`,
							VisitedWebPageURL: String(page.url || url),
							VisitedWebPageTitle: String(page.title || "No Title"),
							VisitedWebPageDateWithTimeInISOString: new Date().toISOString(),
							VisitedWebPageReffererURL: "",
							VisitedWebPageVisitDurationInMilliseconds: "0",
						},
						pageContent: String(markdown || ""),
					},
				],
			}),
		});

		if (!response.ok) {
			console.error("Auto-capture failed:", response.status, await response.text());
		}
	} catch (error) {
		console.error("Auto-capture error:", error);
	}
}

// ── Tab tracking (existing history capture) ─────────────────────────────

chrome.tabs.onCreated.addListener(async (tab: any) => {
	try {
		await initWebHistory(tab.id);
		await initQueues(tab.id);
	} catch (error) {
		console.log(error);
	}
});

chrome.tabs.onUpdated.addListener(async (tabId: number, changeInfo: any, tab: any) => {
	if (changeInfo.status === "complete" && tab.url) {
		const storage = new Storage({ area: "local" });
		await initWebHistory(tab.id);
		await initQueues(tab.id);

		const result = await chrome.scripting.executeScript({
			// @ts-ignore
			target: { tabId: tab.id },
			// @ts-ignore
			func: getRenderedHtml,
		});

		const toPushInTabHistory: any = result[0].result;

		const urlQueueListObj: any = await storage.get("urlQueueList");
		const timeQueueListObj: any = await storage.get("timeQueueList");

		urlQueueListObj.urlQueueList
			.find((data: WebHistory) => data.tabsessionId === tabId)
			?.urlQueue.push(toPushInTabHistory.url);
		timeQueueListObj.timeQueueList
			.find((data: WebHistory) => data.tabsessionId === tabId)
			?.timeQueue.push(toPushInTabHistory.entryTime);

		await storage.set("urlQueueList", {
			urlQueueList: urlQueueListObj.urlQueueList,
		});
		await storage.set("timeQueueList", {
			timeQueueList: timeQueueListObj.timeQueueList,
		});

		// Researcher mode: capture the page into the knowledge base.
		if (isCapturableUrl(tab.url)) {
			const settings = await readCaptureSettings();
			if (settings.enabled && settings.token && settings.workspaceId) {
				autoCapturePage(tabId, tab.url);
			}
		}
	}
});

chrome.tabs.onRemoved.addListener(async (tabId: number, removeInfo: object) => {
	const storage = new Storage({ area: "local" });
	const urlQueueListObj: any = await storage.get("urlQueueList");
	const timeQueueListObj: any = await storage.get("timeQueueList");
	if (urlQueueListObj.urlQueueList && timeQueueListObj.timeQueueList) {
		const urlQueueListToSave = urlQueueListObj.urlQueueList.map((element: WebHistory) => {
			if (element.tabsessionId !== tabId) {
				return element;
			}
		});
		const timeQueueListSave = timeQueueListObj.timeQueueList.map((element: WebHistory) => {
			if (element.tabsessionId !== tabId) {
				return element;
			}
		});
		await storage.set("urlQueueList", {
			urlQueueList: urlQueueListToSave.filter((item: any) => item),
		});
		await storage.set("timeQueueList", {
			timeQueueList: timeQueueListSave.filter((item: any) => item),
		});
	}
});

// ── Context menus: act on any page ──────────────────────────────────────

chrome.runtime.onInstalled.addListener(() => {
	chrome.contextMenus.removeAll(() => {
		chrome.contextMenus.create({
			id: "corvos-save-page",
			title: "Save this page to Corvos",
			contexts: ["page"],
		});
		chrome.contextMenus.create({
			id: "corvos-save-selection",
			title: 'Save "%s" to Corvos',
			contexts: ["selection"],
		});
		chrome.contextMenus.create({
			id: "corvos-ask-page",
			title: "Ask Corvos about this page",
			contexts: ["page", "selection"],
		});
	});
});

async function saveSelectionToCorvos(
	text: string,
	tab: chrome.tabs.Tab | undefined
): Promise<void> {
	const settings = await readCaptureSettings();
	if (!settings.token || !settings.workspaceId) {
		console.warn("Corvos: not connected - cannot save selection");
		return;
	}

	await fetch(await buildBackendUrl("/api/v1/documents"), {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${settings.token}`,
		},
		body: JSON.stringify({
			document_type: "EXTENSION",
			workspace_id: settings.workspaceId,
			content: [
				{
					metadata: {
						BrowsingSessionId: `selection-${tab?.id ?? 0}`,
						VisitedWebPageURL: String(tab?.url ?? ""),
						VisitedWebPageTitle: String(tab?.title ?? "Selection"),
						VisitedWebPageDateWithTimeInISOString: new Date().toISOString(),
						VisitedWebPageReffererURL: "",
						VisitedWebPageVisitDurationInMilliseconds: "0",
					},
					pageContent: String(text),
				},
			],
		}),
	});
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
	try {
		switch (info.menuItemId) {
			case "corvos-save-page": {
				if (tab?.id && isCapturableUrl(tab.url)) {
					await autoCapturePage(tab.id, tab.url ?? "");
				}
				break;
			}
			case "corvos-save-selection": {
				if (info.selectionText) {
					await saveSelectionToCorvos(info.selectionText, tab);
				}
				break;
			}
			case "corvos-ask-page": {
				// Open the sidepanel with page context pre-armed so the
				// next question automatically includes the article.
				await storage.set("ask_with_context", true);
				if (tab?.windowId !== undefined) {
					await chrome.sidePanel.open({ windowId: tab.windowId });
				}
				break;
			}
		}
	} catch (error) {
		console.error("Context menu action failed:", error);
	}
});
