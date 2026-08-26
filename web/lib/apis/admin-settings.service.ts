import {
	type AdminSettingValue,
	adminSettingsListResponse,
	deleteSettingResponse,
	revealSettingResponse,
	updateSettingRequest,
	updateSettingResponse,
} from "@/contracts/types/admin-settings.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

/**
 * Thin REST client for the Phase B admin settings / secrets vault routes.
 *
 * Kept as the single place that talks to `/api/v1/admin/settings/*`. Request
 * and response shapes are defined in admin-settings.types.ts, which mirrors
 * `backend/app/schemas/admin_settings_schemas.py`.
 */
class AdminSettingsApiService {
	getSettings = async () => {
		return baseApiService.get(`/api/v1/admin/settings`, adminSettingsListResponse);
	};

	revealSetting = async (key: string) => {
		return baseApiService.post(
			`/api/v1/admin/settings/${encodeURIComponent(key)}/reveal`,
			revealSettingResponse
		);
	};

	/**
	 * `value` must already be the JSON type the setting's `value_type`
	 * declares. The server validates it strictly and does not coerce, so
	 * sending "5" for an int setting or "true" for a bool setting is a 400.
	 */
	updateSetting = async (key: string, value: AdminSettingValue) => {
		const parsedRequest = updateSettingRequest.safeParse({ value });

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.put(
			`/api/v1/admin/settings/${encodeURIComponent(key)}`,
			updateSettingResponse,
			{
				body: parsedRequest.data,
			}
		);
	};

	/** Reverts the setting to its default (deletes the DB override row). */
	deleteSetting = async (key: string) => {
		return baseApiService.delete(
			`/api/v1/admin/settings/${encodeURIComponent(key)}`,
			deleteSettingResponse
		);
	};
}

export const adminSettingsApiService = new AdminSettingsApiService();
