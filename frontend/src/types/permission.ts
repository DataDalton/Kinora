export interface Permission {
  name: string;
  displayName: string;
  description?: string;
  category: string;
}

export interface PermissionGroup {
  id: number;
  name: string;
  displayName: string;
  description?: string;
  color?: string;
  isSystem: boolean;
  priority: number;
  permissions: string[];
  createdAt: string;
  updatedAt: string;
}

export interface PermissionGroupSimple {
  id: number;
  name: string;
  displayName: string;
  color?: string;
}

export interface PermissionGroupCreate {
  name: string;
  displayName: string;
  description?: string;
  color?: string;
  permissionNames: string[];
}

export interface PermissionGroupUpdate {
  displayName?: string;
  description?: string;
  color?: string;
  permissionNames?: string[];
}
