"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import Toast from "@/components/Toast";
import ConfirmModal from "@/components/ConfirmModal";
import AuthProvidersSection from "@/components/AuthProvidersSection";
import OIDCProvidersManagement from "@/components/OIDCProvidersManagement";
import ForwardAuthSettings from "@/components/ForwardAuthSettings";
import { ChevronDown, ChevronRight } from "lucide-react";
import RootFoldersSection from "@/components/settings/RootFoldersSection";
import FolderHealthSection from "@/components/settings/FolderHealthSection";
import SystemStatusSection from "@/components/settings/SystemStatusSection";
import DatabaseBackupSection from "@/components/settings/DatabaseBackupSection";
import { usePermissions } from "@/contexts/PermissionContext";
import {
	getPermissions,
	getPermissionGroups,
	createPermissionGroup,
	updatePermissionGroup,
	deletePermissionGroup,
} from "@/lib/api/permissions";
import {
	Permission,
	PermissionGroup,
	PermissionGroupCreate,
	PermissionGroupUpdate,
} from "@/types/permission";

interface Setting {
	key: string;
	value: string | null;
	category: string;
	description: string | null;
	is_sensitive: boolean;
	value_type?: string;
}

interface SettingsGroup {
	category: string;
	settings: Setting[];
}

interface DownloadClient {
	id: number;
	name: string;
	client_type: string;
	host: string;
	port: number;
	username: string;
	use_ssl: boolean;
	is_enabled: boolean;
	is_default: boolean;
}

interface UserGroup {
	id: number;
	name: string;
	displayName: string;
	color?: string;
}

interface AppUser {
	id: number;
	username: string;
	isActive: boolean;
	groups: UserGroup[];
	createdAt: string;
	updatedAt: string;
}

// Permission categories with their permissions for display
const permissionCategories = {
	system: [
		"system.admin",
		"system.settings",
		"system.users",
		"system.groups",
		"system.logs",
		"requests.view",
		"requests.manage",
	],
	users: ["users.password.self", "users.password.reset"],
	movies: [
		"movies.view",
		"movies.manage",
		"movies.request",
		"movies.approve",
		"movies.download",
	],
	shows: [
		"shows.view",
		"shows.manage",
		"shows.request",
		"shows.approve",
		"shows.download",
	],
	anime: [
		"anime.view",
		"anime.manage",
		"anime.request",
		"anime.approve",
		"anime.download",
	],
	music: [
		"music.view",
		"music.manage",
		"music.request",
		"music.approve",
		"music.download",
	],
};

// Display order for permission categories (top to bottom)
const categoryOrder = ["system", "users", "movies", "shows", "anime", "music"];

// Predefined colors for permission groups
const predefinedColors = [
	"#3B82F6", // blue
	"#10B981", // green
	"#F59E0B", // amber
	"#EF4444", // red
	"#8B5CF6", // violet
	"#EC4899", // pink
	"#06B6D4", // cyan
	"#84CC16", // lime
	"#F97316", // orange
	"#6366F1", // indigo
];

// Permission hierarchy: selecting a permission also selects all implied permissions
const permissionImplications: Record<string, string[]> = {
	// system.admin grants all permissions
	"system.admin": [
		"system.settings",
		"system.users",
		"system.groups",
		"system.logs",
		"requests.view",
		"requests.manage",
		"users.password.self",
		"users.password.reset",
		"movies.view",
		"movies.manage",
		"movies.request",
		"movies.approve",
		"movies.download",
		"shows.view",
		"shows.manage",
		"shows.request",
		"shows.approve",
		"shows.download",
		"anime.view",
		"anime.manage",
		"anime.request",
		"anime.approve",
		"anime.download",
		"music.view",
		"music.manage",
		"music.request",
		"music.approve",
		"music.download",
	],
	// system.users implies password reset for others
	"system.users": ["users.password.reset"],
	// requests.manage implies requests.view
	"requests.manage": ["requests.view"],
	// *.manage permissions grant all other permissions in their category
	"movies.manage": [
		"movies.view",
		"movies.request",
		"movies.approve",
		"movies.download",
	],
	"shows.manage": [
		"shows.view",
		"shows.request",
		"shows.approve",
		"shows.download",
	],
	"anime.manage": [
		"anime.view",
		"anime.request",
		"anime.approve",
		"anime.download",
	],
	"music.manage": [
		"music.view",
		"music.request",
		"music.approve",
		"music.download",
	],
	// *.approve implies *.view and *.request
	"movies.approve": ["movies.view", "movies.request"],
	"shows.approve": ["shows.view", "shows.request"],
	"anime.approve": ["anime.view", "anime.request"],
	"music.approve": ["music.view", "music.request"],
	// *.download implies *.view
	"movies.download": ["movies.view"],
	"shows.download": ["shows.view"],
	"anime.download": ["anime.view"],
	"music.download": ["music.view"],
	// *.request implies *.view
	"movies.request": ["movies.view"],
	"shows.request": ["shows.view"],
	"anime.request": ["anime.view"],
	"music.request": ["music.view"],
};

// Get all permissions implied by selecting a permission (including nested implications)
function getImpliedPermissions(permissionName: string): string[] {
	const implied = new Set<string>();
	const stack = [permissionName];

	while (stack.length > 0) {
		const current = stack.pop()!;
		const directImplications = permissionImplications[current] || [];
		for (const perm of directImplications) {
			if (!implied.has(perm)) {
				implied.add(perm);
				stack.push(perm);
			}
		}
	}

	return Array.from(implied);
}

type SettingsSection =
	| "users"
	| "permission-groups"
	| "authentication"
	| "oidc-providers"
	| "forward-auth"
	| "download-clients"
	| "api-keys"
	| "root-folders"
	| "folder-health"
	| "system"
	| "system-status"
	| "database";

