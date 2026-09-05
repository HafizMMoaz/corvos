"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type {
	AdminSubscriptionRead,
	FeatureFlagCreateRequest,
	FeatureFlagRead,
	FeatureFlagUpdateRequest,
	PlanCreateRequest,
	PlanRead,
	PlanUpdateRequest,
} from "@/contracts/types/admin-billing.types";
import { adminBillingApiService } from "@/lib/apis/admin-billing.service";
import { AppError } from "@/lib/error";

function toastMessage(action: string, error: unknown): string {
	return error instanceof AppError ? error.message : `Failed to ${action}`;
}

/**
 * Plans, feature flags, and subscriptions for the admin Billing & Plans page.
 * Model entitlements / feature values per plan are fetched on demand by
 * PlanDetailDialog (they're per-plan, not page-level state).
 */
export function useAdminBilling() {
	const [plans, setPlans] = useState<PlanRead[]>([]);
	const [featureFlags, setFeatureFlags] = useState<FeatureFlagRead[]>([]);
	const [subscriptions, setSubscriptions] = useState<AdminSubscriptionRead[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [isMutating, setIsMutating] = useState(false);

	const refresh = useCallback(async () => {
		setIsLoading(true);
		try {
			const [plansData, flagsData, subsData] = await Promise.all([
				adminBillingApiService.getPlans(),
				adminBillingApiService.getFeatureFlags(),
				adminBillingApiService.getSubscriptions(),
			]);
			setPlans(plansData);
			setFeatureFlags(flagsData);
			setSubscriptions(subsData);
		} catch (error) {
			console.error("Failed to load billing data:", error);
			toast.error("Failed to load billing data");
		} finally {
			setIsLoading(false);
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	// ---- Plans ----

	const createPlan = useCallback(
		async (body: PlanCreateRequest) => {
			setIsMutating(true);
			try {
				await adminBillingApiService.createPlan(body);
				await refresh();
				toast.success("Plan created");
			} catch (error) {
				console.error("Failed to create plan:", error);
				toast.error(toastMessage("create plan", error));
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	const updatePlan = useCallback(
		async (planId: number, body: PlanUpdateRequest) => {
			setIsMutating(true);
			try {
				await adminBillingApiService.updatePlan(planId, body);
				await refresh();
				toast.success("Plan updated");
			} catch (error) {
				console.error("Failed to update plan:", error);
				toast.error(toastMessage("update plan", error));
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	const deletePlan = useCallback(
		async (planId: number) => {
			setIsMutating(true);
			try {
				await adminBillingApiService.deletePlan(planId);
				await refresh();
				toast.success("Plan deleted");
			} catch (error) {
				console.error("Failed to delete plan:", error);
				toast.error(toastMessage("delete plan", error));
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	// ---- Feature flags ----

	const createFeatureFlag = useCallback(
		async (body: FeatureFlagCreateRequest) => {
			setIsMutating(true);
			try {
				await adminBillingApiService.createFeatureFlag(body);
				await refresh();
				toast.success("Feature flag created");
			} catch (error) {
				console.error("Failed to create feature flag:", error);
				toast.error(toastMessage("create feature flag", error));
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	const updateFeatureFlag = useCallback(
		async (flagId: number, body: FeatureFlagUpdateRequest) => {
			setIsMutating(true);
			try {
				await adminBillingApiService.updateFeatureFlag(flagId, body);
				await refresh();
				toast.success("Feature flag updated");
			} catch (error) {
				console.error("Failed to update feature flag:", error);
				toast.error(toastMessage("update feature flag", error));
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	const deleteFeatureFlag = useCallback(
		async (flagId: number) => {
			setIsMutating(true);
			try {
				await adminBillingApiService.deleteFeatureFlag(flagId);
				await refresh();
				toast.success("Feature flag deleted");
			} catch (error) {
				console.error("Failed to delete feature flag:", error);
				toast.error(toastMessage("delete feature flag", error));
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	return {
		plans,
		featureFlags,
		subscriptions,
		isLoading,
		isMutating,
		refresh,
		createPlan,
		updatePlan,
		deletePlan,
		createFeatureFlag,
		updateFeatureFlag,
		deleteFeatureFlag,
	};
}
