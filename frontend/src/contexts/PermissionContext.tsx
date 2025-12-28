'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import api from '@/lib/api';

interface PermissionGroup {
  id: number;
  name: string;
  displayName: string;
  color?: string;
}

interface UserInfo {
  id: number;
  username: string;
  groups: PermissionGroup[];
}

interface PermissionContextType {
  permissions: Set<string>;
  groups: PermissionGroup[];
  user: UserInfo | null;
  loading: boolean;
  hasPermission: (permission: string) => boolean;
  hasAnyPermission: (...permissions: string[]) => boolean;
  hasAllPermissions: (...permissions: string[]) => boolean;
  canView: (mediaType: string) => boolean;
  canManage: (mediaType: string) => boolean;
  canRequest: (mediaType: string) => boolean;
  canApprove: (mediaType: string) => boolean;
  canDownload: (mediaType: string) => boolean;
  isAdmin: boolean;
  refreshPermissions: () => Promise<void>;
}

const PermissionContext = createContext<PermissionContextType | null>(null);

export function PermissionProvider({ children }: { children: ReactNode }) {
  const [permissions, setPermissions] = useState<Set<string>>(new Set());
  const [groups, setGroups] = useState<PermissionGroup[]>([]);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshPermissions = useCallback(async () => {
    // Check for token before trying to fetch
    const token = typeof document !== 'undefined'
      ? document.cookie.split('; ').find(row => row.startsWith('access_token='))
      : null;

    if (!token) {
      setPermissions(new Set());
      setGroups([]);
      setUser(null);
      setLoading(false);
      return;
    }

    try {
      const response = await api.get('/auth/me');
      const userData = response.data;
      setPermissions(new Set(userData.permissions || []));
      setGroups(userData.groups || []);
      setUser({
        id: userData.id,
        username: userData.username,
        groups: userData.groups || [],
      });
    } catch (error) {
      console.error('Failed to fetch permissions:', error);
      setPermissions(new Set());
      setGroups([]);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshPermissions();

    // Listen for login events to refresh permissions
    const handleLogin = () => {
      setLoading(true);
      refreshPermissions();
    };

    window.addEventListener('auth:login', handleLogin);
    return () => window.removeEventListener('auth:login', handleLogin);
  }, [refreshPermissions]);

  const hasPermission = useCallback((permission: string) => {
    return permissions.has(permission);
  }, [permissions]);

  const hasAnyPermission = useCallback((...perms: string[]) => {
    return perms.some(p => permissions.has(p));
  }, [permissions]);

  const hasAllPermissions = useCallback((...perms: string[]) => {
    return perms.every(p => permissions.has(p));
  }, [permissions]);

  // Media-specific helpers matching our permission system
  const canView = useCallback((mediaType: string) => hasPermission(`${mediaType}.view`), [hasPermission]);
  const canManage = useCallback((mediaType: string) => hasPermission(`${mediaType}.manage`), [hasPermission]);
  const canRequest = useCallback((mediaType: string) => hasPermission(`${mediaType}.request`), [hasPermission]);
  const canApprove = useCallback((mediaType: string) => hasPermission(`${mediaType}.approve`), [hasPermission]);
  const canDownload = useCallback((mediaType: string) => hasPermission(`${mediaType}.download`), [hasPermission]);

  const isAdmin = hasPermission('system.admin');

  return (
    <PermissionContext.Provider value={{
      permissions,
      groups,
      user,
      loading,
      hasPermission,
      hasAnyPermission,
      hasAllPermissions,
      canView,
      canManage,
      canRequest,
      canApprove,
      canDownload,
      isAdmin,
      refreshPermissions,
    }}>
      {children}
    </PermissionContext.Provider>
  );
}

export function usePermissions() {
  const context = useContext(PermissionContext);
  if (!context) {
    throw new Error('usePermissions must be used within a PermissionProvider');
  }
  return context;
}

// Helper component for conditional rendering
interface RequirePermissionProps {
  permission: string | string[];
  mode?: 'any' | 'all';
  children: ReactNode;
  fallback?: ReactNode;
}

export function RequirePermission({
  permission,
  mode = 'any',
  children,
  fallback = null
}: RequirePermissionProps) {
  const { hasPermission, hasAnyPermission, hasAllPermissions, loading } = usePermissions();

  if (loading) return null;

  const perms = Array.isArray(permission) ? permission : [permission];
  const hasAccess = mode === 'all'
    ? hasAllPermissions(...perms)
    : hasAnyPermission(...perms);

  return hasAccess ? <>{children}</> : <>{fallback}</>;
}
