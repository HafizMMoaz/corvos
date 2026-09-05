"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import type { FeatureFlagRead, PlanRead } from "@/contracts/types/admin-billing.types";
import type { AdminLlmModelRead } from "@/contracts/types/admin-llm.types";
import { adminBillingApiService } from "@/lib/apis/admin-billing.service";
import { adminLlmApiService } from "@/lib/apis/admin-llm.service";
import { AppError } from "@/lib/error";
import { useAdminPermissions } from "../../admin-shell";

// PlatformPermission values, from backend/app/db.py.
const PLANS_WRITE = "plans:write";
const NO_WRITE_HINT = "Requires the plans:write permission";

interface PlanDetailDialogProps {
	/** Plan whose entitlements are being managed, or null to close. */
	plan: PlanRead | null;
	featureFlags: FeatureFlagRead[];
	onOpenChange: (open: boolean) => void;
}

function toastMessage(action: string, error: unknown): string {
	return error instanceof AppError ? error.message : `Failed to ${action}`;
}

/**
 * Per-plan manager for the two things a plan grants:
 *
 * 1. Model entitlements -- an allowlist of model `config_id`s. The ruled
 *    default is inverted from what it looks like: an EMPTY list means
 *    unrestricted (every model allowed), not "no models". Selecting specific
 *    models is what restricts the plan. Saves as a diff of add/remove calls.
 * 2. Feature values -- which feature flags the plan turns on. An absent flag
 *    is off by default; switches apply immediately (PUT on, DELETE reverts to
 *    the default) rather than through a save button.
 */
