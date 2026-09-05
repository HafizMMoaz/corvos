"use client";

import { Trash2 } from "lucide-react";
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
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import type {
	AdminUserListItemRead,
	FeatureFlagRead,
	PlanRead,
	UserEntitlementsRead,
	UserFeatureOverrideRead,
} from "@/contracts/types/admin-billing.types";
import { adminBillingApiService } from "@/lib/apis/admin-billing.service";
import { AppError } from "@/lib/error";
import { useAdminPermissions } from "../../admin-shell";

// PlatformPermission values, from backend/app/db.py.
const BILLING_WRITE = "billing:write";
const BILLING_READ = "billing:read";
const NO_WRITE_HINT = "Requires the billing:write permission";

const NO_PLAN_VALUE = "__no_plan__";

interface UserDetailDialogProps {
	/** User being inspected, or null when the dialog should be closed. */
	user: AdminUserListItemRead | null;
	onOpenChange: (open: boolean) => void;
}

function toastMessage(action: string, error: unknown): string {
	return error instanceof AppError ? error.message : `Failed to ${action}`;
}

function formatDateTime(iso: string | null): string {
	if (!iso) return "-";
	return new Date(iso).toLocaleString(undefined, {
		dateStyle: "medium",
		timeStyle: "short",
	});
}

/**
 * Per-user billing surface: plan assignment (does NOT touch their credit
 * balance -- that stays exclusively on the Paddle fulfillment track), the
 * resolved entitlement state (plan + overrides merged), and feature overrides
 * with optional expiry.
 */
