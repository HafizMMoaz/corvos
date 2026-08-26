"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type {
	CreatePlatformRoleRequest,
	PlatformPermissionInfo,
	PlatformRoleRead,
	UpdatePlatformRoleRequest,
} from "@/contracts/types/admin-rbac.types";
import { adminRbacApiService } from "@/lib/apis/admin-rbac-api.service";

export function useAdminRoles() {
	const [roles, setRoles] = useState<PlatformRoleRead[]>([]);
	const [permissions, setPermissions] = useState<PlatformPermissionInfo[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [isMutating, setIsMutating] = useState(false);

	const refresh = useCallback(async () => {
		setIsLoading(true);
		try {
			const [rolesData, permissionsData] = await Promise.all([
				adminRbacApiService.getRoles(),
				adminRbacApiService.getPermissions(),
			]);
			setRoles(rolesData);
			setPermissions(permissionsData.permissions);
		} catch (error) {
			console.error("Failed to load platform roles:", error);
			toast.error("Failed to load roles");
		} finally {
			setIsLoading(false);
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	const createRole = useCallback(
		async (request: CreatePlatformRoleRequest) => {
			setIsMutating(true);
			try {
				const data = await adminRbacApiService.createRole(request);
				await refresh();
				toast.success("Role created");
				return data;
			} catch (error) {
				console.error("Failed to create role:", error);
				toast.error("Failed to create role");
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	const updateRole = useCallback(
		async (roleId: number, data: UpdatePlatformRoleRequest["data"]) => {
			setIsMutating(true);
			try {
				const updated = await adminRbacApiService.updateRole({ role_id: roleId, data });
				await refresh();
				toast.success("Role updated");
				return updated;
			} catch (error) {
				console.error("Failed to update role:", error);
				toast.error("Failed to update role");
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	const deleteRole = useCallback(
		async (roleId: number) => {
			setIsMutating(true);
			try {
				await adminRbacApiService.deleteRole({ role_id: roleId });
				await refresh();
				toast.success("Role deleted");
			} catch (error) {
				console.error("Failed to delete role:", error);
				toast.error("Failed to delete role");
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	return {
		roles,
		permissions,
		isLoading,
		isMutating,
		refresh,
		createRole,
		updateRole,
		deleteRole,
	};
}
