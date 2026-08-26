"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type { AdminSettingRead, AdminSettingValue } from "@/contracts/types/admin-settings.types";
import { adminSettingsApiService } from "@/lib/apis/admin-settings.service";
import { AppError, AuthorizationError } from "@/lib/error";

export function useAdminSettings() {
	const [settings, setSettings] = useState<AdminSettingRead[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [isMutating, setIsMutating] = useState(false);

	const refresh = useCallback(async () => {
		setIsLoading(true);
		try {
			const data = await adminSettingsApiService.getSettings();
			// GET /admin/settings returns { settings, categories }, not a bare
			// array. base-api only logs a schema mismatch (it returns the raw
			// payload rather than throwing), so guard the shape here instead of
			// letting a drifted contract reach the renderer as a non-array.
			if (!Array.isArray(data.settings)) {
				throw new Error("Unexpected /admin/settings response shape");
			}
			setSettings(data.settings);
		} catch (error) {
			console.error("Failed to load admin settings:", error);
			toast.error("Failed to load settings");
		} finally {
			setIsLoading(false);
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	const updateSetting = useCallback(
		async (key: string, value: AdminSettingValue) => {
			setIsMutating(true);
			try {
				await adminSettingsApiService.updateSetting(key, value);
				await refresh();
				toast.success("Setting updated");
			} catch (error) {
				console.error("Failed to update setting:", error);
				// Server validates the value against a registry - surface the
				// actual message (e.g. "must be a valid URL") rather than a
				// generic one, per the API contract.
				toast.error(error instanceof AppError ? error.message : "Failed to update setting");
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	const revertSetting = useCallback(
		async (key: string) => {
			setIsMutating(true);
			try {
				await adminSettingsApiService.deleteSetting(key);
				await refresh();
				toast.success("Setting reverted to default");
			} catch (error) {
				console.error("Failed to revert setting:", error);
				toast.error("Failed to revert setting");
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	/** Calls the reveal endpoint and returns the real value; does not touch list state. */
	const revealSetting = useCallback(async (key: string) => {
		try {
			const data = await adminSettingsApiService.revealSetting(key);
			return data.value;
		} catch (error) {
			console.error("Failed to reveal setting:", error);
			if (error instanceof AuthorizationError) {
				toast.error("You don't have permission to reveal this value");
			} else {
				toast.error("Failed to reveal value");
			}
			throw error;
		}
	}, []);

	return {
		settings,
		isLoading,
		isMutating,
		refresh,
		updateSetting,
		revertSetting,
		revealSetting,
	};
}
