"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAdminPermissions } from "../../admin-shell";
import { FeatureFlagsContent } from "./FeatureFlagsContent";
import { PlansContent } from "./PlansContent";
import { SubscriptionsContent } from "./SubscriptionsContent";

// PlatformPermission values, from backend/app/db.py.
const PLANS_READ = "plans:read";
const FEATURE_FLAGS_READ = "feature_flags:read";
const BILLING_READ = "billing:read";

/**
 * The admin nav has exactly one slot for this whole area ("billing" in
 * layout-shell.tsx), so this page owns its own internal sub-navigation across
 * plans, feature flags, and subscriptions -- same shape as LlmQuotasContent.
 */
export function BillingContent() {
	const { has } = useAdminPermissions();

	const canReadPlans = has(PLANS_READ);
	const canReadFlags = has(FEATURE_FLAGS_READ);
	const canReadSubs = has(BILLING_READ);

	return (
		<div className="space-y-6 min-w-0">
			<div>
				<h3 className="text-sm font-semibold tracking-tight">Billing & plans</h3>
				<p className="text-xs text-muted-foreground">
					Manage subscription plans, the model entitlements and feature limits they grant, and live
					Paddle subscriptions.
				</p>
			</div>

			<Tabs defaultValue="plans" className="w-full">
				<TabsList>
					<TabsTrigger value="plans" disabled={!canReadPlans}>
						Plans
					</TabsTrigger>
					<TabsTrigger value="flags" disabled={!canReadFlags}>
						Feature Flags
					</TabsTrigger>
					<TabsTrigger value="subscriptions" disabled={!canReadSubs}>
						Subscriptions
					</TabsTrigger>
				</TabsList>
				<TabsContent value="plans">
					{canReadPlans ? <PlansContent /> : <PermissionHint permission={PLANS_READ} />}
				</TabsContent>
				<TabsContent value="flags">
					{canReadFlags ? (
						<FeatureFlagsContent />
					) : (
						<PermissionHint permission={FEATURE_FLAGS_READ} />
					)}
				</TabsContent>
				<TabsContent value="subscriptions">
					{canReadSubs ? <SubscriptionsContent /> : <PermissionHint permission={BILLING_READ} />}
				</TabsContent>
			</Tabs>
		</div>
	);
}

function PermissionHint({ permission }: { permission: string }) {
	return (
		<p className="py-6 text-center text-sm text-muted-foreground">
			Requires the <span className="font-mono">{permission}</span> permission.
		</p>
	);
}
