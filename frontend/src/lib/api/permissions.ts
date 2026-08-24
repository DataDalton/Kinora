import api from "../api";
import type {
	Permission,
	PermissionGroup,
	PermissionGroupCreate,
	PermissionGroupUpdate,
} from "../../types/permission";

// Map API response to typed PermissionGroup
function transformGroup(data: Record<string, unknown>): PermissionGroup {
	return {
		id: data.id as number,
		name: data.name as string,
		displayName: data.displayName as string,
		description: data.description as string | undefined,
		color: data.color as string | undefined,
		isSystem: data.isSystem as boolean,
		priority: data.priority as number,
		permissions: (data.permissions as string[]) || [],
		createdAt: data.createdAt as string,
		updatedAt: data.updatedAt as string,
	};
}

function transformPermission(data: Record<string, unknown>): Permission {
	return {
		name: data.name as string,
		displayName: data.displayName as string,
		description: data.description as string | undefined,
		category: data.category as string,
	};
}

export async function getPermissions(): Promise<Permission[]> {
	const response = await api.get("/permissions");
	return response.data.map(transformPermission);
}

export async function getPermissionGroups(): Promise<PermissionGroup[]> {
	const response = await api.get("/permissions/groups");
	return response.data.map(transformGroup);
}

export async function getPermissionGroup(id: number): Promise<PermissionGroup> {
	const response = await api.get(`/permissions/groups/${id}`);
	return transformGroup(response.data);
}

export async function createPermissionGroup(
	data: PermissionGroupCreate,
): Promise<PermissionGroup> {
	const response = await api.post("/permissions/groups", {
		name: data.name,
		displayName: data.displayName,
		description: data.description,
		color: data.color,
		permissionNames: data.permissionNames,
	});
	return transformGroup(response.data);
}

export async function updatePermissionGroup(
	id: number,
	data: PermissionGroupUpdate,
): Promise<PermissionGroup> {
	const payload: Record<string, unknown> = {};
	if (data.displayName !== undefined) payload.displayName = data.displayName;
	if (data.description !== undefined) payload.description = data.description;
	if (data.color !== undefined) payload.color = data.color;
	if (data.permissionNames !== undefined)
		payload.permissionNames = data.permissionNames;

	const response = await api.put(`/permissions/groups/${id}`, payload);
	return transformGroup(response.data);
}

export async function deletePermissionGroup(id: number): Promise<void> {
	await api.delete(`/permissions/groups/${id}`);
}
