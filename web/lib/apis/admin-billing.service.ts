import {
	adminBillingSuccessResponse,
	adminSubscriptionRead,
	adminUserListResponse,
	type FeatureFlagCreateRequest,
	type FeatureFlagUpdateRequest,
	featureFlagRead,
	type PlanCreateRequest,
	type PlanFeatureValueSetRequest,
	type PlanModelEntitlementCreateRequest,
	type PlanUpdateRequest,
	planFeatureValueRead,
	planModelEntitlementListResponse,
	planModelEntitlementRead,
	planRead,
	type UserFeatureOverrideSetRequest,
	type UserPlanAssignmentUpdateRequest,
	userEntitlementsRead,
	userFeatureOverrideRead,
	userPlanRead,
} from "@/contracts/types/admin-billing.types";
import { baseApiService } from "./base-api.service";

/**
 * Thin REST client for the admin plans/feature-flags/entitlements routes,
 * plus the subscriptions and users listings backing the admin Billing & Users
 * pages.
 *
 * Kept as the single place that talks to `/api/v1/admin/plans`,
 * `/api/v1/admin/feature-flags`, `/api/v1/admin/subscriptions`,
 * `/api/v1/admin/users*`, and the per-user billing actions. Request and
 * response shapes are defined in admin-billing.types.ts, which mirrors
 * `backend/app/schemas/admin_billing_schemas.py`.
 */
class AdminBillingApiService {
	// ---- Plans ----

	getPlans = async () => {
		return baseApiService.get(`/api/v1/admin/plans`, planRead.array());
	};

	createPlan = async (body: PlanCreateRequest) => {
		return baseApiService.post(`/api/v1/admin/plans`, planRead, { body });
	};

	updatePlan = async (planId: number, body: PlanUpdateRequest) => {
		return baseApiService.put(
			`/api/v1/admin/plans/${encodeURIComponent(String(planId))}`,
			planRead,
			{ body }
		);
	};

	/** Hard delete. Members are un-assigned (User.plan_id is ON DELETE SET NULL). */
	deletePlan = async (planId: number) => {
		return baseApiService.delete(
			`/api/v1/admin/plans/${encodeURIComponent(String(planId))}`,
			adminBillingSuccessResponse
		);
	};

	// ---- Plan model entitlements ----

	/**
	 * The plan's allowlist of model `config_id`s. An empty list means
	 * unrestricted access, not "none".
	 */
	getPlanModelEntitlements = async (planId: number) => {
		return baseApiService.get(
			`/api/v1/admin/plans/${encodeURIComponent(String(planId))}/model-entitlements`,
			planModelEntitlementListResponse
		);
	};

	addPlanModelEntitlement = async (planId: number, body: PlanModelEntitlementCreateRequest) => {
		return baseApiService.post(
			`/api/v1/admin/plans/${encodeURIComponent(String(planId))}/model-entitlements`,
			planModelEntitlementRead,
			{ body }
		);
	};

	removePlanModelEntitlement = async (planId: number, configId: number) => {
		return baseApiService.delete(
			`/api/v1/admin/plans/${encodeURIComponent(String(planId))}/model-entitlements/${encodeURIComponent(String(configId))}`,
			adminBillingSuccessResponse
		);
	};

	// ---- Plan feature values ----

	getPlanFeatureValues = async (planId: number) => {
		return baseApiService.get(
			`/api/v1/admin/plans/${encodeURIComponent(String(planId))}/feature-values`,
			planFeatureValueRead.array()
		);
	};

	setPlanFeatureValue = async (
		planId: number,
		featureFlagId: number,
		body: PlanFeatureValueSetRequest
	) => {
		return baseApiService.put(
			`/api/v1/admin/plans/${encodeURIComponent(String(planId))}/feature-values/${encodeURIComponent(String(featureFlagId))}`,
			planFeatureValueRead,
			{ body }
		);
	};

	/** Removes the configured value, reverting the flag to its disabled default. */
	deletePlanFeatureValue = async (planId: number, featureFlagId: number) => {
		return baseApiService.delete(
			`/api/v1/admin/plans/${encodeURIComponent(String(planId))}/feature-values/${encodeURIComponent(String(featureFlagId))}`,
			adminBillingSuccessResponse
		);
	};

	// ---- Feature flags ----

	getFeatureFlags = async () => {
		return baseApiService.get(`/api/v1/admin/feature-flags`, featureFlagRead.array());
	};

	createFeatureFlag = async (body: FeatureFlagCreateRequest) => {
		return baseApiService.post(`/api/v1/admin/feature-flags`, featureFlagRead, { body });
	};

	updateFeatureFlag = async (flagId: number, body: FeatureFlagUpdateRequest) => {
		return baseApiService.put(
			`/api/v1/admin/feature-flags/${encodeURIComponent(String(flagId))}`,
			featureFlagRead,
			{ body }
		);
	};

	deleteFeatureFlag = async (flagId: number) => {
		return baseApiService.delete(
			`/api/v1/admin/feature-flags/${encodeURIComponent(String(flagId))}`,
			adminBillingSuccessResponse
		);
	};

	// ---- Subscriptions ----

	getSubscriptions = async () => {
		return baseApiService.get(`/api/v1/admin/subscriptions`, adminSubscriptionRead.array());
	};

	// ---- Users list ----

	getUsers = async (params?: {
		search?: string;
		planId?: number;
		limit?: number;
		offset?: number;
	}) => {
		const query = new URLSearchParams();
		if (params?.search) query.set("search", params.search);
		if (params?.planId != null) query.set("plan_id", String(params.planId));
		if (params?.limit != null) query.set("limit", String(params.limit));
		if (params?.offset != null) query.set("offset", String(params.offset));
		const qs = query.toString();
		return baseApiService.get(`/api/v1/admin/users${qs ? `?${qs}` : ""}`, adminUserListResponse);
	};

	// ---- Per-user billing actions ----

	setUserPlan = async (userId: string, body: UserPlanAssignmentUpdateRequest) => {
		return baseApiService.put(
			`/api/v1/admin/users/${encodeURIComponent(userId)}/plan`,
			userPlanRead,
			{
				body,
			}
		);
	};

	getUserEntitlements = async (userId: string) => {
		return baseApiService.get(
			`/api/v1/admin/users/${encodeURIComponent(userId)}/entitlements`,
			userEntitlementsRead
		);
	};

	getUserFeatureOverrides = async (userId: string) => {
		return baseApiService.get(
			`/api/v1/admin/users/${encodeURIComponent(userId)}/feature-overrides`,
			userFeatureOverrideRead.array()
		);
	};

	setUserFeatureOverride = async (
		userId: string,
		featureFlagId: number,
		body: UserFeatureOverrideSetRequest
	) => {
		return baseApiService.put(
			`/api/v1/admin/users/${encodeURIComponent(userId)}/feature-overrides/${encodeURIComponent(String(featureFlagId))}`,
			userFeatureOverrideRead,
			{ body }
		);
	};

	deleteUserFeatureOverride = async (userId: string, featureFlagId: number) => {
		return baseApiService.delete(
			`/api/v1/admin/users/${encodeURIComponent(userId)}/feature-overrides/${encodeURIComponent(String(featureFlagId))}`,
			adminBillingSuccessResponse
		);
	};
}

export const adminBillingApiService = new AdminBillingApiService();
