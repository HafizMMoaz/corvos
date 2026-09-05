import { Reveal } from "@/components/connectors-marketing/reveal";
import { MarketingSection } from "@/components/marketing/section";

const COLUMNS = [
	{ label: "Browser agents", examples: "Browserbase, Browser Use" },
	{ label: "Scraping APIs", examples: "Firecrawl" },
	{ label: "Search APIs", examples: "Exa, Tavily, Parallel" },
	{ label: "Scraper marketplaces", examples: "Apify" },
];

const ROWS = [
	{
		feature: "Built for",
		browser: "Click-driven web tasks: logins, forms, navigation",
		scraping: "Converting single pages to markdown or JSON",
		search: "Index-based search and page retrieval",
		marketplace: "Per-site scrapers from a community marketplace",
		corvos: "Typed platform APIs as research primitives for agents",
	},
	{
		feature: "How retrieval works",
		browser: "LLM steers a real browser step by step",
		scraping: "Send a URL, get markdown or structured JSON back",
		search: "Query an index, get ranked results and snippets",
		marketplace: "Find an actor per site, learn its schema, run it",
		corvos: "One typed REST call per platform - no LLM needed in the loop",
	},
	{
		feature: "Platform data (comment trees, transcripts, reviews)",
		browser: "Whatever the LLM parses from rendered HTML",
		scraping: "Page-level only; social platforms are secondary",
		search: "Snippets and page text, not structured items",
		marketplace: "Yes, but schema and quality vary by actor",
		corvos: "First-class: posts, comment trees, transcripts, reviews, SERPs",
	},
	{
		feature: "Consistency",
		browser: "Varies by model and page structure",
		scraping: "One API, but you define schemas per page",
		search: "One API, fixed snippet and content shapes",
		marketplace: "Different schema and quality per actor",
		corvos: "One API, one schema style across all connectors",
	},
	{
		feature: "Research workspace & knowledge base",
		browser: "No",
		scraping: "No",
		search: "No",
		marketplace: "No",
		corvos: "Cited briefs, knowledge base, automations, and deliverables",
	},
	{
		feature: "Pricing",
		browser: "Per browser-minute (1-min minimum) plus LLM token costs",
		scraping: "Credits per page; schema extraction costs extra",
		search: "Per search request",
		marketplace: "Per event or result, set by each actor",
		corvos: "Per item returned - failed calls are free",
	},
];

export function CompareTable() {
	return (
		<MarketingSection>
			<Reveal>
				<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">How Corvos stacks up</h2>
				<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
					Most tools solve one piece: browser automation, page scraping, or search. Corvos combines
					a research workspace with live platform data your agents can call as typed APIs. Here's
					how it compares.
				</p>
			</Reveal>
			<Reveal>
				<div className="mt-8 overflow-x-auto rounded-xl border bg-card">
					<table className="w-full min-w-4xl text-sm">
						<thead>
							<tr className="border-b bg-muted/40 text-left">
								<th className="p-4 font-medium">Feature</th>
								{COLUMNS.map((col) => (
									<th key={col.label} className="p-4 font-medium text-muted-foreground">
										{col.label}
										<span className="block text-xs font-normal">{col.examples}</span>
									</th>
								))}
								<th className="p-4 font-medium text-brand">Corvos</th>
							</tr>
						</thead>
						<tbody>
							{ROWS.map((row) => (
								<tr key={row.feature} className="border-b last:border-b-0">
									<th scope="row" className="p-4 text-left font-medium">
										{row.feature}
									</th>
									<td className="p-4 text-muted-foreground">{row.browser}</td>
									<td className="p-4 text-muted-foreground">{row.scraping}</td>
									<td className="p-4 text-muted-foreground">{row.search}</td>
									<td className="p-4 text-muted-foreground">{row.marketplace}</td>
									<td className="bg-brand/5 p-4 text-foreground">{row.corvos}</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			</Reveal>
		</MarketingSection>
	);
}
