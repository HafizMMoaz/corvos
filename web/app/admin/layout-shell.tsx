"use client";

import { CreditCard, FileClock, Plug, Settings, ShieldCheck, Sparkles, Users } from "lucide-react";
import { useSelectedLayoutSegment } from "next/navigation";
import type React from "react";
import { useMemo } from "react";
import { type RoutedSectionItem, RoutedSectionShell } from "@/components/layout";

export type AdminTab =
	| "roles"
	| "audit-log"
	| "settings"
	| "llm-quotas"
	| "connectors"
	| "billing"
	| "users";

const DEFAULT_TAB: AdminTab = "roles";

interface AdminLayoutShellProps {
	children: React.ReactNode;
}

export function AdminLayoutShell({ children }: AdminLayoutShellProps) {
	const segment = useSelectedLayoutSegment();

	const navItems = useMemo<RoutedSectionItem[]>(
		() => [
			{
				value: "roles" as const,
				label: "Roles & Admins",
				href: "/admin/roles",
				icon: <ShieldCheck className="h-4 w-4" />,
			},
			{
				value: "audit-log" as const,
				label: "Audit Log",
				href: "/admin/audit-log",
				icon: <FileClock className="h-4 w-4" />,
			},
			{
				value: "settings" as const,
				label: "Settings",
				href: "/admin/settings",
				icon: <Settings className="h-4 w-4" />,
			},
			{
				value: "llm-quotas" as const,
				label: "LLM & Quotas",
				href: "/admin/llm-quotas",
				icon: <Sparkles className="h-4 w-4" />,
			},
			{
				value: "connectors" as const,
				label: "Connectors",
				href: "/admin/connectors",
				icon: <Plug className="h-4 w-4" />,
			},
			{
				value: "billing" as const,
				label: "Billing & Plans",
				href: "/admin/billing",
				icon: <CreditCard className="h-4 w-4" />,
				disabled: true,
			},
			{
				value: "users" as const,
				label: "Users",
				href: "/admin/users",
				icon: <Users className="h-4 w-4" />,
				disabled: true,
			},
		],
		[]
	);

	const activeTab: AdminTab =
		segment && navItems.some((item) => item.value === segment)
			? (segment as AdminTab)
			: DEFAULT_TAB;
	const selectedLabel = navItems.find((item) => item.value === activeTab)?.label ?? "Admin";

	return (
		<div className="mx-auto w-full max-w-6xl px-4 py-6 md:px-8">
			<RoutedSectionShell
				title="Admin"
				items={navItems}
				activeValue={activeTab}
				selectedLabel={selectedLabel}
				contentClassName="md:max-w-4xl"
			>
				{children}
			</RoutedSectionShell>
		</div>
	);
}
