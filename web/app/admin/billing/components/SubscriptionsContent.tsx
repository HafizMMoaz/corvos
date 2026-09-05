"use client";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { useAdminBilling } from "@/hooks/use-admin-billing";

/** Paddle's raw subscription statuses, verbatim from webhooks. */
const ACTIVE_STATUSES = new Set(["active", "trialing"]);

function formatDateTime(iso: string | null): string {
	if (!iso) return "-";
	return new Date(iso).toLocaleString(undefined, {
		dateStyle: "medium",
		timeStyle: "short",
	});
}

/**
 * Read-only list of Paddle subscriptions. Subscription state always flows in
 * from Paddle webhooks (`upsert_subscription_from_webhook`), so there is
 * deliberately no admin write action here -- cancel/pause happens in Paddle.
 */
export function SubscriptionsContent() {
	const { subscriptions, isLoading } = useAdminBilling();

	const activeCount = subscriptions.filter((sub) => ACTIVE_STATUSES.has(sub.status)).length;

	return (
		<div className="space-y-4 min-w-0">
			<div>
				<h4 className="text-sm font-semibold tracking-tight">Subscriptions</h4>
				<p className="text-xs text-muted-foreground">
					Live Paddle subscriptions, synced from webhooks.
					{subscriptions.length > 0 &&
						` ${activeCount} of ${subscriptions.length} active/trialing.`}{" "}
					Cancellations and pauses are managed in Paddle, not here.
				</p>
			</div>

			{isLoading ? (
				<div className="space-y-2">
					{["skeleton-a", "skeleton-b", "skeleton-c"].map((key) => (
						<Skeleton key={key} className="h-12 w-full" />
					))}
				</div>
			) : subscriptions.length > 0 ? (
				<div className="rounded-md border">
					<Table>
						<TableHeader>
							<TableRow>
								<TableHead>User</TableHead>
								<TableHead>Plan</TableHead>
								<TableHead>Status</TableHead>
								<TableHead>Current period ends</TableHead>
								<TableHead>Renewal</TableHead>
								<TableHead>Updated</TableHead>
							</TableRow>
						</TableHeader>
						<TableBody>
							{subscriptions.map((sub) => (
								<TableRow key={sub.id}>
									<TableCell>
										<span className="font-medium">{sub.user_email}</span>
									</TableCell>
									<TableCell className="text-muted-foreground">
										{sub.plan_name ?? (
											<span className="text-xs" title="Price id no longer matches any plan">
												Unknown plan
											</span>
										)}
									</TableCell>
									<TableCell>
										<Badge variant={ACTIVE_STATUSES.has(sub.status) ? "secondary" : "outline"}>
											{sub.status}
										</Badge>
									</TableCell>
									<TableCell className="text-muted-foreground">
										{formatDateTime(sub.current_period_end)}
									</TableCell>
									<TableCell className="text-muted-foreground">
										{sub.cancel_at_period_end ? "Cancels" : "Renews"}
									</TableCell>
									<TableCell className="text-muted-foreground">
										{formatDateTime(sub.updated_at)}
									</TableCell>
								</TableRow>
							))}
						</TableBody>
					</Table>
				</div>
			) : (
				<p className="py-6 text-center text-sm text-muted-foreground">
					No Paddle subscriptions yet. They appear here automatically once checkout and webhooks are
					live.
				</p>
			)}
		</div>
	);
}
