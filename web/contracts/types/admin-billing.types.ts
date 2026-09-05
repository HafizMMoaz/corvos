import { z } from "zod";

/**
 * Admin plans, feature flags, entitlements, subscriptions, and users
 *
 * Mirrors `backend/app/schemas/admin_billing_schemas.py` field-for-field. Keep
 * the two in sync: `base-api.service` only logs a zod mismatch (it returns the
 * raw payload rather than throwing), so a drifted schema here fails at render
 * time instead of at the network boundary.
 */

// ============ Plan ============

/** One plan's current state. */
export const planRead = z.object({
	id: z.number(),
	plan_key: z.string(),
	name: z.string(),
	description: z.string().nullable(),
	monthly_credit_micros: z.number(),
	paddle_price_id: z.string().nullable(),
	is_active: z.boolean(),
	updated_by_id: z.string().nullable(),
	created_at: z.string(),
	updated_at: z.string(),
});

export type PlanRead = z.infer<typeof planRead>;

/**
 * Request body for `POST /admin/plans`. `paddle_price_id` is not settable on
 * create -- assign it via a later `PUT` once the matching Paddle price exists.
 */
export const planCreateRequest = z.object({
	plan_key: z.string(),
	name: z.string(),
	description: z.string().nullable().optional(),
	monthly_credit_micros: z.number().optional(),
	is_active: z.boolean().optional(),
});

export type PlanCreateRequest = z.infer<typeof planCreateRequest>;

/** Request body for `PUT /admin/plans/{plan_id}` (partial update). */
export const planUpdateRequest = z.object({
	plan_key: z.string().optional(),
	name: z.string().optional(),
	description: z.string().nullable().optional(),
	monthly_credit_micros: z.number().optional(),
	paddle_price_id: z.string().nullable().optional(),
	is_active: z.boolean().optional(),
});

export type PlanUpdateRequest = z.infer<typeof planUpdateRequest>;

// ============ Feature Flag ============

/** One feature flag definition's current state. */
export const featureFlagRead = z.object({
	id: z.number(),
	flag_key: z.string(),
	name: z.string(),
	description: z.string().nullable(),
	updated_by_id: z.string().nullable(),
	created_at: z.string(),
	updated_at: z.string(),
});

export type FeatureFlagRead = z.infer<typeof featureFlagRead>;

/** Request body for `POST /admin/feature-flags`. */
export const featureFlagCreateRequest = z.object({
	flag_key: z.string(),
	name: z.string(),
	description: z.string().nullable().optional(),
});

export type FeatureFlagCreateRequest = z.infer<typeof featureFlagCreateRequest>;

/** Request body for `PUT /admin/feature-flags/{flag_id}` (partial update). */
export const featureFlagUpdateRequest = z.object({
	flag_key: z.string().optional(),
	name: z.string().optional(),
	description: z.string().nullable().optional(),
});

export type FeatureFlagUpdateRequest = z.infer<typeof featureFlagUpdateRequest>;

// ============ Plan model entitlements ============

/** Request body for `POST /admin/plans/{plan_id}/model-entitlements`. */
export const planModelEntitlementCreateRequest = z.object({
	config_id: z.number(),
});

export type PlanModelEntitlementCreateRequest = z.infer<typeof planModelEntitlementCreateRequest>;

/** Response for `POST /admin/plans/{plan_id}/model-entitlements`. */
export const planModelEntitlementRead = z.object({
	plan_id: z.number(),
	config_id: z.number(),
});

export type PlanModelEntitlementRead = z.infer<typeof planModelEntitlementRead>;

/**
 * Response for the entitlements list endpoint -- the plan's allowlist of
 * model `config_id`s. An empty list means unrestricted access, not "none".
 */
export const planModelEntitlementListResponse = z.array(z.number());

// ============ Plan feature values ============

/** Request body for `PUT /admin/plans/{plan_id}/feature-values/{feature_flag_id}`. */
export const planFeatureValueSetRequest = z.object({
	enabled: z.boolean(),
});

export type PlanFeatureValueSetRequest = z.infer<typeof planFeatureValueSetRequest>;

