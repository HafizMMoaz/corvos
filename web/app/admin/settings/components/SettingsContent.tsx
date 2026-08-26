"use client";

import { useMemo } from "react";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminSettings } from "@/hooks/use-admin-settings";
import { SettingRow } from "./SettingRow";

function groupByCategory<T extends { category: string; key: string }>(items: T[]): [string, T[]][] {
	const groups = new Map<string, T[]>();
	for (const item of items) {
		const existing = groups.get(item.category);
		if (existing) {
			existing.push(item);
		} else {
			groups.set(item.category, [item]);
		}
	}
	for (const group of groups.values()) {
		group.sort((a, b) => a.key.localeCompare(b.key));
	}
	return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
}

export function SettingsContent() {
	const { settings, isLoading, isMutating, updateSetting, revertSetting, revealSetting } =
		useAdminSettings();

	const categories = useMemo(() => groupByCategory(settings), [settings]);

	return (
		<div className="space-y-6 min-w-0">
			<div>
				<h3 className="text-sm font-semibold tracking-tight">Platform settings</h3>
				<p className="text-xs text-muted-foreground">
					Runtime configuration and secrets used across the platform. Secret values stay masked
					until revealed.
				</p>
			</div>

			{isLoading ? (
				<div className="space-y-2">
					{["skeleton-a", "skeleton-b", "skeleton-c", "skeleton-d"].map((key) => (
						<Skeleton key={key} className="h-20 w-full" />
					))}
				</div>
			) : categories.length > 0 ? (
				<Accordion
					type="multiple"
					defaultValue={categories.map(([category]) => category)}
					className="space-y-2"
				>
					{categories.map(([category, categorySettings]) => (
						<AccordionItem key={category} value={category} className="rounded-md border px-4">
							<AccordionTrigger className="hover:no-underline">
								<span className="flex items-center gap-2 text-sm font-medium">
									{category}
									<Badge variant="secondary" className="text-[10px]">
										{categorySettings.length}
									</Badge>
								</span>
							</AccordionTrigger>
							<AccordionContent>
								<div className="-m-1 grid grid-cols-1 gap-3 p-1">
									{categorySettings.map((setting) => (
										<SettingRow
											key={setting.key}
											setting={setting}
											isMutating={isMutating}
											onUpdate={updateSetting}
											onRevert={revertSetting}
											onReveal={revealSetting}
										/>
									))}
								</div>
							</AccordionContent>
						</AccordionItem>
					))}
				</Accordion>
			) : (
				<p className="py-6 text-center text-sm text-muted-foreground">
					No settings configured yet.
				</p>
			)}
		</div>
	);
}
