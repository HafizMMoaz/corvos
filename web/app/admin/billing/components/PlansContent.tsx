"use client";

import { Pencil, Settings2, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { PlanRead } from "@/contracts/types/admin-billing.types";
import { useAdminBilling } from "@/hooks/use-admin-billing";
import { useAdminPermissions } from "../../admin-shell";
import { PlanDeleteDialog } from "./PlanDeleteDialog";
import { PlanDetailDialog } from "./PlanDetailDialog";
import { PlanFormDialog } from "./PlanFormDialog";

// PlatformPermission values, from backend/app/db.py.
const PLANS_WRITE = "plans:write";
const NO_WRITE_HINT = "Requires the plans:write permission";

/** 1_000_000 micros == $1.00 -- same convention as credit_micros_balance. */
function formatMonthlyCredits(micros: number): string {
	const dollars = micros / 1_000_000;
	return `$${dollars.toLocaleString(undefined, { maximumFractionDigits: 2 })}/mo`;
}

export function PlansContent() {
	const { plans, featureFlags, isLoading, isMutating, createPlan, updatePlan, deletePlan } =
		useAdminBilling();
	const { has } = useAdminPermissions();
	const canWrite = has(PLANS_WRITE);

	const [formOpen, setFormOpen] = useState(false);
	const [editingPlan, setEditingPlan] = useState<PlanRead | null>(null);
	const [deleteTarget, setDeleteTarget] = useState<PlanRead | null>(null);
	const [detailTarget, setDetailTarget] = useState<PlanRead | null>(null);

	function openCreateDialog() {
		setEditingPlan(null);
		setFormOpen(true);
	}

	function openEditDialog(plan: PlanRead) {
		setEditingPlan(plan);
		setFormOpen(true);
	}

	return (
		<div className="space-y-4 min-w-0">
			<div className="flex items-center justify-between gap-3">
				<div>
					<h4 className="text-sm font-semibold tracking-tight">Plans</h4>
					<p className="text-xs text-muted-foreground">
						Subscription plans and the monthly credit grant each one carries. Entitlements and
						feature limits live inside each plan.
					</p>
				</div>
				<Button
					size="sm"
					className="shrink-0"
					onClick={openCreateDialog}
					disabled={!canWrite}
					title={canWrite ? undefined : NO_WRITE_HINT}
				>
					Add plan
				</Button>
			</div>

			{isLoading ? (
				<div className="space-y-2">
					{["skeleton-a", "skeleton-b", "skeleton-c"].map((key) => (
						<Skeleton key={key} className="h-12 w-full" />
					))}
				</div>
			) : plans.length > 0 ? (
				<div className="rounded-md border">
					<Table>
						<TableHeader>
							<TableRow>
								<TableHead>Plan</TableHead>
								<TableHead>Monthly credits</TableHead>
								<TableHead>Paddle price</TableHead>
								<TableHead>Status</TableHead>
								<TableHead className="text-right">Actions</TableHead>
							</TableRow>
						</TableHeader>
						<TableBody>
							{plans.map((plan) => (
								<TableRow key={plan.id}>
									<TableCell>
										<div className="flex flex-col">
											<span className="font-medium">{plan.name}</span>
											<span className="font-mono text-xs text-muted-foreground">
												{plan.plan_key}
											</span>
										</div>
									</TableCell>
									<TableCell className="text-muted-foreground">
										{formatMonthlyCredits(plan.monthly_credit_micros)}
									</TableCell>
									<TableCell>
										{plan.paddle_price_id ? (
											<span className="font-mono text-xs">{plan.paddle_price_id}</span>
										) : (
											<span className="text-xs text-muted-foreground">Not linked</span>
										)}
									</TableCell>
									<TableCell>
										{plan.is_active ? (
											<Badge variant="secondary">Active</Badge>
										) : (
											<Badge variant="outline">Inactive</Badge>
										)}
									</TableCell>
									<TableCell className="text-right">
										<div className="flex justify-end gap-1">
											<Button
												variant="ghost"
												size="icon"
												className="h-8 w-8"
												onClick={() => setDetailTarget(plan)}
												title="Entitlements & feature values"
												aria-label={`Manage ${plan.name} entitlements`}
											>
												<Settings2 className="h-4 w-4" />
											</Button>
											<Button
												variant="ghost"
												size="icon"
												className="h-8 w-8"
												onClick={() => openEditDialog(plan)}
												disabled={!canWrite}
												title={canWrite ? undefined : NO_WRITE_HINT}
												aria-label={`Edit ${plan.name}`}
											>
												<Pencil className="h-4 w-4" />
											</Button>
											<Button
												variant="ghost"
												size="icon"
												className="h-8 w-8 text-muted-foreground hover:text-destructive"
												onClick={() => setDeleteTarget(plan)}
												disabled={!canWrite}
												title={canWrite ? undefined : NO_WRITE_HINT}
												aria-label={`Delete ${plan.name}`}
											>
												<Trash2 className="h-4 w-4" />
											</Button>
										</div>
									</TableCell>
								</TableRow>
							))}
						</TableBody>
					</Table>
				</div>
			) : (
				<p className="py-6 text-center text-sm text-muted-foreground">
					No plans yet. Users without a plan get unrestricted model access with every feature flag
					off.
				</p>
			)}

			<PlanFormDialog
				open={formOpen}
				onOpenChange={setFormOpen}
				plan={editingPlan}
				isMutating={isMutating}
				onCreate={createPlan}
				onUpdate={updatePlan}
			/>

			<PlanDeleteDialog
				plan={deleteTarget}
				onOpenChange={(open) => !open && setDeleteTarget(null)}
				isMutating={isMutating}
				onConfirm={async () => {
					if (!deleteTarget) return;
					await deletePlan(deleteTarget.id);
					setDeleteTarget(null);
				}}
			/>

			<PlanDetailDialog
				plan={detailTarget}
				featureFlags={featureFlags}
				onOpenChange={(open) => !open && setDetailTarget(null)}
			/>
		</div>
	);
}