/**
 * One plan's configured value for one feature flag. A `feature_flag_id`
 * absent from the list response is off by default for that plan.
 */
export const planFeatureValueRead = z.object({
	feature_flag_id: z.number(),
	enabled: z.boolean(),
	updated_at: z.string(),
});

export type PlanFeatureValueRead = z.infer<typeof planFeatureValueRead>;

// ============ User plan / entitlements ============

/**
 * Request body for `PUT /admin/users/{user_id}/plan`.
 * `plan_id: null` un-assigns the user from any plan.
 */
export const userPlanAssignmentUpdateRequest = z.object({
	plan_id: z.number().nullable(),
});

export type UserPlanAssignmentUpdateRequest = z.infer<typeof userPlanAssignmentUpdateRequest>;

/** Response for `PUT /admin/users/{user_id}/plan`. */
export const userPlanRead = z.object({
	user_id: z.string(),
	plan_id: z.number().nullable(),
});

export type UserPlanRead = z.infer<typeof userPlanRead>;

/** Response for `GET /admin/users/{user_id}/entitlements`: resolved state. */
export const userEntitlementsRead = z.object({
	user_id: z.string(),
	plan: planRead.nullable(),
	feature_flags: z.record(z.string(), z.boolean()),
	unrestricted_models: z.boolean(),
	allowed_config_ids: z.array(z.number()),
});

export type UserEntitlementsRead = z.infer<typeof userEntitlementsRead>;

/** Request body for `PUT /admin/users/{user_id}/feature-overrides/{feature_flag_id}`. */
export const userFeatureOverrideSetRequest = z.object({
	enabled: z.boolean(),
	expires_at: z.string().nullable().optional(),
});

export type UserFeatureOverrideSetRequest = z.infer<typeof userFeatureOverrideSetRequest>;

/**
 * One user's forced value for one feature flag. Expired-but-not-deleted rows
 * are still listed (with `expires_at` visible) so admins see the full history.
 */
export const userFeatureOverrideRead = z.object({
	id: z.number(),
	user_id: z.string(),
	feature_flag_id: z.number(),
	enabled: z.boolean(),
	expires_at: z.string().nullable(),
	created_by_id: z.string().nullable(),
	created_at: z.string(),
	updated_at: z.string(),
});

export type UserFeatureOverrideRead = z.infer<typeof userFeatureOverrideRead>;

// ============ Admin subscriptions list ============

/**
 * One row of the subscriptions list: a Paddle subscription joined with its
 * user's email and plan's name. Read-only -- subscription state always flows
 * in from Paddle webhooks.
 */
export const adminSubscriptionRead = z.object({
	id: z.number(),
	user_id: z.string(),
	user_email: z.string(),
	plan_id: z.number().nullable(),
	plan_name: z.string().nullable(),
	paddle_subscription_id: z.string(),
	paddle_customer_id: z.string(),
	status: z.string(),
	current_period_end: z.string().nullable(),
	cancel_at_period_end: z.boolean(),
	created_at: z.string(),
	updated_at: z.string(),
});

export type AdminSubscriptionRead = z.infer<typeof adminSubscriptionRead>;

// ============ Admin users list ============

/** One row of the users list. */
export const adminUserListItemRead = z.object({
	id: z.string(),
	email: z.string(),
	display_name: z.string().nullable(),
	is_active: z.boolean(),
	is_superuser: z.boolean(),
	plan_id: z.number().nullable(),
	plan_name: z.string().nullable(),
	credit_micros_balance: z.number(),
	last_login: z.string().nullable(),
});

export type AdminUserListItemRead = z.infer<typeof adminUserListItemRead>;

/** Response for `GET /admin/users` (paginated). */
export const adminUserListResponse = z.object({
	users: z.array(adminUserListItemRead),
	total: z.number(),
	limit: z.number(),
	offset: z.number(),
});

export type AdminUserListResponse = z.infer<typeof adminUserListResponse>;

// ============ Misc ============

/** Shape of `DELETE` endpoints that return `{"success": true}`. */
export const adminBillingSuccessResponse = z.object({
	success: z.boolean(),
});
