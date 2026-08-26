"use client";

import { Progress } from "@/components/ui/progress";

interface QuotaSnapshotCardProps {
	/** Null fields mean "never reserved free-tier quota yet" (only possible for a per-user snapshot). */
	periodStart: string | null;
	tokensReserved: number | null;
	tokensUsed: number | null;
	capTokens: number;
	updatedAt: string | null;
}

/**
 * Renders one free-tier quota snapshot (period, reserved/used vs. cap, a
 * used-of-cap indicator). Shared between the global card and the per-user
 * lookup result so both render identically. A user who has never used the
 * free tier gets an explicit "no usage yet" state rather than zeros, since
 * zero usage and "never touched this" are different facts worth telling apart.
 */
export function QuotaSnapshotCard({
	periodStart,
	tokensReserved,
	tokensUsed,
	capTokens,
	updatedAt,
}: QuotaSnapshotCardProps) {
	const hasUsage = tokensUsed !== null && tokensReserved !== null && periodStart !== null;

	if (!hasUsage) {
		return (
			<div className="space-y-1">
				<p className="text-sm text-muted-foreground">No usage yet.</p>
				<p className="text-xs text-muted-foreground">
					Cap: {capTokens.toLocaleString()} tokens / period
				</p>
			</div>
		);
	}

	const usedPct = capTokens > 0 ? (tokensUsed / capTokens) * 100 : 0;

	return (
		<div className="space-y-3">
			<div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
				<div>
					<p className="text-xs text-muted-foreground">Period</p>
					<p className="font-medium">{periodStart}</p>
				</div>
				<div>
					<p className="text-xs text-muted-foreground">Used</p>
					<p className="font-medium">{tokensUsed.toLocaleString()}</p>
				</div>
				<div>
					<p className="text-xs text-muted-foreground">Reserved</p>
					<p className="font-medium">{tokensReserved.toLocaleString()}</p>
				</div>
				<div>
					<p className="text-xs text-muted-foreground">Cap</p>
					<p className="font-medium">{capTokens.toLocaleString()}</p>
				</div>
			</div>

			<div className="space-y-1">
				<Progress value={usedPct} />
				<p className="text-xs text-muted-foreground">
					{usedPct.toFixed(1)}% of cap used
					{updatedAt ? ` · updated ${new Date(updatedAt).toLocaleString()}` : ""}
				</p>
			</div>
		</div>
	);
}
