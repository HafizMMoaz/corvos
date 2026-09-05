import { convertHtmlToMarkdown } from "dom-to-semantic-markdown";

import { getRenderedHtml } from "./commons";
import type { ExtensionDocumentItem } from "./corvos-api";

/** Cap inline page context so a single giant page can't blow the prompt. */
export const MAX_PAGE_CONTEXT_CHARS = 20000;

/** URLs the extension must never capture (browser internals, store pages). */
export function isCapturableUrl(url: string | undefined | null): boolean {
	if (!url) return false;
	return /^(https?|file):\/\//i.test(url);
}

/**
 * Capture the active tab's rendered content as semantic markdown.
 *
 * Runs `getRenderedHtml` in the page (via chrome.scripting) then converts
 * the HTML to markdown in the extension context. Safe to call from any
 * extension page with the `scripting` permission (popup, sidepanel).
 */
export async function captureActiveTabMarkdown(): Promise<{
	url: string;
	title: string;
	markdown: string;
} | null> {
	const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
	if (!tab?.id || !isCapturableUrl(tab.url)) {
		return null;
	}

	const results = await chrome.scripting.executeScript({
		target: { tabId: tab.id },
		// @ts-ignore - func must be a self-contained serializable function
		func: getRenderedHtml,
	});
	const page = results?.[0]?.result as
		| { url: string; title: string; renderedHtml: string }
		| undefined;
	if (!page?.renderedHtml) {
		return null;
	}

	const markdown = convertHtmlToMarkdown(page.renderedHtml, {
		extractMainContent: true,
		enableTableColumnTracking: true,
		includeMetaData: false,
	});

	return {
		url: page.url ?? tab.url ?? "",
		title: page.title ?? tab.title ?? "Untitled",
		markdown: markdown.slice(0, MAX_PAGE_CONTEXT_CHARS),
	};
}

/**
 * Wrap captured page content as an inline context block for the chat agent.
 * The agent sees the page as part of the user query for this turn only -
 * nothing is persisted until the user explicitly saves the page.
 */
export function buildPageContextQuery(
	page: { url: string; title: string; markdown: string },
	question: string
): string {
	return (
		`<current_web_page_context url="${page.url}" title="${page.title}">\n` +
		`${page.markdown}\n` +
		`</current_web_page_context>\n\n` +
		`${question}`
	);
}

/**
 * Build the `POST /api/v1/documents` body item for a captured page,
 * matching the backend's `ExtensionDocumentContent` schema (same shape
 * the existing savedata/savesnapshot handlers send).
 */
export function buildExtensionDocumentItem(page: {
	url: string;
	title: string;
	markdown: string;
	sessionId?: string;
	referrerUrl?: string;
	durationMs?: number;
}): ExtensionDocumentItem {
	return {
		metadata: {
			BrowsingSessionId: String(page.sessionId ?? ""),
			VisitedWebPageURL: String(page.url || ""),
			VisitedWebPageTitle: String(page.title || "No Title"),
			VisitedWebPageDateWithTimeInISOString: new Date().toISOString(),
			VisitedWebPageReffererURL: String(page.referrerUrl ?? ""),
			VisitedWebPageVisitDurationInMilliseconds: String(page.durationMs ?? 0),
		},
		pageContent: String(page.markdown || ""),
	};
}
