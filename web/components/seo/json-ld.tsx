interface JsonLdProps {
	data: Record<string, unknown>;
}

/**
 * Serialize for embedding inside a <script> block. JSON.stringify escapes
 * quotes but not `<`, so a string containing `</script>` would close the tag
 * early. Escaping `<` as its unicode form keeps the JSON equivalent while
 * making that impossible.
 */
function serialize(data: Record<string, unknown>): string {
	return JSON.stringify(data).replaceAll("<", "\\u003c");
}

export function JsonLd({ data }: JsonLdProps) {
	return (
		<script
			type="application/ld+json"
			// This payload is static, server-serialized JSON that never changes on
			// the client, so there is no real mismatch to catch here. Browser
			// extensions that inject their own <script> into <head> shift these
			// tags by a position, which makes React diff each one against its
			// neighbour and report a hydration error pointing at this line.
			suppressHydrationWarning
			// biome-ignore lint/security/noDangerouslySetInnerHtml: JSON-LD structured data requires dangerouslySetInnerHTML for script injection
			dangerouslySetInnerHTML={{ __html: serialize(data) }}
		/>
	);
}

export function OrganizationJsonLd() {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "Organization",
				name: "Corvos",
				url: "https://www.corvos.com",
				logo: "https://www.corvos.com/logo.png",
				description:
					"Corvos is an open-source NotebookLM alternative for AI agents. It researches the live web with structured data through one API or MCP server.",
				sameAs: [
					"https://github.com/HafizMMoaz/Corvos",
					"https://discord.gg/Ggf9PxDNQ2",
					"https://www.reddit.com/r/Corvos/",
					"https://www.linkedin.com/company/corvos/",
				],
				contactPoint: {
					"@type": "ContactPoint",
					email: "hafizmoazkhalid@gmail.com",
					contactType: "sales",
				},
			}}
		/>
	);
}

export function WebSiteJsonLd() {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "WebSite",
				name: "Corvos",
				url: "https://www.corvos.com",
				description:
					"Corvos is an open-source NotebookLM alternative for AI agents, an open web research platform with live data connectors served through one API or MCP server.",
				potentialAction: {
					"@type": "SearchAction",
					target: {
						"@type": "EntryPoint",
						urlTemplate: "https://www.corvos.com/docs?search={search_term_string}",
					},
					"query-input": "required name=search_term_string",
				},
			}}
		/>
	);
}

export function SoftwareApplicationJsonLd() {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "SoftwareApplication",
				name: "Corvos",
				applicationCategory: "BusinessApplication",
				operatingSystem: "Windows, macOS, Linux, Web",
				offers: {
					"@type": "Offer",
					price: "0",
					priceCurrency: "USD",
					description:
						"Free self-hosted from the open-source repo; cloud starts with $5 of free credit, then pay as you go",
				},
				description:
					"Corvos is an open-source NotebookLM alternative for AI agents. It researches the live web with platform-native connectors for Reddit, YouTube, TikTok, Amazon, Walmart, Google Maps, Google Search, and any page on the open web, through one API or MCP server.",
				url: "https://www.corvos.com",
				downloadUrl: "https://github.com/HafizMMoaz/Corvos/releases",
				featureList: [
					"Platform-native connectors: Reddit, YouTube, TikTok, Amazon, Walmart, Google Maps, Google Search, Web Crawl",
					"MCP server that exposes every connector as a native agent tool",
					"Agent harness with retries, structured output, and credit metering",
					"Live web research with cited briefs and alerts",
					"AI automations and agents (scheduled and event-triggered workflows)",
					"AI-powered semantic search across connected tools and documents",
					"Knowledge base with file uploads and Google Drive, OneDrive, and Dropbox sync",
					"Document Q&A with citations, report, podcast, and video generation",
					"Real-time collaborative team chats",
					"Native desktop app with Quick, General, and Screenshot Assist",
					"Open source and self-hostable with no data limits",
				],
			}}
		/>
	);
}

export function ArticleJsonLd({
	title,
	description,
	url,
	datePublished,
	dateModified,
	author,
	image,
}: {
	title: string;
	description: string;
	url: string;
	datePublished: string;
	dateModified?: string;
	author: string;
	image?: string;
}) {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "Article",
				headline: title,
				description,
				url,
				datePublished,
				...(dateModified ? { dateModified } : {}),
				author: {
					"@type": "Organization",
					name: author,
				},
				publisher: {
					"@type": "Organization",
					name: "Corvos",
					logo: {
						"@type": "ImageObject",
						url: "https://www.corvos.com/logo.png",
					},
				},
				image: image || "https://www.corvos.com/og-image.png",
				mainEntityOfPage: {
					"@type": "WebPage",
					"@id": url,
				},
			}}
		/>
	);
}

export function BreadcrumbJsonLd({ items }: { items: { name: string; url: string }[] }) {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "BreadcrumbList",
				itemListElement: items.map((item, index) => ({
					"@type": "ListItem",
					position: index + 1,
					name: item.name,
					item: item.url,
				})),
			}}
		/>
	);
}

export function FAQJsonLd({ questions }: { questions: { question: string; answer: string }[] }) {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "FAQPage",
				mainEntity: questions.map((q) => ({
					"@type": "Question",
					name: q.question,
					acceptedAnswer: {
						"@type": "Answer",
						text: q.answer,
					},
				})),
			}}
		/>
	);
}
