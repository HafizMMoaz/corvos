"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminLlmQuota } from "@/hooks/use-admin-llm-quota";
import { useAdminPermissions } from "../../admin-shell";
import { QuotaResetConfirmDialog } from "./QuotaResetConfirmDialog";
import { QuotaSnapshotCard } from "./QuotaSnapshotCard";
import { QuotaUserLookup } from "./QuotaUserLookup";

// PlatformPermission value, from backend/app/db.py.
const QUOTAS_WRITE = "quotas:write";
const NO_WRITE_HINT = "Requires the quotas:write permission";

export function QuotaContent() {
	const { globalQuota, isLoading, isMutating, resetGlobalQuota, lookupUser, resetUserQuota } =
		useAdminLlmQuota();
	const { has } = useAdminPermissions();
	const canWrite = has(QUOTAS_WRITE);

	const [confirmResetOpen, setConfirmResetOpen] = useState(false);

	async function handleConfirmReset() {
		try {
			await resetGlobalQuota();
			setConfirmResetOpen(false);
		} catch {
			// hook already surfaced a toast; keep the dialog open to retry
		}
	}

	return (
		<div className="space-y-6 min-w-0">
			<div>
				<h4 className="text-sm font-semibold tracking-tight">Free-tier quota</h4>
				<p className="text-xs text-muted-foreground">
					Platform-wide and per-user free-tier token usage for the current period.
				</p>
			</div>

			<div className="space-y-3">
				<div className="flex items-center justify-between gap-3">
					<h5 className="text-sm font-medium">Platform-wide</h5>
					<Button
						size="sm"
						variant="outline"
						className="text-destructive hover:text-destructive"
						onClick={() => setConfirmResetOpen(true)}
						disabled={!canWrite || isLoading}
						title={canWrite ? undefined : NO_WRITE_HINT}
					>
						Reset platform-wide quota
					</Button>
				</div>

				{isLoading ? (
					<Skeleton className="h-24 w-full" />
				) : globalQuota ? (
					<Card>
						<CardContent className="p-4">
							<QuotaSnapshotCard
								periodStart={globalQuota.period_start}
								tokensReserved={globalQuota.tokens_reserved}
								tokensUsed={globalQuota.tokens_used}
								capTokens={globalQuota.cap_tokens}
								updatedAt={globalQuota.updated_at}
							/>
						</CardContent>
					</Card>
				) : (
					<p className="py-6 text-center text-sm text-muted-foreground">
						Failed to load platform-wide quota.
					</p>
				)}
			</div>

			<div className="space-y-3">
				<h5 className="text-sm font-medium">Look up a user</h5>
				<QuotaUserLookup canWrite={canWrite} onLookup={lookupUser} onReset={resetUserQuota} />
			</div>

			<QuotaResetConfirmDialog
				open={confirmResetOpen}
				onOpenChange={setConfirmResetOpen}
				isMutating={isMutating}
				title="Reset platform-wide quota?"
				description="This zeroes the free-tier token usage shared by every user for the current period. This cannot be undone."
				onConfirm={handleConfirmReset}
			/>
		</div>
	);
}
