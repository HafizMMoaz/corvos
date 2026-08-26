import { z } from "zod";

/**
 * Admin LLM provider/model catalog + free-model quota
 *
 * Mirrors `backend/app/schemas/admin_llm_schemas.py` field-for-field. Keep the
 * two in sync: `base-api.service` only logs a zod mismatch (it returns the raw
 * payload rather than throwing), so a drifted schema here fails at render time
 * instead of at the network boundary.
 */

// ============ LLM Provider ============

/**
 * One provider connection's current state. `has_api_key` reports whether a
 * key is stored without ever returning ciphertext or plaintext -- there is no
 * partial reveal, only "key set" / "key not set" plus
 * `POST /admin/llm-providers/{id}/reveal` for the real value.
 */
export const adminLlmProviderRead = z.object({
	id: z.number(),
	provider_key: z.string(),
	display_name: z.string(),
	transport: z.string(),
	litellm_prefix: z.string().nullable(),
	default_base_url: z.string().nullable(),
	base_url_required: z.boolean(),
	auth_style: z.string(),
	has_api_key: z.boolean(),
	api_base_override: z.string().nullable(),
	is_enabled: z.boolean(),
	notes: z.string().nullable(),
	created_by_id: z.string().nullable(),
	updated_by_id: z.string().nullable(),
	created_at: z.string(),
	updated_at: z.string(),
});

export type AdminLlmProviderRead = z.infer<typeof adminLlmProviderRead>;

/**
 * Request body for `POST /admin/llm-providers`. `api_key`, if given, is
 * plaintext here and encrypted before storage -- never stored or logged as
 * given. No `is_enabled` on create: rows are always created enabled.
 */
export const adminLlmProviderCreateRequest = z.object({
	provider_key: z.string(),
	display_name: z.string(),
	transport: z.string(),
	litellm_prefix: z.string().nullable().optional(),
	default_base_url: z.string().nullable().optional(),
	base_url_required: z.boolean().optional(),
	auth_style: z.string(),
	api_key: z.string().nullable().optional(),
	api_base_override: z.string().nullable().optional(),
	notes: z.string().nullable().optional(),
});

export type AdminLlmProviderCreateRequest = z.infer<typeof adminLlmProviderCreateRequest>;

/**
 * Request body for `PUT /admin/llm-providers/{id}` (partial update). Only
 * fields present in the request are changed. Same encrypt-on-write rule as
 * create for `api_key`.
 */
export const adminLlmProviderUpdateRequest = z.object({
	provider_key: z.string().optional(),
	display_name: z.string().optional(),
	transport: z.string().optional(),
	litellm_prefix: z.string().nullable().optional(),
	default_base_url: z.string().nullable().optional(),
	base_url_required: z.boolean().optional(),
	auth_style: z.string().optional(),
	api_key: z.string().nullable().optional(),
	api_base_override: z.string().nullable().optional(),
	is_enabled: z.boolean().optional(),
	notes: z.string().nullable().optional(),
});

export type AdminLlmProviderUpdateRequest = z.infer<typeof adminLlmProviderUpdateRequest>;

/**
 * Response for `POST /admin/llm-providers/{id}/reveal`: the one place a
 * provider's plaintext API key is ever returned over the wire.
 */
export const adminLlmProviderRevealResponse = z.object({
	id: z.number(),
	api_key: z.string().nullable(),
});

export type AdminLlmProviderRevealResponse = z.infer<typeof adminLlmProviderRevealResponse>;

// ============ LLM Model ============

/** One admin-managed model's current state. */
export const adminLlmModelRead = z.object({
	id: z.number(),
	provider_id: z.number(),
	name: z.string(),
	model_name: z.string(),
	billing_tier: z.string(),
	anonymous_enabled: z.boolean(),
	seo_enabled: z.boolean(),
	seo_slug: z.string().nullable(),
	seo_title: z.string().nullable(),
	seo_description: z.string().nullable(),
	quota_reserve_tokens: z.number().nullable(),
	supports_image_input: z.boolean(),
	supports_tools: z.boolean(),
	max_input_tokens: z.number().nullable(),
	api_base_override: z.string().nullable(),
	api_version: z.string().nullable(),
	rpm: z.number().nullable(),
	tpm: z.number().nullable(),
	/** Arbitrary JSON object passed through to litellm, or null. */
	litellm_params: z.record(z.string(), z.unknown()).nullable(),
	system_instructions: z.string().nullable(),
	use_default_system_instructions: z.boolean(),
	citations_enabled: z.boolean(),
	is_planner: z.boolean(),
	router_pool_eligible: z.boolean(),
	is_enabled: z.boolean(),
	created_by_id: z.string().nullable(),
	updated_by_id: z.string().nullable(),
	created_at: z.string(),
	updated_at: z.string(),
});

export type AdminLlmModelRead = z.infer<typeof adminLlmModelRead>;

