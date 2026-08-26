import * as z from "zod";
import type {
	AdminLlmModelCreateRequest,
	AdminLlmModelRead,
	AdminLlmModelUpdateRequest,
} from "@/contracts/types/admin-llm.types";

/**
 * Form schema, defaults, and payload conversion for the 24-field model
 * create/edit form (ModelFormDialog + its per-section field components).
 * Kept separate from the dialog component so the orchestrator file stays
 * focused on layout, not validation/parsing logic.
 *
 * HTML inputs only ever produce strings, so every optional int and the
 * `litellm_params` JSON object are held as form-level strings ("" meaning
 * "unset") and converted to their real JSON types in `buildModelPayload`.
 */

const optionalIntField = z.string().refine((value) => {
	const trimmed = value.trim();
	return trimmed === "" || /^\d+$/.test(trimmed);
}, "Enter a whole number, or leave blank");

const optionalJsonObjectField = z.string().refine((value) => {
	const trimmed = value.trim();
	if (trimmed === "") return true;
	try {
		const parsed = JSON.parse(trimmed);
		return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed);
	} catch {
		return false;
	}
}, "Enter a valid JSON object, or leave blank");

export const modelFormSchema = z.object({
	// Identity
	provider_id: z.string().min(1, "Provider is required"),
	name: z.string().min(1, "Name is required"),
	model_name: z.string().min(1, "Model name is required"),
	billing_tier: z.enum(["free", "premium"]),
	// Visibility
	anonymous_enabled: z.boolean(),
	seo_enabled: z.boolean(),
	seo_slug: z.string(),
	seo_title: z.string(),
	seo_description: z.string(),
	is_enabled: z.boolean(),
	// Capabilities
	supports_image_input: z.boolean(),
	supports_tools: z.boolean(),
	max_input_tokens: optionalIntField,
	// Rate limits & routing
	rpm: optionalIntField,
	tpm: optionalIntField,
	quota_reserve_tokens: optionalIntField,
	router_pool_eligible: z.boolean(),
	is_planner: z.boolean(),
	// Provider overrides
	api_base_override: z.string(),
	api_version: z.string(),
	litellm_params: optionalJsonObjectField,
	// Prompt behavior
	system_instructions: z.string(),
	use_default_system_instructions: z.boolean(),
	citations_enabled: z.boolean(),
});

export type ModelFormValues = z.infer<typeof modelFormSchema>;

export const EMPTY_MODEL_VALUES: ModelFormValues = {
	provider_id: "",
	name: "",
	model_name: "",
	billing_tier: "premium",
	anonymous_enabled: false,
	seo_enabled: false,
	seo_slug: "",
	seo_title: "",
	seo_description: "",
	is_enabled: true,
	supports_image_input: false,
	supports_tools: false,
	max_input_tokens: "",
	rpm: "",
	tpm: "",
	quota_reserve_tokens: "",
	router_pool_eligible: true,
	is_planner: false,
	api_base_override: "",
	api_version: "",
	litellm_params: "",
	system_instructions: "",
	use_default_system_instructions: true,
	citations_enabled: true,
};

function blankToNull(value: string): string | null {
	const trimmed = value.trim();
	return trimmed ? trimmed : null;
}

function parseOptionalInt(value: string): number | null {
	const trimmed = value.trim();
	return trimmed ? Number.parseInt(trimmed, 10) : null;
}

function parseOptionalJsonObject(value: string): Record<string, unknown> | null {
	const trimmed = value.trim();
	return trimmed ? (JSON.parse(trimmed) as Record<string, unknown>) : null;
}

/** Converts an existing model row into form values for the edit dialog. */
export function modelToFormValues(model: AdminLlmModelRead): ModelFormValues {
	return {
		provider_id: String(model.provider_id),
		name: model.name,
		model_name: model.model_name,
		billing_tier: model.billing_tier === "free" ? "free" : "premium",
		anonymous_enabled: model.anonymous_enabled,
		seo_enabled: model.seo_enabled,
		seo_slug: model.seo_slug ?? "",
		seo_title: model.seo_title ?? "",
		seo_description: model.seo_description ?? "",
		is_enabled: model.is_enabled,
		supports_image_input: model.supports_image_input,
		supports_tools: model.supports_tools,
		max_input_tokens: model.max_input_tokens?.toString() ?? "",
		rpm: model.rpm?.toString() ?? "",
		tpm: model.tpm?.toString() ?? "",
		quota_reserve_tokens: model.quota_reserve_tokens?.toString() ?? "",
		router_pool_eligible: model.router_pool_eligible,
		is_planner: model.is_planner,
		api_base_override: model.api_base_override ?? "",
		api_version: model.api_version ?? "",
		litellm_params: model.litellm_params ? JSON.stringify(model.litellm_params, null, 2) : "",
		system_instructions: model.system_instructions ?? "",
		use_default_system_instructions: model.use_default_system_instructions,
		citations_enabled: model.citations_enabled,
	};
}

/** Converts validated form values into the create/update request body. */
export function buildModelPayload(
	values: ModelFormValues
): AdminLlmModelCreateRequest & AdminLlmModelUpdateRequest {
	return {
		provider_id: Number(values.provider_id),
		name: values.name,
		model_name: values.model_name,
		billing_tier: values.billing_tier,
		anonymous_enabled: values.anonymous_enabled,
		seo_enabled: values.seo_enabled,
		seo_slug: blankToNull(values.seo_slug),
		seo_title: blankToNull(values.seo_title),
		seo_description: blankToNull(values.seo_description),
		is_enabled: values.is_enabled,
		supports_image_input: values.supports_image_input,
		supports_tools: values.supports_tools,
		max_input_tokens: parseOptionalInt(values.max_input_tokens),
		rpm: parseOptionalInt(values.rpm),
		tpm: parseOptionalInt(values.tpm),
		quota_reserve_tokens: parseOptionalInt(values.quota_reserve_tokens),
		router_pool_eligible: values.router_pool_eligible,
		is_planner: values.is_planner,
		api_base_override: blankToNull(values.api_base_override),
		api_version: blankToNull(values.api_version),
		litellm_params: parseOptionalJsonObject(values.litellm_params),
		system_instructions: blankToNull(values.system_instructions),
		use_default_system_instructions: values.use_default_system_instructions,
		citations_enabled: values.citations_enabled,
	};
}
