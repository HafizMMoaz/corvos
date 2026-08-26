"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type {
	AdminLlmModelCreateRequest,
	AdminLlmModelRead,
	AdminLlmModelUpdateRequest,
} from "@/contracts/types/admin-llm.types";
import { adminLlmApiService } from "@/lib/apis/admin-llm.service";
import { AppError } from "@/lib/error";

export function useAdminLlmModels() {
	const [models, setModels] = useState<AdminLlmModelRead[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [isMutating, setIsMutating] = useState(false);

	const refresh = useCallback(async () => {
		setIsLoading(true);
		try {
			const data = await adminLlmApiService.getModels();
			setModels(data);
		} catch (error) {
			console.error("Failed to load LLM models:", error);
			toast.error("Failed to load LLM models");
		} finally {
			setIsLoading(false);
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	const createModel = useCallback(
		async (body: AdminLlmModelCreateRequest) => {
			setIsMutating(true);
			try {
				await adminLlmApiService.createModel(body);
				await refresh();
				toast.success("Model created");
			} catch (error) {
				console.error("Failed to create LLM model:", error);
				toast.error(error instanceof AppError ? error.message : "Failed to create model");
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	const updateModel = useCallback(
		async (id: number, body: AdminLlmModelUpdateRequest) => {
			setIsMutating(true);
			try {
				await adminLlmApiService.updateModel(id, body);
				await refresh();
				toast.success("Model updated");
			} catch (error) {
				console.error("Failed to update LLM model:", error);
				toast.error(error instanceof AppError ? error.message : "Failed to update model");
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	const deleteModel = useCallback(
		async (id: number) => {
			setIsMutating(true);
			try {
				await adminLlmApiService.deleteModel(id);
				await refresh();
				toast.success("Model deleted");
			} catch (error) {
				console.error("Failed to delete LLM model:", error);
				toast.error(error instanceof AppError ? error.message : "Failed to delete model");
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	/** Manually re-applies the DB catalog into the live config; returns the applied count. */
	const reloadCatalog = useCallback(async () => {
		setIsMutating(true);
		try {
			const data = await adminLlmApiService.reloadCatalog();
			toast.success(
				`Catalog reloaded (${data.applied_count} model${data.applied_count === 1 ? "" : "s"} applied)`
			);
			return data.applied_count;
		} catch (error) {
			console.error("Failed to reload LLM catalog:", error);
			toast.error(error instanceof AppError ? error.message : "Failed to reload catalog");
			throw error;
		} finally {
			setIsMutating(false);
		}
	}, []);

	return {
		models,
		isLoading,
		isMutating,
		refresh,
		createModel,
		updateModel,
		deleteModel,
		reloadCatalog,
	};
}
