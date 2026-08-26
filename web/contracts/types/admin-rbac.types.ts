import { z } from "zod";

/**
 * Admin session
 */
export const adminMeResponse = z.object({
	user_id: z.string(),
	email: z.string(),
	permissions: z.array(z.string()),
	roles: z.array(z.string()),
});

export type AdminMeResponse = z.infer<typeof adminMeResponse>;

/**
 * Platform permissions
 */
export const platformPermissionInfo = z.object({
	value: z.string(),
	name: z.string(),
	description: z.string(),
});

export const platformPermissionsListResponse = z.object({
	permissions: z.array(platformPermissionInfo),
});

export type PlatformPermissionInfo = z.infer<typeof platformPermissionInfo>;
export type PlatformPermissionsListResponse = z.infer<typeof platformPermissionsListResponse>;

/**
 * Platform roles
 */
const platformRoleBase = z.object({
	id: z.number(),
	name: z.string().min(1).max(100),
	description: z.string().max(500).nullable(),
	permissions: z.array(z.string()),
	is_system_role: z.boolean(),
	created_at: z.string(),
});

export const platformRoleRead = platformRoleBase;

export type PlatformRoleRead = z.infer<typeof platformRoleRead>;

/**
 * Get platform roles
 */
export const getPlatformRolesResponse = z.array(platformRoleRead);

export type GetPlatformRolesResponse = z.infer<typeof getPlatformRolesResponse>;

/**
 * Create platform role
 */
export const createPlatformRoleRequest = z.object({
	name: z.string().min(1).max(100),
	description: z.string().max(500).optional(),
	permissions: z.array(z.string()),
});

export const createPlatformRoleResponse = platformRoleRead;

export type CreatePlatformRoleRequest = z.infer<typeof createPlatformRoleRequest>;
export type CreatePlatformRoleResponse = z.infer<typeof createPlatformRoleResponse>;

/**
 * Update platform role
 */
export const updatePlatformRoleRequest = z.object({
	role_id: z.number(),
	data: z.object({
		name: z.string().min(1).max(100).optional(),
		description: z.string().max(500).optional(),
		permissions: z.array(z.string()).optional(),
	}),
});

export const updatePlatformRoleResponse = platformRoleRead;

export type UpdatePlatformRoleRequest = z.infer<typeof updatePlatformRoleRequest>;
export type UpdatePlatformRoleResponse = z.infer<typeof updatePlatformRoleResponse>;

/**
 * Delete platform role
 */
export const deletePlatformRoleRequest = z.object({
	role_id: z.number(),
});

export const deletePlatformRoleResponse = z.object({
	success: z.literal(true),
});

export type DeletePlatformRoleRequest = z.infer<typeof deletePlatformRoleRequest>;
export type DeletePlatformRoleResponse = z.infer<typeof deletePlatformRoleResponse>;

/**
 * Platform role assignments
 */
export const platformRoleAssignmentRead = z.object({
	id: z.number(),
	user_id: z.string(),
	role_id: z.number(),
	role_name: z.string(),
	assigned_by_id: z.string().nullable(),
	created_at: z.string(),
});

export type PlatformRoleAssignmentRead = z.infer<typeof platformRoleAssignmentRead>;

/**
 * Get role assignments
 */
export const getRoleAssignmentsResponse = z.array(platformRoleAssignmentRead);

export type GetRoleAssignmentsResponse = z.infer<typeof getRoleAssignmentsResponse>;

/**
 * Create role assignment
 */
export const createRoleAssignmentRequest = z.object({
	user_id: z.string().min(1),
	role_id: z.number(),
});

export const createRoleAssignmentResponse = platformRoleAssignmentRead;

export type CreateRoleAssignmentRequest = z.infer<typeof createRoleAssignmentRequest>;
export type CreateRoleAssignmentResponse = z.infer<typeof createRoleAssignmentResponse>;

/**
 * Delete role assignment
 */
export const deleteRoleAssignmentRequest = z.object({
	assignment_id: z.number(),
});

export const deleteRoleAssignmentResponse = z.object({
	success: z.literal(true),
});

export type DeleteRoleAssignmentRequest = z.infer<typeof deleteRoleAssignmentRequest>;
export type DeleteRoleAssignmentResponse = z.infer<typeof deleteRoleAssignmentResponse>;

/**
 * Admin audit log
 */
export const adminAuditLogRead = z.object({
	id: z.number(),
	actor_user_id: z.string().nullable(),
	action: z.string(),
	target_type: z.string(),
	target_id: z.string().nullable(),
	before: z.record(z.string(), z.unknown()).nullable(),
	after: z.record(z.string(), z.unknown()).nullable(),
	extra_metadata: z.record(z.string(), z.unknown()).nullable(),
	created_at: z.string(),
});

export type AdminAuditLogRead = z.infer<typeof adminAuditLogRead>;

/**
 * Get audit log
 */
export const getAuditLogRequest = z.object({
	limit: z.number().optional(),
	offset: z.number().optional(),
	action: z.string().optional(),
	target_type: z.string().optional(),
});

export const adminAuditLogListResponse = z.object({
	entries: z.array(adminAuditLogRead),
	total: z.number(),
});

export type GetAuditLogRequest = z.infer<typeof getAuditLogRequest>;
export type AdminAuditLogListResponse = z.infer<typeof adminAuditLogListResponse>;