/** Request body for `POST /admin/llm-models`. */
export const adminLlmModelCreateRequest = z.object({
	provider_id: z.number(),
	name: z.string(),
	model_name: z.string(),
	billing_tier: z.string().optional(),
	anonymous_enabled: z.boolean().optional(),
	seo_enabled: z.boolean().optional(),
	seo_slug: z.string().nullable().optional(),
	seo_title: z.string().nullable().optional(),
	seo_description: z.string().nullable().optional(),
	quota_reserve_tokens: z.number().nullable().optional(),
	supports_image_input: z.boolean().optional(),
	supports_tools: z.boolean().optional(),
	max_input_tokens: z.number().nullable().optional(),
	api_base_override: z.string().nullable().optional(),
	api_version: z.string().nullable().optional(),
	rpm: z.number().nullable().optional(),
	tpm: z.number().nullable().optional(),
	litellm_params: z.record(z.string(), z.unknown()).nullable().optional(),
	system_instructions: z.string().nullable().optional(),
	use_default_system_instructions: z.boolean().optional(),
	citations_enabled: z.boolean().optional(),
	is_planner: z.boolean().optional(),
	router_pool_eligible: z.boolean().optional(),
	is_enabled: z.boolean().optional(),
});

export type AdminLlmModelCreateRequest = z.infer<typeof adminLlmModelCreateRequest>;

/**
 * Request body for `PUT /admin/llm-models/{id}` (partial update). Only fields
 * present in the request are changed.
 */
export const adminLlmModelUpdateRequest = z.object({
	provider_id: z.number().optional(),
	name: z.string().optional(),
	model_name: z.string().optional(),
	billing_tier: z.string().optional(),
	anonymous_enabled: z.boolean().optional(),
	seo_enabled: z.boolean().optional(),
	seo_slug: z.string().nullable().optional(),
	seo_title: z.string().nullable().optional(),
	seo_description: z.string().nullable().optional(),
	quota_reserve_tokens: z.number().nullable().optional(),
	supports_image_input: z.boolean().optional(),
	supports_tools: z.boolean().optional(),
	max_input_tokens: z.number().nullable().optional(),
	api_base_override: z.string().nullable().optional(),
	api_version: z.string().nullable().optional(),
	rpm: z.number().nullable().optional(),
	tpm: z.number().nullable().optional(),
	litellm_params: z.record(z.string(), z.unknown()).nullable().optional(),
	system_instructions: z.string().nullable().optional(),
	use_default_system_instructions: z.boolean().optional(),
	citations_enabled: z.boolean().optional(),
	is_planner: z.boolean().optional(),
	router_pool_eligible: z.boolean().optional(),
	is_enabled: z.boolean().optional(),
});

export type AdminLlmModelUpdateRequest = z.infer<typeof adminLlmModelUpdateRequest>;

// ============ Live model discovery ============

/**
 * One model discovered live from a provider's own API (or, for
 * `static`-discovery providers, LiteLLM's bundled cost map), returned by
 * `POST /admin/llm-providers/{id}/discover-models`. Trimmed from the
 * workspace BYOK flow's model-preview shape: no `source`/`enabled`/
 * `metadata` -- those are workspace-connection-specific concepts that don't
 * apply to this admin-catalog use case.
 */
export const adminLlmDiscoveredModelRead = z.object({
	model_id: z.string(),
	display_name: z.string().nullable(),
	supports_chat: z.boolean().nullable(),
	supports_image_input: z.boolean().nullable(),
	supports_tools: z.boolean().nullable(),
	supports_image_generation: z.boolean().nullable(),
	max_input_tokens: z.number().nullable(),
});

export type AdminLlmDiscoveredModelRead = z.infer<typeof adminLlmDiscoveredModelRead>;

// ============ Reload ============

/** Response for `POST /admin/llm-models/reload`. */
export const adminLlmReloadResponse = z.object({
	applied_count: z.number(),
});

export type AdminLlmReloadResponse = z.infer<typeof adminLlmReloadResponse>;

// ============ Free-model quota ============

/**
 * Response for `GET /admin/llm-quota` and `POST /admin/llm-quota/reset`: the
 * platform-wide free-tier token quota for the current period, plus the
 * configured cap it's enforced against.
 */
export const adminFreeQuotaGlobalRead = z.object({
	period_start: z.string(),
	tokens_reserved: z.number(),
	tokens_used: z.number(),
	cap_tokens: z.number(),
	updated_at: z.string(),
});

export type AdminFreeQuotaGlobalRead = z.infer<typeof adminFreeQuotaGlobalRead>;

/**
 * Response for `GET /admin/llm-quota/users/{user_id}` and
 * `POST /admin/llm-quota/users/{user_id}/reset`: one user's free-tier token
 * quota for the current period, plus the configured cap. All fields except
 * `user_id`/`cap_tokens` are null when the user has never reserved free-tier
 * quota yet -- render that as an explicit "no usage yet" state, not zeros.
 */
export const adminFreeQuotaUserRead = z.object({
	user_id: z.string(),
	period_start: z.string().nullable(),
	tokens_reserved: z.number().nullable(),
	tokens_used: z.number().nullable(),
	cap_tokens: z.number(),
	updated_at: z.string().nullable(),
});

export type AdminFreeQuotaUserRead = z.infer<typeof adminFreeQuotaUserRead>;