export default function SettingsPage() {
	const queryClient = useQueryClient();
	const { hasPermission } = usePermissions();
	const [editingKey, setEditingKey] = useState<string | null>(null);
	const [editValue, setEditValue] = useState("");
	const [selectedSection, setSelectedSection] =
		useState<SettingsSection>("users");
	const [editingClientId, setEditingClientId] = useState<number | null>(null);
	const [editingClient, setEditingClient] = useState<
		Partial<DownloadClient> & { password?: string }
	>({});
	const [expandedCategories, setExpandedCategories] = useState<
		Record<string, boolean>
	>({
		auth: true,
		general: true,
		storage: true,
	});

	// User management state
	const [showCreateUserModal, setShowCreateUserModal] = useState(false);
	const [showEditUserModal, setShowEditUserModal] = useState(false);
	const [showResetPasswordModal, setShowResetPasswordModal] = useState(false);
	const [selectedUser, setSelectedUser] = useState<AppUser | null>(null);
	const [newUserData, setNewUserData] = useState<{
		username: string;
		password: string;
		groupIds: number[];
		isActive: boolean;
	}>({ username: "", password: "", groupIds: [], isActive: true });
	const [editUserData, setEditUserData] = useState<{
		username: string;
		groupIds: number[];
		isActive: boolean;
	}>({ username: "", groupIds: [], isActive: true });
	const [resetPasswordData, setResetPasswordData] = useState({
		password: "",
	});

	// Permission group management state
	const [showCreateGroupModal, setShowCreateGroupModal] = useState(false);
	const [showEditGroupModal, setShowEditGroupModal] = useState(false);
	const [selectedGroup, setSelectedGroup] = useState<PermissionGroup | null>(
		null,
	);
	const [newGroupData, setNewGroupData] = useState<{
		name: string;
		displayName: string;
		description: string;
		color: string;
		permissionNames: string[];
	}>({
		name: "",
		displayName: "",
		description: "",
		color: predefinedColors[0],
		permissionNames: [],
	});
	const [editGroupData, setEditGroupData] = useState<{
		displayName: string;
		description: string;
		color: string;
		permissionNames: string[];
	}>({ displayName: "", description: "", color: "", permissionNames: [] });

	// Toast and confirmation state
	const [toast, setToast] = useState<{
		message: string;
		type: "success" | "error" | "info";
	} | null>(null);

	// Helper to show toast and auto-dismiss any existing toast first
	const showToast = (message: string, type: "success" | "error" | "info") => {
		setToast(null); // Clear existing toast first
		setTimeout(() => {
			setToast({ message, type });
		}, 0);
	};
	const [confirmDialog, setConfirmDialog] = useState<{
		isOpen: boolean;
		title: string;
		message: string;
		onConfirm: () => void;
	}>({ isOpen: false, title: "", message: "", onConfirm: () => {} });

	const { data: settingsGroups, isLoading } = useQuery<SettingsGroup[]>({
		queryKey: ["settings"],
		queryFn: async () => {
			const response = await api.get("/settings");
			return response.data;
		},
	});

	const { data: downloadClients } = useQuery<DownloadClient[]>({
		queryKey: ["settings-download-clients"],
		queryFn: async () => {
			const response = await api.get("/settings/download-clients");
			return response.data;
		},
	});

	const { data: users } = useQuery<AppUser[]>({
		queryKey: ["users"],
		queryFn: async () => {
			const response = await api.get("/users");
			return response.data.map((user: Record<string, unknown>) => ({
				...user,
				groups: (
					(user.groups as Array<Record<string, unknown>>) || []
				).map((g: Record<string, unknown>) => ({
					id: g.id,
					name: g.name,
					displayName: g.displayName,
					color: g.color,
				})),
			}));
		},
	});

	// Permission groups query
	const { data: permissionGroups } = useQuery<PermissionGroup[]>({
		queryKey: ["permission-groups"],
		queryFn: getPermissionGroups,
	});

	// All permissions query
	const { data: allPermissions } = useQuery<Permission[]>({
		queryKey: ["permissions"],
		queryFn: getPermissions,
	});

	// Group permissions by category for display, sorted by categoryOrder
	const permissionsByCategory = useMemo(() => {
		if (!allPermissions) return {};
		const grouped = allPermissions.reduce(
			(acc, perm) => {
				if (!acc[perm.category]) {
					acc[perm.category] = [];
				}
				acc[perm.category].push(perm);
				return acc;
			},
			{} as Record<string, Permission[]>,
		);

		// Return object with keys sorted by categoryOrder
		const sorted: Record<string, Permission[]> = {};
		for (const cat of categoryOrder) {
			if (grouped[cat]) {
				sorted[cat] = grouped[cat];
			}
		}
		// Add any remaining categories not in categoryOrder
		for (const cat of Object.keys(grouped)) {
			if (!sorted[cat]) {
				sorted[cat] = grouped[cat];
			}
		}
		return sorted;
	}, [allPermissions]);

	const initializeDefaultsMutation = useMutation({
		mutationFn: async () => {
			const response = await api.post("/settings/initialize-defaults");
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["settings"] });
		},
	});

	const updateSettingMutation = useMutation({
		mutationFn: async ({ key, value }: { key: string; value: string }) => {
			const response = await api.put(`/settings/${key}`, { value });
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["settings"] });
			setEditingKey(null);
			setEditValue("");
		},
	});

	const deleteSettingMutation = useMutation({
		mutationFn: async (key: string) => {
			const response = await api.delete(`/settings/${key}`);
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["settings"] });
		},
	});

	const updateDownloadClientMutation = useMutation({
		mutationFn: async ({
			id,
			data,
		}: {
			id: number;
			data: Partial<DownloadClient> & { password?: string };
		}) => {
			const response = await api.put(
				`/settings/download-clients/${id}`,
				data,
			);
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: ["settings-download-clients"],
			});
			setEditingClientId(null);
			setEditingClient({});
		},
	});

	const createUserMutation = useMutation({
		mutationFn: async (data: typeof newUserData) => {
			const response = await api.post("/users", {
				username: data.username,
				password: data.password,
				group_ids: data.groupIds,
				isActive: data.isActive,
			});
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["users"] });
			setShowCreateUserModal(false);
			setNewUserData({
				username: "",
				password: "",
				groupIds: [],
				isActive: true,
			});
			showToast("User created successfully!", "success");
		},
		onError: (error: any) => {
			const errorMsg = error.response?.data?.detail
				? typeof error.response.data.detail === "string"
					? error.response.data.detail
					: error.response.data.detail[0]?.msg || "Validation error"
				: "Failed to create user";
			showToast(errorMsg, "error");
		},
	});

	const updateUserMutation = useMutation({
		mutationFn: async ({
			id,
			data,
		}: {
			id: number;
			data: typeof editUserData;
		}) => {
			const response = await api.put(`/users/${id}`, {
				username: data.username,
				group_ids: data.groupIds,
				isActive: data.isActive,
			});
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["users"] });
			setShowEditUserModal(false);
			setSelectedUser(null);
			showToast("User updated successfully!", "success");
		},
		onError: (error: any) => {
			const errorMsg = error.response?.data?.detail
				? typeof error.response.data.detail === "string"
					? error.response.data.detail
					: error.response.data.detail[0]?.msg || "Validation error"
				: "Failed to update user";
			showToast(errorMsg, "error");
		},
	});

	const deleteUserMutation = useMutation({
		mutationFn: async (id: number) => {
			const response = await api.delete(`/users/${id}`);
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["users"] });
			showToast("User deleted successfully!", "success");
		},
		onError: (error: any) => {
			const errorMsg = error.response?.data?.detail
				? typeof error.response.data.detail === "string"
					? error.response.data.detail
					: error.response.data.detail[0]?.msg || "Validation error"
				: "Failed to delete user";
			showToast(errorMsg, "error");
		},
	});

	const resetPasswordMutation = useMutation({
		mutationFn: async ({
			id,
			password,
		}: {
			id: number;
			password: string;
		}) => {
			const response = await api.put(`/users/${id}/password`, {
				password,
			});
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["users"] });
			setShowResetPasswordModal(false);
			setSelectedUser(null);
			setResetPasswordData({ password: "" });
			showToast("Password reset successfully!", "success");
		},
		onError: (error: any) => {
			const errorMsg = error.response?.data?.detail
				? typeof error.response.data.detail === "string"
					? error.response.data.detail
					: error.response.data.detail[0]?.msg || "Validation error"
				: "Failed to reset password";
			showToast(errorMsg, "error");
		},
	});

	const toggleUserActiveMutation = useMutation({
		mutationFn: async (id: number) => {
			const response = await api.put(`/users/${id}/toggle-active`);
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["users"] });
		},
		onError: (error: any) => {
			const errorMsg = error.response?.data?.detail
				? typeof error.response.data.detail === "string"
					? error.response.data.detail
					: error.response.data.detail[0]?.msg || "Validation error"
				: "Failed to toggle user status";
			showToast(errorMsg, "error");
		},
	});

	// Permission group mutations
	const createGroupMutation = useMutation({
		mutationFn: async (data: PermissionGroupCreate) => {
			return await createPermissionGroup(data);
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["permission-groups"] });
			setShowCreateGroupModal(false);
			setNewGroupData({
				name: "",
				displayName: "",
				description: "",
				color: predefinedColors[0],
				permissionNames: [],
			});
			showToast("Permission group created successfully!", "success");
		},
		onError: (error: any) => {
			const errorMsg = error.response?.data?.detail
				? typeof error.response.data.detail === "string"
					? error.response.data.detail
					: error.response.data.detail[0]?.msg || "Validation error"
				: "Failed to create permission group";
			showToast(errorMsg, "error");
		},
	});

	const updateGroupMutation = useMutation({
		mutationFn: async ({
			id,
			data,
		}: {
			id: number;
			data: PermissionGroupUpdate;
		}) => {
			return await updatePermissionGroup(id, data);
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["permission-groups"] });
			queryClient.invalidateQueries({ queryKey: ["users"] });
			setShowEditGroupModal(false);
			setSelectedGroup(null);
			showToast("Permission group updated successfully!", "success");
		},
		onError: (error: any) => {
			const errorMsg = error.response?.data?.detail
				? typeof error.response.data.detail === "string"
					? error.response.data.detail
					: error.response.data.detail[0]?.msg || "Validation error"
				: "Failed to update permission group";
			showToast(errorMsg, "error");
		},
	});

	const deleteGroupMutation = useMutation({
		mutationFn: async (id: number) => {
			return await deletePermissionGroup(id);
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["permission-groups"] });
			queryClient.invalidateQueries({ queryKey: ["users"] });
			showToast("Permission group deleted successfully!", "success");
		},
		onError: (error: any) => {
			const errorMsg = error.response?.data?.detail
				? typeof error.response.data.detail === "string"
					? error.response.data.detail
					: error.response.data.detail[0]?.msg || "Validation error"
				: "Failed to delete permission group";
			showToast(errorMsg, "error");
		},
	});

	const handleEditClient = (client: DownloadClient) => {
		setEditingClientId(client.id);
		setEditingClient({
			name: client.name,
			host: client.host,
			port: client.port,
			username: client.username,
			use_ssl: client.use_ssl,
			is_enabled: client.is_enabled,
			is_default: client.is_default,
		});
	};

	const handleSaveClient = (id: number) => {
		updateDownloadClientMutation.mutate({ id, data: editingClient });
	};

	const handleCancelClientEdit = () => {
		setEditingClientId(null);
		setEditingClient({});
	};

	const handleEdit = (setting: Setting) => {
		setEditingKey(setting.key);
		setEditValue(setting.value || "");
	};

	const handleSave = (key: string) => {
		updateSettingMutation.mutate({ key, value: editValue });
	};

	const handleCancel = () => {
		setEditingKey(null);
		setEditValue("");
	};

	const handleReset = (key: string) => {
		setConfirmDialog({
			isOpen: true,
			title: "Reset Setting",
			message:
				"Reset this setting to default? This action cannot be undone.",
			onConfirm: () => {
				deleteSettingMutation.mutate(key);
				setConfirmDialog({
					isOpen: false,
					title: "",
					message: "",
					onConfirm: () => {},
				});
			},
		});
	};

	const categoryTitles: Record<string, string> = {
		api_keys: "API Keys",
		general: "General",
		paths: "Root Folders",
		system: "System",
	};

	if (isLoading) {
		return (
			<div className="min-h-screen">
				{/* Header Section */}
				<div className="bg-gradient-to-r from-slate-600/10 via-gray-600/10 to-zinc-600/10 border-b-2 border-border">
					<div className="container mx-auto px-6 py-8">
						<h1 className="text-4xl font-bold mb-2">Settings</h1>
						<p className="text-muted-foreground">
							Configure your application preferences
						</p>
					</div>
				</div>

				{/* Content Section */}
				<div className="container mx-auto px-6 py-8">
					<p>Loading settings...</p>
				</div>
			</div>
		);
	}

	const handleEditUser = (user: AppUser) => {
		setSelectedUser(user);
		setEditUserData({
			username: user.username,
			groupIds: user.groups?.map((g) => g.id) || [],
			isActive: user.isActive,
		});
		setShowEditUserModal(true);
	};

	const handleDeleteUser = (user: AppUser) => {
		setConfirmDialog({
			isOpen: true,
			title: "Delete User",
			message: `Are you sure you want to delete user "${user.username}"? This action cannot be undone.`,
			onConfirm: () => {
				deleteUserMutation.mutate(user.id);
				setConfirmDialog({
					isOpen: false,
					title: "",
					message: "",
					onConfirm: () => {},
				});
			},
		});
	};

	const handleResetPassword = (user: AppUser) => {
		setSelectedUser(user);
		setResetPasswordData({ password: "" });
		setShowResetPasswordModal(true);
	};

	// Permission group handlers
	const handleEditGroup = (group: PermissionGroup) => {
		setSelectedGroup(group);
		// Expand stored permissions to include all implied permissions for display
		const storedPermissions = group.permissions || [];
		const expandedPermissions = new Set(storedPermissions);
		for (const perm of storedPermissions) {
			const implied = getImpliedPermissions(perm);
			implied.forEach((p) => expandedPermissions.add(p));
		}
		setEditGroupData({
			displayName: group.displayName,
			description: group.description || "",
			color: group.color || predefinedColors[0],
			permissionNames: Array.from(expandedPermissions),
		});
		setShowEditGroupModal(true);
	};

	const handleDeleteGroup = (group: PermissionGroup) => {
		// Count users who will be affected
		const affectedUsers =
			users?.filter((u) => u.groups?.some((g) => g.id === group.id)) ||
			[];
		setConfirmDialog({
			isOpen: true,
			title: "Delete Permission Group",
			message: `Are you sure you want to delete "${group.displayName}"?${affectedUsers.length > 0 ? ` ${affectedUsers.length} user(s) will lose this group.` : ""} This action cannot be undone.`,
			onConfirm: () => {
				deleteGroupMutation.mutate(group.id);
				setConfirmDialog({
					isOpen: false,
					title: "",
					message: "",
					onConfirm: () => {},
				});
			},
		});
	};

	const togglePermission = (
		permissionName: string,
		currentPermissions: string[],
		setPermissions: (perms: string[]) => void,
	) => {
		if (currentPermissions.includes(permissionName)) {
			// When deselecting, also remove all implied permissions
			const implied = getImpliedPermissions(permissionName);
			const toRemove = new Set([permissionName, ...implied]);
			setPermissions(currentPermissions.filter((p) => !toRemove.has(p)));
		} else {
			// When selecting, also add all implied permissions
			const implied = getImpliedPermissions(permissionName);
			const newPermissions = new Set([
				...currentPermissions,
				permissionName,
				...implied,
			]);
			setPermissions(Array.from(newPermissions));
		}
	};

	const toggleCategory = (categoryId: string) => {
		setExpandedCategories((prev) => ({
			...prev,
			[categoryId]: !prev[categoryId],
		}));
	};

	const categories = [
		{
			id: "auth",
			name: "Authentication & Security",
			sections: [
				{
					id: "users" as SettingsSection,
					name: "User Management",
					count: users?.length || 0,
				},
				{
					id: "permission-groups" as SettingsSection,
					name: "Permission Groups",
					count: permissionGroups?.length || 0,
				},
				{
					id: "authentication" as SettingsSection,
					name: "Linked Providers",
					count: 0,
				},
				{
					id: "oidc-providers" as SettingsSection,
					name: "OIDC Providers",
					count: 0,
				},
				{
					id: "forward-auth" as SettingsSection,
					name: "Forward Auth",
					count: 0,
				},
			],
		},
		{
			id: "general",
			name: "General Settings",
			sections: [
				{
					id: "download-clients" as SettingsSection,
					name: "Download Clients",
					count: downloadClients?.length || 0,
				},
				{
					id: "api-keys" as SettingsSection,
					name: "API Keys",
					count:
						settingsGroups?.find((g) => g.category === "api_keys")
							?.settings.length || 0,
				},
				{
					id: "system" as SettingsSection,
					name: "System",
					count:
						settingsGroups?.find((g) => g.category === "system")
							?.settings.length || 0,
				},
				{
					id: "system-status" as SettingsSection,
					name: "System Status",
					count: 0,
				},
			],
		},
		{
			id: "storage",
			name: "Storage & Folders",
			sections: [
				{
					id: "root-folders" as SettingsSection,
					name: "Root Folders",
					count: 0,
				},
				{
					id: "folder-health" as SettingsSection,
					name: "Folder Health",
					count: 0,
				},
				...(hasPermission("system.admin")
					? [
							{
								id: "database" as SettingsSection,
								name: "Database & Backup",
								count: 0,
							},
						]
					: []),
			],
		},
	];

	return (
		<div className="min-h-screen bg-background">
			<div className="flex">
				{/* Left Navigation */}
				<div className="w-64 bg-card border-r border-border p-6 min-h-screen">
					<h2 className="text-xl font-bold mb-6">Settings</h2>
					<nav className="space-y-4">
						{categories.map((category) => (
							<div key={category.id}>
								<button
									onClick={() => toggleCategory(category.id)}
									className="w-full flex items-center justify-between px-2 py-2 text-sm font-semibold text-foreground hover:bg-accent rounded-lg transition-colors cursor-pointer"
								>
									<span>{category.name}</span>
									{expandedCategories[category.id] ? (
										<ChevronDown className="w-4 h-4" />
									) : (
										<ChevronRight className="w-4 h-4" />
									)}
								</button>
								{expandedCategories[category.id] && (
									<div className="mt-2 space-y-1 ml-2">
										{category.sections.map((section) => {
											const isActive =
												selectedSection === section.id;

											return (
												<button
													key={section.id}
													onClick={() =>
														setSelectedSection(
															section.id,
														)
													}
													className={`w-full flex items-center justify-between px-3 py-2 rounded-lg transition-colors cursor-pointer ${
														isActive
															? "bg-primary text-primary-foreground"
															: "hover:bg-accent"
													}`}
												>
													<span className="text-sm font-medium">
														{section.name}
													</span>
													{section.count > 0 && (
														<span
															className={`text-xs px-2 py-1 rounded-full ${
																isActive
																	? "bg-primary-foreground/20"
																	: "bg-muted"
															}`}
														>
															{section.count}
														</span>
													)}
												</button>
											);
										})}
									</div>
								)}
							</div>
						))}
					</nav>
				</div>

				{/* Main Content */}
				<div className="flex-1">
					{/* User Management Section */}
					{selectedSection === "users" && (
						<div>
							<PageHeader
								title="User Management"
								description="Manage user accounts, roles, and permissions"
								gradientFrom="purple-600/10"
								gradientVia="pink-600/10"
								gradientTo="rose-600/10"
							/>
							<div className="p-8">
								<div className="max-w-6xl mx-auto">
									<div className="mb-6 flex justify-between items-center">
										<h2 className="text-xl font-bold">
											Users
										</h2>
										<button
											onClick={() =>
												setShowCreateUserModal(true)
											}
											className="px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition cursor-pointer"
										>
											Create New User
										</button>
									</div>

									{users && users.length > 0 ? (
										<div className="bg-card text-card-foreground border border-border rounded-lg overflow-hidden shadow-sm">
											<table className="w-full">
												<thead className="bg-muted">
													<tr>
														<th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
															Username
														</th>
														<th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
															Groups
														</th>
														<th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
															Status
														</th>
														<th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">
															Created
														</th>
														<th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider">
															Actions
														</th>
													</tr>
												</thead>
												<tbody className="divide-y divide-border">
													{users.map((user) => (
														<tr
															key={user.id}
															className="hover:bg-muted/30"
														>
															<td className="px-6 py-4 whitespace-nowrap">
																<div className="font-medium">
																	{
																		user.username
																	}
																</div>
															</td>
															<td className="px-6 py-4">
																<div className="flex flex-wrap gap-1">
																	{user.groups &&
																	user.groups
																		.length >
																		0 ? (
																		user.groups.map(
																			(
																				group,
																			) => (
																				<span
																					key={
																						group.id
																					}
																					className="px-2 py-1 rounded-full text-xs font-medium text-white"
																					style={{
																						backgroundColor:
																							group.color ||
																							"#6366F1",
																					}}
																				>
																					{
																						group.displayName
																					}
																				</span>
																			),
																		)
																	) : (
																		<span className="text-muted-foreground text-sm">
																			No
																			groups
																		</span>
																	)}
																</div>
															</td>
															<td className="px-6 py-4 whitespace-nowrap">
																<button
																	onClick={() =>
																		toggleUserActiveMutation.mutate(
																			user.id,
																		)
																	}
																	className="cursor-pointer"
																>
																	<span
																		className={`px-3 py-1 rounded-full text-xs font-medium ${
																			user.isActive
																				? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
																				: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
																		}`}
																	>
																		{user.isActive
																			? "Active"
																			: "Inactive"}
																	</span>
																</button>
															</td>
															<td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
																{new Date(
																	user.createdAt,
																).toLocaleDateString()}
															</td>
															<td className="px-6 py-4 whitespace-nowrap text-right text-sm">
																<div className="flex items-center justify-end gap-2">
																	<button
																		onClick={() =>
																			handleEditUser(
																				user,
																			)
																		}
																		className="px-3 py-1 bg-primary text-primary-foreground rounded hover:opacity-90 transition cursor-pointer"
																	>
																		Edit
																	</button>
																	<button
																		onClick={() =>
																			handleResetPassword(
																				user,
																			)
																		}
																		className="px-3 py-1 bg-blue-600 text-white rounded hover:opacity-90 transition cursor-pointer"
																	>
																		Reset
																		Password
																	</button>
																	<button
																		onClick={() =>
																			handleDeleteUser(
																				user,
																			)
																		}
																		className="px-3 py-1 bg-destructive text-destructive-foreground rounded hover:opacity-90 transition cursor-pointer"
																	>
																		Delete
																	</button>
																</div>
															</td>
														</tr>
													))}
												</tbody>
											</table>
										</div>
									) : (
										<div className="text-center py-12 text-muted-foreground">
											No users found
										</div>
									)}
								</div>
							</div>
						</div>
					)}

					{/* Permission Groups Section */}
					{selectedSection === "permission-groups" && (
						<div>
							<PageHeader
								title="Permission Groups"
								description="Manage permission groups and their access levels"
								gradientFrom="amber-600/10"
								gradientVia="orange-600/10"
								gradientTo="red-600/10"
							/>
							<div className="p-8">
								<div className="max-w-6xl mx-auto">
									<div className="mb-6 flex justify-between items-center">
										<h2 className="text-xl font-bold">
											Permission Groups
										</h2>
										<button
											onClick={() =>
												setShowCreateGroupModal(true)
											}
											className="px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition cursor-pointer"
										>
											Create New Group
										</button>
									</div>

									{permissionGroups &&
									permissionGroups.length > 0 ? (
										<div className="space-y-4">
											{permissionGroups.map((group) => (
												<div
													key={group.id}
													className="bg-card text-card-foreground border border-border rounded-lg p-6 shadow-sm"
												>
													<div className="flex justify-between items-start">
														<div className="flex-1">
															<div className="flex items-center gap-3 mb-2">
																<span
																	className="w-4 h-4 rounded-full"
																	style={{
																		backgroundColor:
																			group.color ||
																			"#6366F1",
																	}}
																/>
																<h3 className="font-semibold text-lg">
																	{
																		group.displayName
																	}
																</h3>
																{group.isSystem && (
																	<span className="px-2 py-1 bg-muted text-muted-foreground text-xs rounded-full">
																		System
																	</span>
																)}
															</div>
															{group.description && (
																<p className="text-sm text-muted-foreground mb-3">
																	{
																		group.description
																	}
																</p>
															)}
															<div className="flex items-center gap-2 text-sm text-muted-foreground">
																<span>
																	{group
																		.permissions
																		?.length ||
																		0}{" "}
																	permissions
																</span>
																<span>|</span>
																<span>
																	Priority:{" "}
																	{
																		group.priority
																	}
																</span>
															</div>
														</div>
														<div className="flex items-center gap-2">
															<button
																onClick={() =>
																	handleEditGroup(
																		group,
																	)
																}
																className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition cursor-pointer"
															>
																Edit
															</button>
															{!group.isSystem && (
																<button
																	onClick={() =>
																		handleDeleteGroup(
																			group,
																		)
																	}
																	className="px-4 py-2 bg-destructive text-destructive-foreground rounded-lg hover:opacity-90 transition cursor-pointer"
																>
																	Delete
																</button>
															)}
														</div>
													</div>
												</div>
											))}
										</div>
									) : (
										<div className="text-center py-12 text-muted-foreground">
											No permission groups found
										</div>
									)}
								</div>
							</div>
						</div>
					)}

					{/* Authentication Section */}
					{selectedSection === "authentication" && (
						<div>
							<PageHeader
								title="Authentication"
								description="Manage linked authentication providers"
								gradientFrom="indigo-600/10"
								gradientVia="blue-600/10"
								gradientTo="cyan-600/10"
							/>
							<div className="p-8">
								<div className="max-w-6xl mx-auto">
									<AuthProvidersSection />
								</div>
							</div>
						</div>
					)}

					{/* OIDC Providers Section */}
					{selectedSection === "oidc-providers" && (
						<div>
							<PageHeader
								title="OIDC Providers"
								description="Configure OIDC/SSO providers for login (Admin Only)"
								gradientFrom="violet-600/10"
								gradientVia="purple-600/10"
								gradientTo="fuchsia-600/10"
							/>
							<div className="p-8">
								<div className="max-w-6xl mx-auto">
									<OIDCProvidersManagement />
								</div>
							</div>
						</div>
					)}

					{/* Forward Auth Section */}
					{selectedSection === "forward-auth" && (
						<div>
							<PageHeader
								title="Forward Authentication"
								description="Configure trusted proxy IPs for Authelia/Authentik forward authentication"
								gradientFrom="emerald-600/10"
								gradientVia="teal-600/10"
								gradientTo="cyan-600/10"
							/>
							<div className="p-8">
								<div className="max-w-6xl mx-auto">
									<ForwardAuthSettings />
								</div>
							</div>
						</div>
					)}

					{/* Download Clients Section */}
					{selectedSection === "download-clients" && (
						<div>
							<PageHeader
								title="Download Clients"
								description="Manage your configured download clients"
								gradientFrom="blue-600/10"
								gradientVia="indigo-600/10"
								gradientTo="purple-600/10"
							/>
							<div className="p-8">
								<div className="max-w-6xl mx-auto">
									{downloadClients &&
									downloadClients.length > 0 ? (
										<div className="space-y-4">
											{downloadClients.map((client) => (
												<div
													key={client.id}
													className="bg-card text-card-foreground border-border border rounded-lg p-4 shadow-sm"
												>
													{editingClientId ===
													client.id ? (
														<div className="space-y-4">
															<div className="grid grid-cols-2 gap-4">
																<div>
																	<label className="block text-sm font-medium mb-1">
																		Name
																	</label>
																	<input
																		type="text"
																		value={
																			editingClient.name ||
																			""
																		}
																		onChange={(
																			e,
																		) =>
																			setEditingClient(
																				{
																					...editingClient,
																					name: e
																						.target
																						.value,
																				},
																			)
																		}
																		className="w-full px-3 py-2 border border-border rounded-md bg-background"
																	/>
																</div>
																<div>
																	<label className="block text-sm font-medium mb-1">
																		Host
																	</label>
																	<input
																		type="text"
																		value={
																			editingClient.host ||
																			""
																		}
																		onChange={(
																			e,
																		) =>
																			setEditingClient(
																				{
																					...editingClient,
																					host: e
																						.target
																						.value,
																				},
																			)
																		}
																		className="w-full px-3 py-2 border border-border rounded-md bg-background"
																	/>
																</div>
																<div>
																	<label className="block text-sm font-medium mb-1">
																		Port
																	</label>
																	<input
																		type="number"
																		value={
																			editingClient.port ||
																			""
																		}
																		onChange={(
																			e,
																		) =>
																			setEditingClient(
																				{
																					...editingClient,
																					port: parseInt(
																						e
																							.target
																							.value,
																					),
																				},
																			)
																		}
																		className="w-full px-3 py-2 border border-border rounded-md bg-background"
																	/>
																</div>
																<div>
																	<label className="block text-sm font-medium mb-1">
																		Username
																	</label>
																	<input
																		type="text"
																		value={
																			editingClient.username ||
																			""
																		}
																		onChange={(
																			e,
																		) =>
																			setEditingClient(
																				{
																					...editingClient,
																					username:
																						e
																							.target
																							.value,
																				},
																			)
																		}
																		className="w-full px-3 py-2 border border-border rounded-md bg-background"
																	/>
																</div>
																<div>
																	<label className="block text-sm font-medium mb-1">
																		Password
																		(leave
																		blank to
																		keep
																		current)
																	</label>
																	<input
																		type="password"
																		value={
																			editingClient.password ||
																			""
																		}
																		onChange={(
																			e,
																		) =>
																			setEditingClient(
																				{
																					...editingClient,
																					password:
																						e
																							.target
																							.value,
																				},
																			)
																		}
																		placeholder="********"
																		className="w-full px-3 py-2 border border-border rounded-md bg-background"
																	/>
																</div>
																<div className="col-span-2 space-y-3">
																	<label className="flex items-center justify-between p-3 bg-muted/50 rounded-md cursor-pointer">
																		<span className="text-sm font-medium">
																			Use
																			SSL
																		</span>
																		<div className="relative inline-flex items-center">
																			<input
																				type="checkbox"
																				checked={
																					editingClient.use_ssl ||
																					false
																				}
																				onChange={(
																					e,
																				) =>
																					setEditingClient(
																						{
																							...editingClient,
																							use_ssl:
																								e
																									.target
																									.checked,
																						},
																					)
																				}
																				className="sr-only peer"
																			/>
																			<div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
																		</div>
																	</label>
																	<label className="flex items-center justify-between p-3 bg-muted/50 rounded-md cursor-pointer">
																		<span className="text-sm font-medium">
																			Enabled
																		</span>
																		<div className="relative inline-flex items-center">
																			<input
																				type="checkbox"
																				checked={
																					editingClient.is_enabled ||
																					false
																				}
																				onChange={(
																					e,
																				) =>
																					setEditingClient(
																						{
																							...editingClient,
																							is_enabled:
																								e
																									.target
																									.checked,
																						},
																					)
																				}
																				className="sr-only peer"
																			/>
																			<div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
																		</div>
																	</label>
																	<label className="flex items-center justify-between p-3 bg-muted/50 rounded-md cursor-pointer">
																		<span className="text-sm font-medium">
																			Set
																			as
																			Default
																		</span>
																		<div className="relative inline-flex items-center">
																			<input
																				type="checkbox"
																				checked={
																					editingClient.is_default ||
																					false
																				}
																				onChange={(
																					e,
																				) =>
																					setEditingClient(
																						{
																							...editingClient,
																							is_default:
																								e
																									.target
																									.checked,
																						},
																					)
																				}
																				className="sr-only peer"
																			/>
																			<div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
																		</div>
																	</label>
																</div>
															</div>
															<div className="flex gap-2">
																<button
																	onClick={() =>
																		handleSaveClient(
																			client.id,
																		)
																	}
																	className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 cursor-pointer"
																>
																	Save
																</button>
																<button
																	onClick={
																		handleCancelClientEdit
																	}
																	className="px-4 py-2 border border-border rounded-md hover:bg-accent cursor-pointer"
																>
																	Cancel
																</button>
															</div>
														</div>
													) : (
														<div className="flex justify-between items-start">
															<div className="flex-1">
																<div className="flex items-center gap-2 mb-2">
																	<h3 className="font-medium text-lg">
																		{
																			client.name
																		}
																	</h3>
																	{client.is_default && (
																		<span className="px-2 py-1 bg-primary text-primary-foreground text-xs rounded">
																			Default
																		</span>
																	)}
																	{client.is_enabled ? (
																		<span className="px-2 py-1 bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 text-xs rounded">
																			Enabled
																		</span>
																	) : (
																		<span className="px-2 py-1 bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200 text-xs rounded">
																			Disabled
																		</span>
																	)}
																</div>
																<div className="grid grid-cols-2 gap-2 text-sm">
																	<div>
																		<span className="text-muted-foreground">
																			Type:
																		</span>
																		<span className="ml-2 font-medium">
																			{
																				client.client_type
																			}
																		</span>
																	</div>
																	<div>
																		<span className="text-muted-foreground">
																			Host:
																		</span>
																		<span className="ml-2 font-mono text-sm">
																			{client.use_ssl
																				? "https://"
																				: "http://"}
																			{
																				client.host
																			}
																			:
																			{
																				client.port
																			}
																		</span>
																	</div>
																	<div>
																		<span className="text-muted-foreground">
																			Username:
																		</span>
																		<span className="ml-2 font-medium">
																			{
																				client.username
																			}
																		</span>
																	</div>
																</div>
															</div>
															<button
																onClick={() =>
																	handleEditClient(
																		client,
																	)
																}
																className="ml-4 px-3 py-1 text-sm border border-border rounded-md hover:bg-accent cursor-pointer"
															>
																Edit
															</button>
														</div>
													)}
												</div>
											))}
										</div>
									) : (
										<div className="text-center py-12 text-muted-foreground">
											No download clients configured
										</div>
									)}
								</div>
							</div>
						</div>
					)}

					{/* API Keys Section */}
					{selectedSection === "api-keys" && (
						<div>
							<PageHeader
								title="API Keys"
								description="Manage API keys for external services"
								gradientFrom="green-600/10"
								gradientVia="emerald-600/10"
								gradientTo="teal-600/10"
							/>
							<div className="p-8">
								<div className="max-w-6xl mx-auto">
									{settingsGroups?.find(
										(g) => g.category === "api_keys",
									) && (
										<SettingsGroupSection
											group={
												settingsGroups.find(
													(g) =>
														g.category ===
														"api_keys",
												)!
											}
											editingKey={editingKey}
											editValue={editValue}
											onEdit={handleEdit}
											onSave={handleSave}
											onCancel={handleCancel}
											onReset={handleReset}
											setEditValue={setEditValue}
											updateMutation={
												updateSettingMutation
											}
											deleteMutation={
												deleteSettingMutation
											}
										/>
									)}
								</div>
							</div>
						</div>
					)}

					{/* System Section */}
					{selectedSection === "system" && (
						<div>
							<PageHeader
								title="System Settings"
								description="System configuration and status"
								gradientFrom="slate-600/10"
								gradientVia="gray-600/10"
								gradientTo="zinc-600/10"
							/>
							<div className="p-8">
								<div className="max-w-6xl mx-auto">
									{settingsGroups?.find(
										(g) => g.category === "system",
									) && (
										<SettingsGroupSection
											group={
												settingsGroups.find(
													(g) =>
														g.category === "system",
												)!
											}
											editingKey={editingKey}
											editValue={editValue}
											onEdit={handleEdit}
											onSave={handleSave}
											onCancel={handleCancel}
											onReset={handleReset}
											setEditValue={setEditValue}
											updateMutation={
												updateSettingMutation
											}
											deleteMutation={
												deleteSettingMutation
											}
										/>
									)}
								</div>
							</div>
						</div>
					)}

					{/* Root Folders Section */}
					{selectedSection === "root-folders" && (
						<RootFoldersSection />
					)}

					{/* Folder Health Section */}
					{selectedSection === "folder-health" && (
						<FolderHealthSection />
					)}

					{/* System Status Section */}
					{selectedSection === "system-status" && (
						<SystemStatusSection />
					)}

					{/* Database & Backup Section */}
					{selectedSection === "database" && (
						<DatabaseBackupSection />
					)}
				</div>
			</div>

			{/* Create User Modal */}
			{showCreateUserModal && (
				<div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-50 flex items-center justify-center p-4">
					<div className="bg-background rounded-lg max-w-lg w-full border border-border shadow-2xl p-6 max-h-[90vh] overflow-y-auto">
						<h2 className="text-2xl font-bold mb-4">
							Create New User
						</h2>
						<div className="space-y-4">
							<div>
								<label className="block text-sm font-medium mb-1">
									Username
								</label>
								<input
									type="text"
									value={newUserData.username}
									onChange={(e) =>
										setNewUserData({
											...newUserData,
											username: e.target.value,
										})
									}
									className="w-full px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
									placeholder="Enter username"
								/>
							</div>
							<div>
								<label className="block text-sm font-medium mb-1">
									Password
								</label>
								<input
									type="password"
									value={newUserData.password}
									onChange={(e) =>
										setNewUserData({
											...newUserData,
											password: e.target.value,
										})
									}
									className="w-full px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
									placeholder="Enter password (min 8 characters)"
								/>
							</div>
							<div>
								<label className="block text-sm font-medium mb-2">
									Permission Groups
								</label>
								<div className="space-y-1 max-h-48 overflow-y-auto border border-border rounded-lg p-2">
									{permissionGroups &&
									permissionGroups.length > 0 ? (
										permissionGroups.map((group) => {
											const isSelected =
												newUserData.groupIds.includes(
													group.id,
												);
											return (
												<button
													key={group.id}
													type="button"
													onClick={() => {
														if (isSelected) {
															setNewUserData({
																...newUserData,
																groupIds:
																	newUserData.groupIds.filter(
																		(id) =>
																			id !==
																			group.id,
																	),
															});
														} else {
															setNewUserData({
																...newUserData,
																groupIds: [
																	...newUserData.groupIds,
																	group.id,
																],
															});
														}
													}}
													className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition cursor-pointer ${
														isSelected
															? "bg-primary/10 ring-1 ring-primary"
															: "hover:bg-muted/50"
													}`}
												>
													<span
														className="w-3 h-3 rounded-full shrink-0"
														style={{
															backgroundColor:
																group.color ||
																"#6366F1",
														}}
													/>
													<span
														className={`flex-1 text-left text-sm ${isSelected ? "font-medium" : ""}`}
													>
														{group.displayName}
													</span>
													{group.isSystem && (
														<span className="text-xs text-muted-foreground">
															System
														</span>
													)}
													{isSelected && (
														<svg
															className="w-4 h-4 text-primary"
															fill="none"
															viewBox="0 0 24 24"
															stroke="currentColor"
														>
															<path
																strokeLinecap="round"
																strokeLinejoin="round"
																strokeWidth={2}
																d="M5 13l4 4L19 7"
															/>
														</svg>
													)}
												</button>
											);
										})
									) : (
										<p className="text-sm text-muted-foreground p-2">
											No permission groups available
										</p>
									)}
								</div>
							</div>
							<label className="flex items-center justify-between p-3 bg-muted/50 rounded-lg cursor-pointer">
								<div>
									<div className="font-semibold">Active</div>
									<div className="text-xs text-muted-foreground">
										User can log in and access the system
									</div>
								</div>
								<div className="relative inline-flex items-center">
									<input
										type="checkbox"
										checked={newUserData.isActive}
										onChange={(e) =>
											setNewUserData({
												...newUserData,
												isActive: e.target.checked,
											})
										}
										className="sr-only peer"
									/>
									<div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
								</div>
							</label>
							<div className="flex gap-3 pt-4">
								<button
									onClick={() =>
										createUserMutation.mutate(newUserData)
									}
									disabled={
										createUserMutation.isPending ||
										!newUserData.username ||
										!newUserData.password
									}
									className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer transition"
								>
									{createUserMutation.isPending
										? "Creating..."
										: "Create User"}
								</button>
								<button
									onClick={() => {
										setShowCreateUserModal(false);
										setNewUserData({
											username: "",
											password: "",
											groupIds: [],
											isActive: true,
										});
									}}
									className="px-6 py-3 bg-muted text-foreground rounded-lg hover:opacity-90 cursor-pointer transition"
								>
									Cancel
								</button>
							</div>
						</div>
					</div>
				</div>
			)}

			{/* Edit User Modal */}
			{showEditUserModal && selectedUser && (
				<div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-50 flex items-center justify-center p-4">
					<div className="bg-background rounded-lg max-w-lg w-full border border-border shadow-2xl p-6 max-h-[90vh] overflow-y-auto">
						<h2 className="text-2xl font-bold mb-4">
							Edit User: {selectedUser.username}
						</h2>
						<div className="space-y-4">
							<div>
								<label className="block text-sm font-medium mb-1">
									Username
								</label>
								<input
									type="text"
									value={editUserData.username}
									onChange={(e) =>
										setEditUserData({
											...editUserData,
											username: e.target.value,
										})
									}
									className="w-full px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
									placeholder="Enter username"
								/>
							</div>
							<div>
								<label className="block text-sm font-medium mb-2">
									Permission Groups
								</label>
								<div className="space-y-1 max-h-48 overflow-y-auto border border-border rounded-lg p-2">
									{permissionGroups &&
									permissionGroups.length > 0 ? (
										permissionGroups.map((group) => {
											const isSelected =
												editUserData.groupIds.includes(
													group.id,
												);
											return (
												<button
													key={group.id}
													type="button"
													onClick={() => {
														if (isSelected) {
															setEditUserData({
																...editUserData,
																groupIds:
																	editUserData.groupIds.filter(
																		(id) =>
																			id !==
																			group.id,
																	),
															});
														} else {
															setEditUserData({
																...editUserData,
																groupIds: [
																	...editUserData.groupIds,
																	group.id,
																],
															});
														}
													}}
													className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition cursor-pointer ${
														isSelected
															? "bg-primary/10 ring-1 ring-primary"
															: "hover:bg-muted/50"
													}`}
												>
													<span
														className="w-3 h-3 rounded-full shrink-0"
														style={{
															backgroundColor:
																group.color ||
																"#6366F1",
														}}
													/>
													<span
														className={`flex-1 text-left text-sm ${isSelected ? "font-medium" : ""}`}
													>
														{group.displayName}
													</span>
													{group.isSystem && (
														<span className="text-xs text-muted-foreground">
															System
														</span>
													)}
													{isSelected && (
														<svg
															className="w-4 h-4 text-primary"
															fill="none"
															viewBox="0 0 24 24"
															stroke="currentColor"
														>
															<path
																strokeLinecap="round"
																strokeLinejoin="round"
																strokeWidth={2}
																d="M5 13l4 4L19 7"
															/>
														</svg>
													)}
												</button>
											);
										})
									) : (
										<p className="text-sm text-muted-foreground p-2">
											No permission groups available
										</p>
									)}
								</div>
							</div>
							<label className="flex items-center justify-between p-3 bg-muted/50 rounded-lg cursor-pointer">
								<div>
									<div className="font-semibold">Active</div>
									<div className="text-xs text-muted-foreground">
										User can log in and access the system
									</div>
								</div>
								<div className="relative inline-flex items-center">
									<input
										type="checkbox"
										checked={editUserData.isActive}
										onChange={(e) =>
											setEditUserData({
												...editUserData,
												isActive: e.target.checked,
											})
										}
										className="sr-only peer"
									/>
									<div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
								</div>
							</label>
							<div className="flex gap-3 pt-4">
								<button
									onClick={() =>
										updateUserMutation.mutate({
											id: selectedUser.id,
											data: editUserData,
										})
									}
									disabled={
										updateUserMutation.isPending ||
										!editUserData.username
									}
									className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer transition"
								>
									{updateUserMutation.isPending
										? "Updating..."
										: "Update User"}
								</button>
								<button
									onClick={() => {
										setShowEditUserModal(false);
										setSelectedUser(null);
									}}
									className="px-6 py-3 bg-muted text-foreground rounded-lg hover:opacity-90 cursor-pointer transition"
								>
									Cancel
								</button>
							</div>
						</div>
					</div>
				</div>
			)}

			{/* Reset Password Modal */}
			{showResetPasswordModal && selectedUser && (
				<div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-50 flex items-center justify-center p-4">
					<div className="bg-background rounded-lg max-w-md w-full border border-border shadow-2xl p-6">
						<h2 className="text-2xl font-bold mb-4">
							Reset Password: {selectedUser.username}
						</h2>
						<div className="space-y-4">
							<div>
								<label className="block text-sm font-medium mb-1">
									New Password
								</label>
								<input
									type="password"
									value={resetPasswordData.password}
									onChange={(e) =>
										setResetPasswordData({
											password: e.target.value,
										})
									}
									className="w-full px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
									placeholder="Enter new password (min 8 characters)"
								/>
							</div>
							<div className="flex gap-3 pt-4">
								<button
									onClick={() =>
										resetPasswordMutation.mutate({
											id: selectedUser.id,
											password:
												resetPasswordData.password,
										})
									}
									disabled={
										resetPasswordMutation.isPending ||
										!resetPasswordData.password ||
										resetPasswordData.password.length < 8
									}
									className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer transition"
								>
									{resetPasswordMutation.isPending
										? "Resetting..."
										: "Reset Password"}
								</button>
								<button
									onClick={() => {
										setShowResetPasswordModal(false);
										setSelectedUser(null);
										setResetPasswordData({ password: "" });
									}}
									className="px-6 py-3 bg-muted text-foreground rounded-lg hover:opacity-90 cursor-pointer transition"
								>
									Cancel
								</button>
							</div>
						</div>
					</div>
				</div>
			)}

			{/* Create Permission Group Modal */}
			{showCreateGroupModal && (
				<div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-50 flex items-center justify-center p-4">
					<div className="bg-background rounded-lg max-w-5xl w-full border border-border shadow-2xl max-h-[90vh] overflow-hidden flex flex-col">
						<div className="p-6 border-b border-border">
							<h2 className="text-2xl font-bold">
								Create Permission Group
							</h2>
						</div>
						<div className="flex-1 flex overflow-hidden">
							{/* Left Panel - Group Details */}
							<div className="w-80 shrink-0 p-6 border-r border-border overflow-y-auto">
								<div className="space-y-4">
									<div>
										<label className="block text-sm font-medium mb-1">
											Name (identifier)
										</label>
										<input
											type="text"
											value={newGroupData.name}
											onChange={(e) =>
												setNewGroupData({
													...newGroupData,
													name: e.target.value
														.toLowerCase()
														.replace(
															/[^a-z0-9_]/g,
															"_",
														),
												})
											}
											className="w-full px-3 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary text-sm"
											placeholder="group_name"
										/>
										<p className="text-xs text-muted-foreground mt-1">
											Lowercase, underscores only
										</p>
									</div>
									<div>
										<label className="block text-sm font-medium mb-1">
											Display Name
										</label>
										<input
											type="text"
											value={newGroupData.displayName}
											onChange={(e) =>
												setNewGroupData({
													...newGroupData,
													displayName: e.target.value,
												})
											}
											className="w-full px-3 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary text-sm"
											placeholder="Group Name"
										/>
									</div>
									<div>
										<label className="block text-sm font-medium mb-1">
											Description
										</label>
										<textarea
											value={newGroupData.description}
											onChange={(e) =>
												setNewGroupData({
													...newGroupData,
													description: e.target.value,
												})
											}
											className="w-full px-3 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary resize-none text-sm"
											placeholder="Optional description..."
											rows={3}
										/>
									</div>
									<div>
										<label className="block text-sm font-medium mb-2">
											Color
										</label>
										<div className="flex flex-wrap gap-2">
											{predefinedColors.map((color) => (
												<button
													key={color}
													type="button"
													onClick={() =>
														setNewGroupData({
															...newGroupData,
															color,
														})
													}
													className={`w-7 h-7 rounded-full cursor-pointer transition-transform ${newGroupData.color === color ? "ring-2 ring-offset-2 ring-primary scale-110" : "hover:scale-105"}`}
													style={{
														backgroundColor: color,
													}}
												/>
											))}
											<input
												type="color"
												value={newGroupData.color}
												onChange={(e) =>
													setNewGroupData({
														...newGroupData,
														color: e.target.value,
													})
												}
												className="w-7 h-7 rounded cursor-pointer"
											/>
										</div>
									</div>
									<div className="pt-2">
										<div className="flex items-center gap-2 text-sm text-muted-foreground">
											<span
												className="w-3 h-3 rounded-full"
												style={{
													backgroundColor:
														newGroupData.color ||
														predefinedColors[0],
												}}
											/>
											<span className="font-medium text-foreground">
												{newGroupData.displayName ||
													"Preview"}
											</span>
										</div>
									</div>
								</div>
							</div>

							{/* Right Panel - Permissions */}
							<div className="flex-1 p-6 overflow-y-auto">
								<div className="mb-4 flex items-center justify-between">
									<h3 className="text-lg font-semibold">
										Permissions
									</h3>
									<span className="text-sm text-muted-foreground">
										{newGroupData.permissionNames.length}{" "}
										selected
									</span>
								</div>
								<div className="space-y-6">
									{Object.entries(permissionsByCategory).map(
										([category, perms]) => (
											<div key={category}>
												<div className="flex items-center gap-2 mb-3">
													<h4 className="font-medium capitalize text-sm">
														{category}
													</h4>
													<button
														type="button"
														onClick={() => {
															const categoryPermNames =
																perms.map(
																	(p) =>
																		p.name,
																);
															const allSelected =
																categoryPermNames.every(
																	(p) =>
																		newGroupData.permissionNames.includes(
																			p,
																		),
																);
															if (allSelected) {
																setNewGroupData(
																	{
																		...newGroupData,
																		permissionNames:
																			newGroupData.permissionNames.filter(
																				(
																					p,
																				) =>
																					!categoryPermNames.includes(
																						p,
																					),
																			),
																	},
																);
															} else {
																const newPerms =
																	[
																		...new Set(
																			[
																				...newGroupData.permissionNames,
																				...categoryPermNames,
																			],
																		),
																	];
																setNewGroupData(
																	{
																		...newGroupData,
																		permissionNames:
																			newPerms,
																	},
																);
															}
														}}
														className="text-xs text-primary hover:underline cursor-pointer"
													>
														{perms.every((p) =>
															newGroupData.permissionNames.includes(
																p.name,
															),
														)
															? "Deselect all"
															: "Select all"}
													</button>
												</div>
												<div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
													{perms.map((perm) => {
														const isChecked =
															newGroupData.permissionNames.includes(
																perm.name,
															);
														return (
															<button
																key={perm.name}
																type="button"
																onClick={() =>
																	togglePermission(
																		perm.name,
																		newGroupData.permissionNames,
																		(
																			perms,
																		) =>
																			setNewGroupData(
																				{
																					...newGroupData,
																					permissionNames:
																						perms,
																				},
																			),
																	)
																}
																className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left transition cursor-pointer ${
																	isChecked
																		? "bg-primary/10 ring-1 ring-primary"
																		: "bg-muted/50 hover:bg-muted"
																}`}
															>
																{isChecked ? (
																	<svg
																		className="w-4 h-4 text-primary shrink-0"
																		fill="none"
																		viewBox="0 0 24 24"
																		stroke="currentColor"
																	>
																		<path
																			strokeLinecap="round"
																			strokeLinejoin="round"
																			strokeWidth={
																				2
																			}
																			d="M5 13l4 4L19 7"
																		/>
																	</svg>
																) : (
																	<div className="w-4 h-4 rounded border border-border shrink-0" />
																)}
																<span
																	className={
																		isChecked
																			? "font-medium"
																			: ""
																	}
																>
																	{
																		perm.displayName
																	}
																</span>
															</button>
														);
													})}
												</div>
											</div>
										),
									)}
								</div>
							</div>
						</div>
						<div className="p-6 border-t border-border flex gap-3">
							<button
								onClick={() =>
									createGroupMutation.mutate(newGroupData)
								}
								disabled={
									createGroupMutation.isPending ||
									!newGroupData.name ||
									!newGroupData.displayName
								}
								className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer transition"
							>
								{createGroupMutation.isPending
									? "Creating..."
									: "Create Group"}
							</button>
							<button
								onClick={() => {
									setShowCreateGroupModal(false);
									setNewGroupData({
										name: "",
										displayName: "",
										description: "",
										color: predefinedColors[0],
										permissionNames: [],
									});
								}}
								className="px-6 py-3 bg-muted text-foreground rounded-lg hover:opacity-90 cursor-pointer transition"
							>
								Cancel
							</button>
						</div>
					</div>
				</div>
			)}

			{/* Edit Permission Group Modal */}
			{showEditGroupModal && selectedGroup && (
				<div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-50 flex items-center justify-center p-4">
					<div className="bg-background rounded-lg max-w-5xl w-full border border-border shadow-2xl max-h-[90vh] overflow-hidden flex flex-col">
						<div className="p-6 border-b border-border">
							<div className="flex items-center gap-3">
								<h2 className="text-2xl font-bold">
									Edit Permission Group
								</h2>
								{selectedGroup.isSystem && (
									<span className="px-2 py-1 bg-muted text-muted-foreground text-sm rounded-full">
										System
									</span>
								)}
							</div>
						</div>
						<div className="flex-1 flex overflow-hidden">
							{/* Left Panel - Group Details */}
							<div className="w-80 shrink-0 p-6 border-r border-border overflow-y-auto">
								<div className="space-y-4">
									<div>
										<label className="block text-sm font-medium mb-1">
											Name (identifier)
										</label>
										<input
											type="text"
											value={selectedGroup.name}
											disabled
											className="w-full px-3 py-2 border border-border bg-muted text-muted-foreground rounded-lg cursor-not-allowed text-sm"
										/>
										<p className="text-xs text-muted-foreground mt-1">
											Cannot be changed
										</p>
									</div>
									<div>
										<label className="block text-sm font-medium mb-1">
											Display Name
										</label>
										<input
											type="text"
											value={editGroupData.displayName}
											onChange={(e) =>
												setEditGroupData({
													...editGroupData,
													displayName: e.target.value,
												})
											}
											className="w-full px-3 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary text-sm"
											placeholder="Group Name"
										/>
									</div>
									<div>
										<label className="block text-sm font-medium mb-1">
											Description
										</label>
										<textarea
											value={editGroupData.description}
											onChange={(e) =>
												setEditGroupData({
													...editGroupData,
													description: e.target.value,
												})
											}
											className="w-full px-3 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary resize-none text-sm"
											placeholder="Optional description..."
											rows={3}
										/>
									</div>
									<div>
										<label className="block text-sm font-medium mb-2">
											Color
										</label>
										<div className="flex flex-wrap gap-2">
											{predefinedColors.map((color) => (
												<button
													key={color}
													type="button"
													onClick={() =>
														setEditGroupData({
															...editGroupData,
															color,
														})
													}
													className={`w-7 h-7 rounded-full cursor-pointer transition-transform ${editGroupData.color === color ? "ring-2 ring-offset-2 ring-primary scale-110" : "hover:scale-105"}`}
													style={{
														backgroundColor: color,
													}}
												/>
											))}
											<input
												type="color"
												value={editGroupData.color}
												onChange={(e) =>
													setEditGroupData({
														...editGroupData,
														color: e.target.value,
													})
												}
												className="w-7 h-7 rounded cursor-pointer"
											/>
										</div>
									</div>
									<div className="pt-2">
										<div className="flex items-center gap-2 text-sm text-muted-foreground">
											<span
												className="w-3 h-3 rounded-full"
												style={{
													backgroundColor:
														editGroupData.color ||
														predefinedColors[0],
												}}
											/>
											<span className="font-medium text-foreground">
												{editGroupData.displayName ||
													"Preview"}
											</span>
										</div>
									</div>
								</div>
							</div>

							{/* Right Panel - Permissions */}
							<div className="flex-1 p-6 overflow-y-auto">
								<div className="mb-4 flex items-center justify-between">
									<h3 className="text-lg font-semibold">
										Permissions
									</h3>
									<span className="text-sm text-muted-foreground">
										{editGroupData.permissionNames.length}{" "}
										selected
									</span>
								</div>
								<div className="space-y-6">
									{Object.entries(permissionsByCategory).map(
										([category, perms]) => (
											<div key={category}>
												<div className="flex items-center gap-2 mb-3">
													<h4 className="font-medium capitalize text-sm">
														{category}
													</h4>
													<button
														type="button"
														onClick={() => {
															const categoryPermNames =
																perms.map(
																	(p) =>
																		p.name,
																);
															const allSelected =
																categoryPermNames.every(
																	(p) =>
																		editGroupData.permissionNames.includes(
																			p,
																		),
																);
															if (allSelected) {
																setEditGroupData(
																	{
																		...editGroupData,
																		permissionNames:
																			editGroupData.permissionNames.filter(
																				(
																					p,
																				) =>
																					!categoryPermNames.includes(
																						p,
																					),
																			),
																	},
																);
															} else {
																const newPerms =
																	[
																		...new Set(
																			[
																				...editGroupData.permissionNames,
																				...categoryPermNames,
																			],
																		),
																	];
																setEditGroupData(
																	{
																		...editGroupData,
																		permissionNames:
																			newPerms,
																	},
																);
															}
														}}
														className="text-xs text-primary hover:underline cursor-pointer"
													>
														{perms.every((p) =>
															editGroupData.permissionNames.includes(
																p.name,
															),
														)
															? "Deselect all"
															: "Select all"}
													</button>
												</div>
												<div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
													{perms.map((perm) => {
														const isChecked =
															editGroupData.permissionNames.includes(
																perm.name,
															);
														return (
															<button
																key={perm.name}
																type="button"
																onClick={() =>
																	togglePermission(
																		perm.name,
																		editGroupData.permissionNames,
																		(
																			perms,
																		) =>
																			setEditGroupData(
																				{
																					...editGroupData,
																					permissionNames:
																						perms,
																				},
																			),
																	)
																}
																className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left transition cursor-pointer ${
																	isChecked
																		? "bg-primary/10 ring-1 ring-primary"
																		: "bg-muted/50 hover:bg-muted"
																}`}
															>
																{isChecked ? (
																	<svg
																		className="w-4 h-4 text-primary shrink-0"
																		fill="none"
																		viewBox="0 0 24 24"
																		stroke="currentColor"
																	>
																		<path
																			strokeLinecap="round"
																			strokeLinejoin="round"
																			strokeWidth={
																				2
																			}
																			d="M5 13l4 4L19 7"
																		/>
																	</svg>
																) : (
																	<div className="w-4 h-4 rounded border border-border shrink-0" />
																)}
																<span
																	className={
																		isChecked
																			? "font-medium"
																			: ""
																	}
																>
																	{
																		perm.displayName
																	}
																</span>
															</button>
														);
													})}
												</div>
											</div>
										),
									)}
								</div>
							</div>
						</div>
						<div className="p-6 border-t border-border flex gap-3">
							<button
								onClick={() =>
									updateGroupMutation.mutate({
										id: selectedGroup.id,
										data: editGroupData,
									})
								}
								disabled={
									updateGroupMutation.isPending ||
									!editGroupData.displayName
								}
								className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer transition"
							>
								{updateGroupMutation.isPending
									? "Updating..."
									: "Update Group"}
							</button>
							<button
								onClick={() => {
									setShowEditGroupModal(false);
									setSelectedGroup(null);
								}}
								className="px-6 py-3 bg-muted text-foreground rounded-lg hover:opacity-90 cursor-pointer transition"
							>
								Cancel
							</button>
						</div>
					</div>
				</div>
			)}

			{/* Confirm Dialog */}
			<ConfirmModal
				isOpen={confirmDialog.isOpen}
				title={confirmDialog.title}
				message={confirmDialog.message}
				confirmText="Delete"
				cancelText="Cancel"
				variant="danger"
				onConfirm={confirmDialog.onConfirm}
				onCancel={() =>
					setConfirmDialog({
						isOpen: false,
						title: "",
						message: "",
						onConfirm: () => {},
					})
				}
			/>

			{/* Toast Notification */}
			{toast && (
				<div className="fixed bottom-4 right-4 z-70">
					<Toast
						message={toast.message}
						type={toast.type}
						onClose={() => setToast(null)}
					/>
				</div>
			)}
		</div>
	);
}

