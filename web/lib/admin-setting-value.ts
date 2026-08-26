import type {
	AdminSettingValue,
	AdminSettingValueType,
} from "@/contracts/types/admin-settings.types";

/**
 * Value (de)serialization for the admin settings vault.
 *
 * The vault sends and expects *typed* JSON: `PUT /admin/settings/{key}`
 * validates a "bool" setting against a real JSON boolean and an "int" setting
 * against a real JSON integer (see `_validate_input` in
 * `backend/app/services/settings_vault_service.py`) and 400s on anything else,
 * including the string form of the right value. Text inputs necessarily hold
 * strings, so every draft has to be converted back before it goes on the wire.
 */

/**
 * Render a value as text, for display in a row or as the initial draft in the
 * edit dialog. Booleans and numbers are stringified explicitly: React renders
 * nothing at all for a bare `false`, which would otherwise show an empty box
 * for every disabled boolean setting.
 *
 * Returns "" for null; callers decide what placeholder a null value deserves,
 * since null means different things in different spots ("no value set" vs.
 * "not revealed yet").
 */
export function formatSettingValue(value: AdminSettingValue): string {
	if (value === null) return "";
	if (typeof value === "string") return value;
	if (typeof value === "number" || typeof value === "boolean") return String(value);
	return JSON.stringify(value);
}

export type ParsedSettingDraft =
	| { ok: true; value: AdminSettingValue }
	| { ok: false; error: string };

/**
 * Convert a text draft into the JSON type `valueType` demands, or explain why
 * it can't be. Mirrors the server's validation so a bad value is caught in the
 * dialog rather than as a 400 toast.
 */
export function parseSettingDraft(
	valueType: AdminSettingValueType,
	raw: string
): ParsedSettingDraft {
	const trimmed = raw.trim();

	switch (valueType) {
		case "bool":
			// The dialog edits booleans with a Switch and submits the boolean
			// directly; this branch only covers a value arriving as text.
			return { ok: true, value: trimmed.toLowerCase() === "true" };

		case "int": {
			if (!/^-?\d+$/.test(trimmed)) {
				return { ok: false, error: "Enter a whole number (no decimal point)." };
			}
			const parsed = Number(trimmed);
			if (!Number.isSafeInteger(parsed)) {
				return { ok: false, error: "That number is too large to represent exactly." };
			}
			return { ok: true, value: parsed };
		}

		case "float": {
			const parsed = Number(trimmed);
			if (trimmed === "" || !Number.isFinite(parsed)) {
				return { ok: false, error: "Enter a number." };
			}
			return { ok: true, value: parsed };
		}

		case "json": {
			try {
				return { ok: true, value: JSON.parse(trimmed) as AdminSettingValue };
			} catch {
				return { ok: false, error: "Enter valid JSON." };
			}
		}

		default:
			if (trimmed === "") {
				return { ok: false, error: "Enter a value." };
			}
			return { ok: true, value: trimmed };
	}
}
