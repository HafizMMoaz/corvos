"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type { AdminAuditLogRead } from "@/contracts/types/admin-rbac.types";
import { adminRbacApiService } from "@/lib/apis/admin-rbac-api.service";

export const ADMIN_AUDIT_LOG_PAGE_SIZE = 25;

export function useAdminAuditLog() {
	const [entries, setEntries] = useState<AdminAuditLogRead[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(0);
	const [isLoading, setIsLoading] = useState(true);

	const refresh = useCallback(async () => {
		setIsLoading(true);
		try {
			const data = await adminRbacApiService.getAuditLog({
				limit: ADMIN_AUDIT_LOG_PAGE_SIZE,
				offset: page * ADMIN_AUDIT_LOG_PAGE_SIZE,
			});
			setEntries(data.entries);
			setTotal(data.total);
		} catch (error) {
			console.error("Failed to load audit log:", error);
			toast.error("Failed to load audit log");
		} finally {
			setIsLoading(false);
		}
	}, [page]);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	const pageCount = Math.max(1, Math.ceil(total / ADMIN_AUDIT_LOG_PAGE_SIZE));

	return {
		entries,
		total,
		page,
		setPage,
		pageCount,
		pageSize: ADMIN_AUDIT_LOG_PAGE_SIZE,
		isLoading,
		refresh,
	};
}
