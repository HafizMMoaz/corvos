"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ModelsContent } from "./ModelsContent";
import { ProvidersContent } from "./ProvidersContent";
import { QuotaContent } from "./QuotaContent";

/**
 * The admin nav has exactly one slot for this whole area ("llm-quotas" in
 * layout-shell.tsx), so this page owns its own internal sub-navigation across
 * the three resource types instead of getting three separate nav-level routes.
 */
export function LlmQuotasContent() {
	return (
		<div className="space-y-6 min-w-0">
			<div>
				<h3 className="text-sm font-semibold tracking-tight">LLM providers, models & quotas</h3>
				<p className="text-xs text-muted-foreground">
					Manage the platform's LLM provider connections, the model catalog built on top of them,
					and free-tier token quota usage.
				</p>
			</div>

			<Tabs defaultValue="providers" className="w-full">
				<TabsList>
					<TabsTrigger value="providers">Providers</TabsTrigger>
					<TabsTrigger value="models">Models</TabsTrigger>
					<TabsTrigger value="quota">Quota</TabsTrigger>
				</TabsList>
				<TabsContent value="providers">
					<ProvidersContent />
				</TabsContent>
				<TabsContent value="models">
					<ModelsContent />
				</TabsContent>
				<TabsContent value="quota">
					<QuotaContent />
				</TabsContent>
			</Tabs>
		</div>
	);
}