export function PlanDetailDialog({ plan, featureFlags, onOpenChange }: PlanDetailDialogProps) {
	const { has } = useAdminPermissions();
	const canWrite = has(PLANS_WRITE);

	const [models, setModels] = useState<AdminLlmModelRead[]>([]);
	const [entitledIds, setEntitledIds] = useState<number[]>([]);
	const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
	const [featureValues, setFeatureValues] = useState<Map<number, boolean>>(new Map());
	const [isLoading, setIsLoading] = useState(false);
	const [isSavingEntitlements, setIsSavingEntitlements] = useState(false);
	const [isTogglingFlag, setIsTogglingFlag] = useState(false);

	const load = useCallback(async () => {
		if (!plan) return;
		setIsLoading(true);
		try {
			const [modelList, entitlementIds, values] = await Promise.all([
				adminLlmApiService.getModels(),
				adminBillingApiService.getPlanModelEntitlements(plan.id),
				adminBillingApiService.getPlanFeatureValues(plan.id),
			]);
			setModels(modelList);
			setEntitledIds(entitlementIds);
			setSelectedIds(new Set(entitlementIds));
			setFeatureValues(new Map(values.map((value) => [value.feature_flag_id, value.enabled])));
		} catch (error) {
			console.error("Failed to load plan details:", error);
			toast.error(toastMessage("load plan details", error));
		} finally {
			setIsLoading(false);
		}
	}, [plan]);

	useEffect(() => {
		if (plan) void load();
	}, [plan, load]);

	const hasChanges =
		selectedIds.size !== entitledIds.length || entitledIds.some((id) => !selectedIds.has(id));

	function toggleModel(modelId: number, checked: boolean) {
		setSelectedIds((current) => {
			const next = new Set(current);
			if (checked) next.add(modelId);
			else next.delete(modelId);
			return next;
		});
	}

	async function saveEntitlements() {
		if (!plan) return;
		setIsSavingEntitlements(true);
		try {
			const target = Array.from(selectedIds);
			const toAdd = target.filter((id) => !entitledIds.includes(id));
			const toRemove = entitledIds.filter((id) => !selectedIds.has(id));
			for (const configId of toAdd) {
				await adminBillingApiService.addPlanModelEntitlement(plan.id, { config_id: configId });
			}
			for (const configId of toRemove) {
				await adminBillingApiService.removePlanModelEntitlement(plan.id, configId);
			}
			setEntitledIds(target);
			toast.success(
				toAdd.length + toRemove.length === 0
					? "No entitlement changes"
					: "Model entitlements updated"
			);
		} catch (error) {
			console.error("Failed to save model entitlements:", error);
			toast.error(toastMessage("save model entitlements", error));
			// reload to resync local state with what actually landed
			await load();
		} finally {
			setIsSavingEntitlements(false);
		}
	}

	async function toggleFeatureValue(flag: FeatureFlagRead, enabled: boolean) {
		if (!plan) return;
		setIsTogglingFlag(true);
		try {
			if (enabled) {
				await adminBillingApiService.setPlanFeatureValue(plan.id, flag.id, { enabled: true });
			} else {
				// Reverting to "off" removes the configured row entirely --
				// absent means the disabled default, same observable behavior.
				await adminBillingApiService.deletePlanFeatureValue(plan.id, flag.id);
			}
			setFeatureValues((current) => {
				const next = new Map(current);
				if (enabled) next.set(flag.id, true);
				else next.delete(flag.id);
				return next;
			});
			toast.success(`"${flag.name}" ${enabled ? "enabled" : "disabled"} for this plan`);
		} catch (error) {
			console.error("Failed to set plan feature value:", error);
			toast.error(toastMessage("update feature value", error));
		} finally {
			setIsTogglingFlag(false);
		}
	}

	return (
		<Dialog open={plan !== null} onOpenChange={onOpenChange}>
			<DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
				<DialogHeader>
					<DialogTitle>{plan ? `${plan.name} - entitlements & limits` : ""}</DialogTitle>
					<DialogDescription>
						Control which models this plan allows and which features it turns on. Users on no plan
						at all get unrestricted model access with every feature off.
					</DialogDescription>
				</DialogHeader>

				{isLoading ? (
					<div className="space-y-2">
						<Skeleton className="h-24 w-full" />
						<Skeleton className="h-24 w-full" />
					</div>
				) : (
					<div className="space-y-6">
						{/* ---- Model entitlements ---- */}
						<div className="space-y-3">
							<div className="flex items-center justify-between gap-3">
								<div>
									<h5 className="text-sm font-medium">Model entitlements</h5>
									<p className="text-xs text-muted-foreground">
										Selecting specific models restricts the plan to that allowlist.
									</p>
								</div>
								<Button
									size="sm"
									onClick={() => void saveEntitlements()}
									disabled={!canWrite || isSavingEntitlements || !hasChanges}
									title={canWrite ? undefined : NO_WRITE_HINT}
									className="relative shrink-0 min-w-[90px]"
								>
									<span className={isSavingEntitlements ? "opacity-0" : ""}>Save</span>
									{isSavingEntitlements && <Spinner size="sm" className="absolute" />}
								</Button>
							</div>

							{selectedIds.size === 0 && (
								<div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs">
									<Badge variant="outline" className="mr-2 border-amber-500/50 text-amber-600">
										Unrestricted
									</Badge>
									No models selected - members of this plan can use <strong>every</strong> model in
									the catalog.
								</div>
							)}

							{models.length === 0 ? (
								<p className="py-4 text-center text-sm text-muted-foreground">
									No models configured yet - add them under LLM &amp; Quotas first.
								</p>
							) : (
								<ScrollArea className="h-56 rounded-md border">
									<div className="divide-y">
										{models.map((model) => (
											<Label
												key={model.id}
												htmlFor={`plan-model-${plan?.id}-${model.id}`}
												className="flex cursor-pointer items-center justify-between gap-3 px-3 py-2.5 font-normal hover:bg-muted/50"
											>
												<span className="flex min-w-0 flex-col">
													<span className="flex items-center gap-2 text-sm font-medium">
														{model.name}
														{model.billing_tier === "free" && (
															<Badge variant="secondary">free</Badge>
														)}
														{!model.is_enabled && <Badge variant="outline">off</Badge>}
													</span>
													<span className="truncate font-mono text-xs text-muted-foreground">
														{model.model_name}
													</span>
												</span>
												<input
													id={`plan-model-${plan?.id}-${model.id}`}
													type="checkbox"
													className="h-4 w-4 shrink-0 accent-foreground"
													checked={selectedIds.has(model.id)}
													onChange={(event) => toggleModel(model.id, event.target.checked)}
													disabled={!canWrite || isSavingEntitlements}
												/>
											</Label>
										))}
									</div>
								</ScrollArea>
							)}
						</div>

						{/* ---- Feature values ---- */}
						<div className="space-y-3">
							<div>
								<h5 className="text-sm font-medium">Feature limits</h5>
								<p className="text-xs text-muted-foreground">
									Features this plan turns on. Users can be granted exceptions per-user from their
									profile in Users.
								</p>
							</div>

							{featureFlags.length === 0 ? (
								<p className="py-4 text-center text-sm text-muted-foreground">
									No feature flags defined yet - create some in the Feature Flags tab.
								</p>
							) : (
								<div className="rounded-md border divide-y">
									{featureFlags.map((flag) => (
										<div
											key={flag.id}
											className="flex items-center justify-between gap-3 px-3 py-2.5"
										>
											<div className="min-w-0">
												<p className="text-sm font-medium">{flag.name}</p>
												<p className="truncate font-mono text-xs text-muted-foreground">
													{flag.flag_key}
												</p>
											</div>
											<Switch
												checked={featureValues.get(flag.id) === true}
												onCheckedChange={(checked) => void toggleFeatureValue(flag, checked)}
												disabled={!canWrite || isTogglingFlag}
												title={canWrite ? undefined : NO_WRITE_HINT}
												aria-label={`Toggle ${flag.name}`}
											/>
										</div>
									))}
								</div>
							)}
						</div>
					</div>
				)}

				<DialogFooter>
					<Button size="sm" variant="secondary" onClick={() => onOpenChange(false)}>
						Close
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