function SettingsGroupSection({
	group,
	editingKey,
	editValue,
	onEdit,
	onSave,
	onCancel,
	onReset,
	setEditValue,
	updateMutation,
	deleteMutation,
}: {
	group: SettingsGroup;
	editingKey: string | null;
	editValue: string;
	onEdit: (setting: Setting) => void;
	onSave: (key: string) => void;
	onCancel: () => void;
	onReset: (key: string) => void;
	setEditValue: (value: string) => void;
	updateMutation: any;
	deleteMutation: any;
}) {
	return (
		<div className="space-y-4">
			{group.settings.map((setting) => (
				<div
					key={setting.key}
					className="bg-card text-card-foreground border-border border rounded-lg p-4 shadow-sm"
				>
					<div className="flex justify-between items-start">
						<div className="flex-1">
							<h3 className="font-medium text-lg mb-1">
								{setting.key
									.replace(/_/g, " ")
									.replace(/\b\w/g, (c) => c.toUpperCase())}
							</h3>
							{setting.description && (
								<p className="text-sm text-muted-foreground mb-3">
									{setting.description}
								</p>
							)}

							{setting.value_type === "boolean" &&
							editingKey !== setting.key ? (
								<div className="flex items-center gap-4">
									<label className="relative inline-flex items-center cursor-pointer">
										<input
											type="checkbox"
											checked={setting.value === "true"}
											onChange={(e) => {
												updateMutation.mutate({
													key: setting.key,
													value: e.target.checked
														? "true"
														: "false",
												});
											}}
											className="sr-only peer"
										/>
										<div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
										<span className="ml-3 text-sm font-medium">
											{setting.value === "true"
												? "Enabled"
												: "Disabled"}
										</span>
									</label>
								</div>
							) : editingKey === setting.key ? (
								<div className="flex gap-2">
									<input
										type={
											setting.is_sensitive
												? "password"
												: setting.value_type ===
													  "integer"
													? "number"
													: "text"
										}
										value={editValue}
										onChange={(e) =>
											setEditValue(e.target.value)
										}
										className="flex-1 px-3 py-2 border-input bg-background text-foreground border rounded focus:outline-none focus:ring-2 focus:ring-ring"
										placeholder={`Enter ${setting.key}`}
										{...(setting.value_type === "integer"
											? { min: 1, step: 1 }
											: {})}
									/>
									<button
										onClick={() => onSave(setting.key)}
										className="px-4 py-2 bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
										disabled={updateMutation.isPending}
									>
										Save
									</button>
									<button
										onClick={onCancel}
										className="px-4 py-2 bg-secondary text-secondary-foreground rounded hover:opacity-90 cursor-pointer"
									>
										Cancel
									</button>
								</div>
							) : (
								<div className="flex items-center gap-2">
									<code className="flex-1 bg-muted text-muted-foreground px-3 py-2 rounded text-sm">
										{setting.value ||
											"(not set - using default)"}
									</code>
									<button
										onClick={() => onEdit(setting)}
										className="px-4 py-2 bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
									>
										Edit
									</button>
									{setting.value &&
										setting.value !== "***HIDDEN***" && (
											<button
												onClick={() =>
													onReset(setting.key)
												}
												className="px-4 py-2 bg-destructive text-destructive-foreground rounded hover:opacity-90 cursor-pointer"
												disabled={
													deleteMutation.isPending
												}
											>
												Reset
											</button>
										)}
								</div>
							)}
						</div>
					</div>
				</div>
			))}
		</div>
	);
}
