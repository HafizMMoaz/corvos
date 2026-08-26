"use client";

import { useCallback, useState } from "react";
import type { AdminLlmDiscoveredModelRead } from "@/contracts/types/admin-llm.types";
import { adminLlmApiService } from "@/lib/apis/admin-llm.service";
import { AppError } from "@/lib/error";

/**
 * Fetches the live model list for one provider (Phase C Track 4: live model
 * discovery for the admin "Add model" dialog).
 *
 * Discovery failing or coming back empty must never block the admin from
 * still typing a model name by hand, so failures land in `error` as text for
 * the form to render inline, not a toast that could read as a blocking
 * error.
 */
export function useAdminLlmDiscoveredModels() {
	const [models, setModels] = useState<AdminLlmDiscoveredModelRead[]>([]);
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const discover = useCallback(async (providerId: number) => {
		setIsLoading(true);
		setError(null);
		try {
			const data = await adminLlmApiService.discoverProviderModels(providerId);
			setModels(data);
		} catch (err) {
			console.error("Failed to discover provider models:", err);
			setModels([]);
			setError(err instanceof AppError ? err.message : "Model discovery failed");
		} finally {
			setIsLoading(false);
		}
	}, []);

	const reset = useCallback(() => {
		setModels([]);
		setError(null);
		setIsLoading(false);
	}, []);

	return { models, isLoading, error, discover, reset };
}