export function UserDetailDialog({ user, onOpenChange }: UserDetailDialogProps) {
	const { has } = useAdminPermissions();
	const canRead = has(BILLING_READ);
	const canWrite = has(BILLING_WRITE);

	const [plans, setPlans] = useState<PlanRead[]>([]);
	const [featureFlags, setFeatureFlags] = useState<FeatureFlagRead[]>([]);
	const [entitlements, setEntitlements] = useState<UserEntitlementsRead | null>(null);
	const [overrides, setOverrides] = useState<UserFeatureOverrideRead[]>([]);
	const [selectedPlanId, setSelectedPlanId] = useState<string>(NO_PLAN_VALUE);
	const [isLoading, setIsLoading] = useState(false);
	const [isSavingPlan, setIsSavingPlan] = useState(false);
	const [isMutatingOverride, setIsMutatingOverride] = useState(false);

	// Add-override draft (only admins with billing:write see the form).
	const [draftFlagId, setDraftFlagId] = useState<string>("");
	const [draftEnabled, setDraftEnabled] = useState(true);
	const [draftExpiresAt, setDraftExpiresAt] = useState("");

	const load = useCallback(async () => {
		if (!user) return;
		setIsLoading(true);
		try {
			const [plansList, flagsList, entitlementsData, overridesData] = await Promise.all([
				adminBillingApiService.getPlans(),
				adminBillingApiService.getFeatureFlags(),
				adminBillingApiService.getUserEntitlements(user.id),
				adminBillingApiService.getUserFeatureOverrides(user.id),
			]);
			setPlans(plansList);
			setFeatureFlags(flagsList);
			setEntitlements(entitlementsData);
			setOverrides(overridesData);
			setSelectedPlanId(entitlementsData.plan ? String(entitlementsData.plan.id) : NO_PLAN_VALUE);
		} catch (error) {
			console.error("Failed to load user billing details:", error);
			toast.error(toastMessage("load user details", error));
		} finally {
			setIsLoading(false);
		}
	}, [user]);

	useEffect(() => {
		if (user) void load();
	}, [user, load]);

	const flagById = new Map(featureFlags.map((flag) => [flag.id, flag]));

	async function savePlanAssignment() {
		if (!user) return;
		setIsSavingPlan(true);
		try {
			await adminBillingApiService.setUserPlan(user.id, {
				plan_id: selectedPlanId === NO_PLAN_VALUE ? null : Number(selectedPlanId),
			});
			toast.success("Plan assignment saved");
			await load();
		} catch (error) {
			console.error("Failed to set user plan:", error);
			toast.error(toastMessage("assign plan", error));
		} finally {
			setIsSavingPlan(false);
		}
	}

	async function addOverride() {
		if (!user || !draftFlagId) return;
		setIsMutatingOverride(true);
		try {
			await adminBillingApiService.setUserFeatureOverride(user.id, Number(draftFlagId), {
				enabled: draftEnabled,
				expires_at: draftExpiresAt === "" ? null : new Date(draftExpiresAt).toISOString(),
			});
			toast.success("Feature override saved");
			setDraftFlagId("");
			setDraftEnabled(true);
			setDraftExpiresAt("");
			await load();
		} catch (error) {
			console.error("Failed to set user feature override:", error);
			toast.error(toastMessage("set override", error));
		} finally {
			setIsMutatingOverride(false);
		}
	}

	async function removeOverride(featureFlagId: number) {
		if (!user) return;
		setIsMutatingOverride(true);
		try {
			await adminBillingApiService.deleteUserFeatureOverride(user.id, featureFlagId);
			toast.success("Feature override removed");
			await load();
		} catch (error) {
			console.error("Failed to remove user feature override:", error);
			toast.error(toastMessage("remove override", error));
		} finally {
			setIsMutatingOverride(false);
		}
	}

	return (
		<Dialog open={user !== null} onOpenChange={onOpenChange}>
			<DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
				<DialogHeader>
					<DialogTitle>{user ? user.email : ""}</DialogTitle>
					<DialogDescription>
						Plan assignment, resolved entitlements, and per-user feature overrides. Plan changes
						never touch this user's credit balance.
					</DialogDescription>
				</DialogHeader>

				{isLoading || !entitlements ? (
					<div className="space-y-2">
						<Skeleton className="h-20 w-full" />
						<Skeleton className="h-20 w-full" />
						<Skeleton className="h-20 w-full" />
					</div>
				) : (
					<div className="space-y-6">
						{/* ---- Plan assignment ---- */}
						<div className="space-y-2">
							<Label htmlFor="user-plan">Plan</Label>
							<div className="flex items-center gap-2">
								<Select
									value={selectedPlanId}
									onValueChange={setSelectedPlanId}
									disabled={!canWrite || isSavingPlan}
								>
									<SelectTrigger id="user-plan" className="w-full">
										<SelectValue placeholder="No plan" />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value={NO_PLAN_VALUE}>
											No plan (unrestricted models, flags off)
										</SelectItem>
										{plans.map((plan) => (
											<SelectItem key={plan.id} value={String(plan.id)}>
												{plan.name}
												{!plan.is_active ? " (inactive)" : ""}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
								<Button
									size="sm"
									className="relative shrink-0 min-w-[80px]"
									onClick={() => void savePlanAssignment()}
									disabled={!canWrite || isSavingPlan}
									title={canWrite ? undefined : NO_WRITE_HINT}
								>
									<span className={isSavingPlan ? "opacity-0" : ""}>Save</span>
									{isSavingPlan && <Spinner size="sm" className="absolute" />}
								</Button>
							</div>
						</div>

						{/* ---- Resolved entitlements ---- */}
						{canRead && (
							<div className="space-y-3">
								<div>
									<h5 className="text-sm font-medium">Resolved entitlements</h5>
									<p className="text-xs text-muted-foreground">
										What this user effectively gets once their plan and overrides are merged.
									</p>
								</div>

								<div className="grid grid-cols-2 gap-2 rounded-md border p-3 text-sm">
									<div className="flex items-center gap-2">
										<span className="text-muted-foreground">Models:</span>
										{entitlements.unrestricted_models ? (
											<Badge variant="secondary">Unrestricted</Badge>
										) : (
											<Badge variant="outline">
												{entitlements.allowed_config_ids.length} allowed
											</Badge>
										)}
									</div>
									<div className="flex items-center gap-2">
										<span className="text-muted-foreground">Features on:</span>
										<Badge variant="outline">
											{Object.values(entitlements.feature_flags).filter(Boolean).length}
										</Badge>
									</div>
								</div>

								{featureFlags.length > 0 && (
									<div className="rounded-md border divide-y">
										{featureFlags.map((flag) => {
											const isOn = entitlements.feature_flags[flag.flag_key] === true;
											const override = overrides.find((o) => o.feature_flag_id === flag.id);
											return (
												<div
													key={flag.id}
													className="flex items-center justify-between gap-3 px-3 py-2.5"
												>
													<div className="min-w-0">
														<p className="text-sm font-medium">{flag.name}</p>
														<p className="truncate font-mono text-xs text-muted-foreground">
															{flag.flag_key}
															{override && " · overridden"}
														</p>
													</div>
													<Badge variant={isOn ? "secondary" : "outline"}>
														{isOn ? "On" : "Off"}
													</Badge>
												</div>
											);
										})}
									</div>
								)}
							</div>
						)}

						{/* ---- Feature overrides ---- */}
						{canRead && (
							<div className="space-y-3">
								<div>
									<h5 className="text-sm font-medium">Feature overrides</h5>
									<p className="text-xs text-muted-foreground">
										Force a feature on or off for this user, regardless of their plan. Optional
										expiry reverts them to the plan default when it passes.
									</p>
								</div>

								{overrides.length > 0 ? (
									<div className="rounded-md border divide-y">
										{overrides.map((override) => {
											const flag = flagById.get(override.feature_flag_id);
											const expired =
												override.expires_at !== null && new Date(override.expires_at) < new Date();
											return (
												<div
													key={override.id}
													className="flex items-center justify-between gap-3 px-3 py-2.5"
												>
													<div className="min-w-0">
														<p className="flex items-center gap-2 text-sm font-medium">
															{flag?.name ?? `Flag #${override.feature_flag_id}`}
															<Badge variant={override.enabled ? "secondary" : "outline"}>
																{override.enabled ? "on" : "off"}
															</Badge>
															{expired && (
																<Badge variant="outline" className="text-muted-foreground">
																	expired
																</Badge>
															)}
														</p>
														<p className="truncate text-xs text-muted-foreground">
															{override.expires_at
																? `Until ${formatDateTime(override.expires_at)}`
																: "No expiry"}
														</p>
													</div>
													<Button
														variant="ghost"
														size="icon"
														className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive"
														onClick={() => void removeOverride(override.feature_flag_id)}
														disabled={!canWrite || isMutatingOverride}
														title={canWrite ? "Remove override" : NO_WRITE_HINT}
														aria-label="Remove override"
													>
														<Trash2 className="h-4 w-4" />
													</Button>
												</div>
											);
										})}
									</div>
								) : (
									<p className="py-2 text-center text-sm text-muted-foreground">
										No overrides - every feature follows the plan default.
									</p>
								)}

								{canWrite && featureFlags.length > 0 && (
									<div className="space-y-3 rounded-md border p-3">
										<div className="grid grid-cols-2 gap-3">
											<div className="space-y-2">
												<Label htmlFor="override-flag">Feature</Label>
												<Select
													value={draftFlagId}
													onValueChange={setDraftFlagId}
													disabled={isMutatingOverride}
												>
													<SelectTrigger id="override-flag" className="w-full">
														<SelectValue placeholder="Choose a feature" />
													</SelectTrigger>
													<SelectContent>
														{featureFlags.map((flag) => (
															<SelectItem key={flag.id} value={String(flag.id)}>
																{flag.name}
															</SelectItem>
														))}
													</SelectContent>
												</Select>
											</div>
											<div className="space-y-2">
												<Label htmlFor="override-expiry">Expires at (optional)</Label>
												<input
													id="override-expiry"
													type="datetime-local"
													value={draftExpiresAt}
													onChange={(event) => setDraftExpiresAt(event.target.value)}
													disabled={isMutatingOverride}
													className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
												/>
											</div>
										</div>
										<div className="flex items-center justify-between">
											<div className="flex items-center gap-2">
												<Switch
													id="override-enabled"
													checked={draftEnabled}
													onCheckedChange={setDraftEnabled}
													disabled={isMutatingOverride}
												/>
												<Label htmlFor="override-enabled" className="text-sm">
													{draftEnabled ? "Force on" : "Force off"}
												</Label>
											</div>
											<Button
												size="sm"
												className="relative min-w-[90px]"
												onClick={() => void addOverride()}
												disabled={isMutatingOverride || draftFlagId === ""}
											>
												<span className={isMutatingOverride ? "opacity-0" : ""}>Add override</span>
												{isMutatingOverride && <Spinner size="sm" className="absolute" />}
											</Button>
										</div>
									</div>
								)}
							</div>
						)}
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
