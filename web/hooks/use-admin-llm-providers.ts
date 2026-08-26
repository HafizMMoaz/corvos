"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type {
	AdminLlmProviderCreateRequest,
	AdminLlmProviderRead,
	AdminLlmProviderUpdateRequest,
} from "@/contracts/types/admin-llm.types";
import { adminLlmApiService } from "@/lib/apis/admin-llm.service";
import { AppError } from "@/lib/error";

export function useAdminLlmProviders() {
	const [providers, setProviders] = useState<AdminLlmProviderRead[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [isMutating, setIsMutating] = useState(false);

	const refresh = useCallback(async () => {
		setIsLoading(true);
		try {
			const data = await adminLlmApiService.getProviders();
			setProviders(data);
		} catch (error) {
			console.error("Failed to load LLM providers:", error);
			toast.error("Failed to load LLM providers");
		} finally {
			setIsLoading(false);
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	const createProvider = useCallback(
		async (body: AdminLlmProviderCreateRequest) => {
			setIsMutating(true);
			try {
				await adminLlmApiService.createProvider(body);
				await refresh();
				toast.success("Provider created");
			} catch (error) {
				console.error("Failed to create LLM provider:", error);
				toast.error(error instanceof AppError ? error.message : "Failed to create provider");
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	const updateProvider = useCallback(
		async (id: number, body: AdminLlmProviderUpdateRequest) => {
			setIsMutating(true);
			try {
				await adminLlmApiService.updateProvider(id, body);
				await refresh();
				toast.success("Provider updated");
			} catch (error) {
				console.error("Failed to update LLM provider:", error);
				toast.error(error instanceof AppError ? error.message : "Failed to update provider");
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	const deleteProvider = useCallback(
		async (id: number) => {
			setIsMutating(true);
			try {
				await adminLlmApiService.deleteProvider(id);
				await refresh();
				toast.success("Provider deleted");
			} catch (error) {
				console.error("Failed to delete LLM provider:", error);
				toast.error(error instanceof AppError ? error.message : "Failed to delete provider");
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	/** Returns the provider's decrypted API key; does not touch list state. */
	const revealProviderApiKey = useCallback(async (id: number) => {
		try {
			const data = await adminLlmApiService.revealProviderApiKey(id);
			return data.api_key;
		} catch (error) {
			console.error("Failed to reveal LLM provider API key:", error);
			toast.error(error instanceof AppError ? error.message : "Failed to reveal API key");
			throw error;
		}
	}, []);

	return {
		providers,
		isLoading,
		isMutating,
		refresh,
		createProvider,
		updateProvider,
		deleteProvider,
		revealProviderApiKey,
	};
}
