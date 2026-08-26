"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type {
	AdminFreeQuotaGlobalRead,
	AdminFreeQuotaUserRead,
} from "@/contracts/types/admin-llm.types";
import { adminLlmApiService } from "@/lib/apis/admin-llm.service";
import { AppError } from "@/lib/error";

export function useAdminLlmQuota() {
	const [globalQuota, setGlobalQuota] = useState<AdminFreeQuotaGlobalRead | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [isMutating, setIsMutating] = useState(false);

	const refresh = useCallback(async () => {
		setIsLoading(true);
		try {
			const data = await adminLlmApiService.getGlobalQuota();
			setGlobalQuota(data);
		} catch (error) {
			console.error("Failed to load free-model quota:", error);
			toast.error("Failed to load free-model quota");
		} finally {
			setIsLoading(false);
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	/** Zeroes the platform-wide free-tier counter shared by every user. */
	const resetGlobalQuota = useCallback(async () => {
		setIsMutating(true);
		try {
			await adminLlmApiService.resetGlobalQuota();
			await refresh();
			toast.success("Platform-wide quota reset");
		} catch (error) {
			console.error("Failed to reset global free-model quota:", error);
			toast.error(error instanceof AppError ? error.message : "Failed to reset quota");
			throw error;
		} finally {
			setIsMutating(false);
		}
	}, [refresh]);

	/** On-demand per-user lookup - does not touch this hook's own state, just returns the result or throws. */
	const lookupUser = useCallback(async (userId: string): Promise<AdminFreeQuotaUserRead> => {
		try {
			return await adminLlmApiService.getUserQuota(userId);
		} catch (error) {
			console.error("Failed to look up user free-model quota:", error);
			toast.error(error instanceof AppError ? error.message : "Failed to look up user quota");
			throw error;
		}
	}, []);

	const resetUserQuota = useCallback(async (userId: string): Promise<AdminFreeQuotaUserRead> => {
		try {
			const data = await adminLlmApiService.resetUserQuota(userId);
			toast.success("User's quota reset");
			return data;
		} catch (error) {
			console.error("Failed to reset user free-model quota:", error);
			toast.error(error instanceof AppError ? error.message : "Failed to reset user's quota");
			throw error;
		}
	}, []);

	return {
		globalQuota,
		isLoading,
		isMutating,
		refresh,
		resetGlobalQuota,
		lookupUser,
		resetUserQuota,
	};
}
