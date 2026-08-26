import { z } from "zod";

/**
 * Admin settings (Settings / Secrets Vault)
 *
 * Mirrors `backend/app/schemas/admin_settings_schemas.py` field-for-field.
 * Keep the two in sync: `base-api.service` only logs a zod mismatch (it
 * returns the raw payload rather than throwing), so a drifted schema here
 * fails at render time instead of at the network boundary.
 */

/**
 * `value_type` tokens, from `SettingDefinition.value_type` in
 * `backend/app/config/settings_registry.py` (`ValueType` literal). Modelled as
 * an enum rather than a bare string so a typo like "boolean"/"number" is a
 * compile error instead of a silently-never-matching branch.
 */
export const adminSettingValueType = z.enum(["string", "int", "float", "bool", "json"]);

export type AdminSettingValueType = z.infer<typeof adminSettingValueType>;

/**
 * A setting's value. The backend types this as `Any` and stores it per
 * `value_type`, so it arrives as a JSON bool / number / string / null (or an
 * arbitrary JSON document for `value_type: "json"`).
 *
 * Note a secret's value is a *masked string* (e.g. "***1234") everywhere
 * except the reveal endpoint, whatever its declared `value_type`.
 */
export const adminSettingValue = z.json();

export type AdminSettingValue = z.infer<typeof adminSettingValue>;

export const adminSettingRead = z.object({
	key: z.string(),
	category: z.string(),
	value_type: adminSettingValueType,
	is_secret: z.boolean(),
	is_disruptive: z.boolean(),
	description: z.string(),
	value: adminSettingValue,
	/** False when no override row exists, i.e. `value` is the Config default. */
	has_override: z.boolean(),
	updated_by_id: z.string().nullable(),
	updated_at: z.string().nullable(),
});

export type AdminSettingRead = z.infer<typeof adminSettingRead>;

/**
 * List settings: `GET /admin/settings` returns an object wrapper, not a bare
 * array. `categories` is the registry's full category list (it is not
 * narrowed by the `?category=` filter).
 */
export const adminSettingsListResponse = z.object({
	settings: z.array(adminSettingRead),
	categories: z.array(z.string()),
});

export type AdminSettingsListResponse = z.infer<typeof adminSettingsListResponse>;

/**
 * Reveal setting
 */
export const revealSettingResponse = z.object({
	key: z.string(),
	value: adminSettingValue,
});

export type RevealSettingResponse = z.infer<typeof revealSettingResponse>;

/**
 * Update setting. `value` must be the JSON type the setting's `value_type`
 * declares (a real JSON bool for "bool", a real JSON int for "int", ...); the
 * server 400s on a type mismatch rather than coercing, so callers must send
 * the typed value, never its string form.
 */
export const updateSettingRequest = z.object({
	value: adminSettingValue,
});

/** PUT returns the updated row, with secrets re-masked. */
export const updateSettingResponse = adminSettingRead;

export type UpdateSettingRequest = z.infer<typeof updateSettingRequest>;
export type UpdateSettingResponse = z.infer<typeof updateSettingResponse>;

/**
 * Delete (revert to default) setting. Returns the reverted row (now showing
 * the Config default with `has_override: false`), not a success envelope.
 */
export const deleteSettingResponse = adminSettingRead;

export type DeleteSettingResponse = z.infer<typeof deleteSettingResponse>;
