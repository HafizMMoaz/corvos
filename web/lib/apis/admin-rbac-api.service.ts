import {
	adminAuditLogListResponse,
	adminMeResponse,
	type CreatePlatformRoleRequest,
	type CreateRoleAssignmentRequest,
	createPlatformRoleRequest,
	createPlatformRoleResponse,
	createRoleAssignmentRequest,
	createRoleAssignmentResponse,
	type DeletePlatformRoleRequest,
	type DeleteRoleAssignmentRequest,
	deletePlatformRoleRequest,
	deletePlatformRoleResponse,
	deleteRoleAssignmentRequest,
	deleteRoleAssignmentResponse,
	type GetAuditLogRequest,
	getAuditLogRequest,
	getPlatformRolesResponse,
	getRoleAssignmentsResponse,
	platformPermissionsListResponse,
	type UpdatePlatformRoleRequest,
	updatePlatformRoleRequest,
	updatePlatformRoleResponse,
} from "@/contracts/types/admin-rbac.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class AdminRbacApiService {
	getMe = async () => {
		return baseApiService.get(`/api/v1/admin/me`, adminMeResponse);
	};

	getPermissions = async () => {
		return baseApiService.get(`/api/v1/admin/permissions`, platformPermissionsListResponse);
	};

	getRoles = async () => {
		return baseApiService.get(`/api/v1/admin/roles`, getPlatformRolesResponse);
	};

	createRole = async (request: CreatePlatformRoleRequest) => {
		const parsedRequest = createPlatformRoleRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/admin/roles`, createPlatformRoleResponse, {
			body: parsedRequest.data,
		});
	};

	updateRole = async (request: UpdatePlatformRoleRequest) => {
		const parsedRequest = updatePlatformRoleRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.patch(
			`/api/v1/admin/roles/${parsedRequest.data.role_id}`,
			updatePlatformRoleResponse,
			{
				body: parsedRequest.data.data,
			}
		);
	};

	deleteRole = async (request: DeletePlatformRoleRequest) => {
		const parsedRequest = deletePlatformRoleRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(
			`/api/v1/admin/roles/${parsedRequest.data.role_id}`,
			deletePlatformRoleResponse
		);
	};

	getRoleAssignments = async () => {
		return baseApiService.get(`/api/v1/admin/role-assignments`, getRoleAssignmentsResponse);
	};

	createRoleAssignment = async (request: CreateRoleAssignmentRequest) => {
		const parsedRequest = createRoleAssignmentRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/admin/role-assignments`, createRoleAssignmentResponse, {
			body: parsedRequest.data,
		});
	};

	deleteRoleAssignment = async (request: DeleteRoleAssignmentRequest) => {
		const parsedRequest = deleteRoleAssignmentRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(
			`/api/v1/admin/role-assignments/${parsedRequest.data.assignment_id}`,
			deleteRoleAssignmentResponse
		);
	};

	getAuditLog = async (request: GetAuditLogRequest) => {
		const parsedRequest = getAuditLogRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const queryParams = new URLSearchParams();
		const { limit, offset, action, target_type } = parsedRequest.data;
		if (limit !== undefined) queryParams.set("limit", String(limit));
		if (offset !== undefined) queryParams.set("offset", String(offset));
		if (action) queryParams.set("action", action);
		if (target_type) queryParams.set("target_type", target_type);

		const queryString = queryParams.toString();

		return baseApiService.get(
			`/api/v1/admin/audit-log${queryString ? `?${queryString}` : ""}`,
			adminAuditLogListResponse
		);
	};
}

export const adminRbacApiService = new AdminRbacApiService();
