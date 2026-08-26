import { z } from "zod";

/**
 * Admin connector OAuth app credentials vault
 *
 * Mirrors `backend/app/schemas/admin_connector_credentials_schemas.py`
 * field-for-field. Keep the two in sync: `base-api.service` only logs a zod
 * mismatch (it returns the raw payload rather than throwing), so a drifted
 * schema here fails at render time instead of at the network boundary.
 */

export const adminConnectorCredentialRead = z.object({
	connector_key: z.string(),
	display_name: z.string(),
	description: z.string(),
	has_client_id: z.boolean(),
	has_client_secret: z.boolean(),
	/**
	 * Whether the backend's `Config` class carries a non-empty env-derived
	 * value for this field. Describes the environment, not the override row,
	 * so it stays true for a connector configured only through `.env` -- which
	 * is what lets the UI tell "cleared / never configured" apart from "no
	 * admin override, but a working environment default is in effect".
	 */
	has_default_client_id: z.boolean(),
	has_default_client_secret: z.boolean(),
	is_enabled: z.boolean(),
	/** False when no override row exists, i.e. the connector is using its Config default. */
	has_override: z.boolean(),
	updated_by_id: z.string().nullable(),
	updated_at: z.string().nullable(),
});

export type AdminConnectorCredentialRead = z.infer<typeof adminConnectorCredentialRead>;

/**
 * List connectors: `GET /admin/connector-credentials` returns an object
 * wrapper, not a bare array, and always has exactly 13 rows (one per
 * registry entry) regardless of DB state.
 */
export const adminConnectorCredentialsListResponse = z.object({
	connectors: z.array(adminConnectorCredentialRead),
});

export type AdminConnectorCredentialsListResponse = z.infer<
	typeof adminConnectorCredentialsListResponse
>;

/**
 * Partial update payload. All three fields are optional and independently
 * omittable -- omitted means "leave unchanged", present-and-null means
 * "clear this stored credential". Zod's `.optional()` + the service layer
 * building the object conditionally (never assigning an explicit `undefined`
 * vs. never setting the key at all matters here -- see the service file)
 * is what keeps an omitted field genuinely absent from the JSON body.
 */
export const updateConnectorCredentialRequest = z.object({
	client_id: z.string().nullable().optional(),
	client_secret: z.string().nullable().optional(),
	is_enabled: z.boolean().nullable().optional(),
});

export type UpdateConnectorCredentialRequest = z.infer<typeof updateConnectorCredentialRequest>;

/** PUT returns the updated row. */
export const updateConnectorCredentialResponse = adminConnectorCredentialRead;

export type UpdateConnectorCredentialResponse = z.infer<typeof updateConnectorCredentialResponse>;

/**
 * Delete (revert to default) connector credential. Returns the reverted row
 * (now showing `has_override: false`), not a success envelope.
 */
export const deleteConnectorCredentialResponse = adminConnectorCredentialRead;

export type DeleteConnectorCredentialResponse = z.infer<typeof deleteConnectorCredentialResponse>;

/**
 * Reveal connector credential. Returns both decrypted fields in one call --
 * there is no per-field reveal endpoint.
 */
export const revealConnectorCredentialResponse = z.object({
	connector_key: z.string(),
	client_id: z.string().nullable(),
	client_secret: z.string().nullable(),
});

export type RevealConnectorCredentialResponse = z.infer<typeof revealConnectorCredentialResponse>;
