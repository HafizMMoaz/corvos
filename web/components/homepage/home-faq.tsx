import { ConnectorFaq } from "@/components/connectors-marketing/connector-faq";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { MarketingSection } from "@/components/marketing/section";
import { FAQJsonLd } from "@/components/seo/json-ld";

/** Answers are 40-60 words, written as quotable definitions for AI Overviews. */
export const HOME_FAQ = [
	{
		question: "What is open web research?",
		answer:
			"Open web research means gathering live data from across the web - search results, discussions, reviews, videos, and any page - instead of relying on a stale index. Corvos gives you typed connectors that collect this data in real time and turn it into cited briefs, alerts, and automations for you and your agents.",
	},
	{
		question: "What is an MCP server?",
		answer:
			"An MCP server exposes tools to AI agents through the Model Context Protocol - an open standard used by Claude, Cursor, and most agent frameworks. Add the Corvos MCP server and your agents can call every connector (reddit.scrape, google_search.scrape, etc.) as native tools.",
	},
	{
		question: "How is Corvos different from a web scraping API?",
		answer:
			"A scraping API returns raw HTML and leaves the rest to you. Corvos pairs typed platform connectors with an agent harness - retries, structured output, credit metering, and an MCP server - so your agents go from a prompt to a cited brief without you building the plumbing.",
	},
	{
		question: "Can I use the connector APIs directly in my own app?",
		answer:
			"Yes. Every connector is a typed REST endpoint - call it from any language with your API key, no agent required. Send a POST with your query and get structured JSON back. Each connector page has copy-paste examples in cURL, Python, JavaScript, and Go.",
	},
	{
		question: "Can I self-host Corvos?",
		answer:
			"Yes. Corvos is open source and self-hostable - run the entire platform on your own infrastructure and keep sensitive research in-house. Start with the cloud version in minutes, or deploy from GitHub when you need full control.",
	},
];

export function HomeFaq() {
	return (
		<MarketingSection>
			<FAQJsonLd questions={HOME_FAQ} />
			<Reveal>
				<h2 className="text-2xl font-bold tracking-tight sm:text-3xl text-center">
					Frequently asked questions
				</h2>
			</Reveal>
			<Reveal>
				<div className="mt-6 max-w-3xl mx-auto">
					<ConnectorFaq items={HOME_FAQ} />
				</div>
			</Reveal>
		</MarketingSection>
	);
}
