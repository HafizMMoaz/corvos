"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import type { AdminFreeQuotaUserRead } from "@/contracts/types/admin-llm.types";
import { QuotaResetConfirmDialog } from "./QuotaResetConfirmDialog";
import { QuotaSnapshotCard } from "./QuotaSnapshotCard";

const NO_WRITE_HINT = "Requires the quotas:write permission";

interface QuotaUserLookupProps {
	canWrite: boolean;
	onLookup: (userId: string) => Promise<AdminFreeQuotaUserRead>;
	onReset: (userId: string) => Promise<AdminFreeQuotaUserRead>;
}

/** A UUID text input + "Look up" button, rendering one user's quota snapshot with its own scoped reset. */
export function QuotaUserLookup({ canWrite, onLookup, onReset }: QuotaUserLookupProps) {
	const [userIdInput, setUserIdInput] = useState("");
	const [isLookingUp, setIsLookingUp] = useState(false);
	const [isResetting, setIsResetting] = useState(false);
	const [result, setResult] = useState<AdminFreeQuotaUserRead | null>(null);
	const [confirmResetOpen, setConfirmResetOpen] = useState(false);

	async function handleLookup() {
		const userId = userIdInput.trim();
		if (!userId) return;
		setIsLookingUp(true);
		try {
			const data = await onLookup(userId);
			setResult(data);
		} catch {
			// hook already surfaced a toast with the server's error message
			setResult(null);
		} finally {
			setIsLookingUp(false);
		}
	}

	async function handleConfirmReset() {
		if (!result) return;
		setIsResetting(true);
		try {
			const data = await onReset(result.user_id);
			setResult(data);
			setConfirmResetOpen(false);
		} catch {
			// hook already surfaced a toast; keep the dialog open to retry
		} finally {
			setIsResetting(false);
		}
	}

	return (
		<div className="space-y-3">
			<div className="space-y-2">
				<Label htmlFor="quota-user-id">User ID</Label>
				<div className="flex gap-2">
					<Input
						id="quota-user-id"
						value={userIdInput}
						onChange={(event) => setUserIdInput(event.target.value)}
						onKeyDown={(event) => {
							if (event.key === "Enter") {
								event.preventDefault();
								void handleLookup();
							}
						}}
						placeholder="00000000-0000-0000-0000-000000000000"
						className="font-mono text-xs"
						disabled={isLookingUp}
					/>
					<Button
						type="button"
						variant="outline"
						onClick={() => void handleLookup()}
						disabled={isLookingUp || !userIdInput.trim()}
						className="relative shrink-0 min-w-[96px]"
					>
						<span className={isLookingUp ? "opacity-0" : ""}>Look up</span>
						{isLookingUp && <Spinner size="sm" className="absolute" />}
					</Button>
				</div>
			</div>

			{result && (
				<Card>
					<CardContent className="space-y-3 p-4">
						<QuotaSnapshotCard
							periodStart={result.period_start}
							tokensReserved={result.tokens_reserved}
							tokensUsed={result.tokens_used}
							capTokens={result.cap_tokens}
							updatedAt={result.updated_at}
						/>
						<div className="flex justify-end">
							<Button
								size="sm"
								variant="outline"
								className="text-destructive hover:text-destructive"
								onClick={() => setConfirmResetOpen(true)}
								disabled={!canWrite}
								title={canWrite ? undefined : NO_WRITE_HINT}
							>
								Reset this user's quota
							</Button>
						</div>
					</CardContent>
				</Card>
			)}

			<QuotaResetConfirmDialog
				open={confirmResetOpen}
				onOpenChange={setConfirmResetOpen}
				isMutating={isResetting}
				title="Reset this user's quota?"
				description={
					<>
						This zeroes the free-tier token usage for user{" "}
						<span className="font-mono text-xs text-foreground">{result?.user_id}</span> for the
						current period. This cannot be undone.
					</>
				}
				onConfirm={handleConfirmReset}
			/>
		</div>
	);
}
