'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import PageHeader from '@/components/PageHeader';
import Toast from '@/components/Toast';
import ConfirmModal from '@/components/ConfirmModal';
import AuthProvidersSection from '@/components/AuthProvidersSection';
import OIDCProvidersManagement from '@/components/OIDCProvidersManagement';
import ForwardAuthSettings from '@/components/ForwardAuthSettings';
import { ChevronDown, ChevronRight } from 'lucide-react';
import RootFoldersSection from '@/components/settings/RootFoldersSection';
import FolderHealthSection from '@/components/settings/FolderHealthSection';

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

interface AppUser {
  id: number;
  username: string;
  is_active: boolean;
  role: string;
  created_at: string;
  updated_at: string;
}

type SettingsSection = 'users' | 'authentication' | 'oidc-providers' | 'forward-auth' | 'download-clients' | 'api-keys' | 'root-folders' | 'folder-health' | 'system';

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [selectedSection, setSelectedSection] = useState<SettingsSection>('users');
  const [editingClientId, setEditingClientId] = useState<number | null>(null);
  const [editingClient, setEditingClient] = useState<Partial<DownloadClient> & { password?: string }>({});
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({
    'auth': true,
    'general': true,
    'storage': true,
  });

  // User management state
  const [showCreateUserModal, setShowCreateUserModal] = useState(false);
  const [showEditUserModal, setShowEditUserModal] = useState(false);
  const [showResetPasswordModal, setShowResetPasswordModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<AppUser | null>(null);
  const [newUserData, setNewUserData] = useState({ username: '', password: '', role: 'user', is_active: true });
  const [editUserData, setEditUserData] = useState({ username: '', role: 'user', is_active: true });
  const [resetPasswordData, setResetPasswordData] = useState({ password: '' });

  // Toast and confirmation state
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  // Helper to show toast and auto-dismiss any existing toast first
  const showToast = (message: string, type: 'success' | 'error' | 'info') => {
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
  }>({ isOpen: false, title: '', message: '', onConfirm: () => {} });

  const { data: settingsGroups, isLoading } = useQuery<SettingsGroup[]>({
    queryKey: ['settings'],
    queryFn: async () => {
      const response = await api.get('/settings');
      return response.data;
    },
  });

  const { data: downloadClients } = useQuery<DownloadClient[]>({
    queryKey: ['settings-download-clients'],
    queryFn: async () => {
      const response = await api.get('/settings/download-clients');
      return response.data;
    },
  });

  const { data: users } = useQuery<AppUser[]>({
    queryKey: ['users'],
    queryFn: async () => {
      const response = await api.get('/users');
      return response.data;
    },
  });

  const initializeDefaultsMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post('/settings/initialize-defaults');
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
  });

  const updateSettingMutation = useMutation({
    mutationFn: async ({ key, value }: { key: string; value: string }) => {
      const response = await api.put(`/settings/${key}`, { value });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      setEditingKey(null);
      setEditValue('');
    },
  });

  const deleteSettingMutation = useMutation({
    mutationFn: async (key: string) => {
      const response = await api.delete(`/settings/${key}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
  });

  const updateDownloadClientMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<DownloadClient> & { password?: string } }) => {
      const response = await api.put(`/settings/download-clients/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings-download-clients'] });
      setEditingClientId(null);
      setEditingClient({});
    },
  });

  const createUserMutation = useMutation({
    mutationFn: async (data: typeof newUserData) => {
      const response = await api.post('/users', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setShowCreateUserModal(false);
      setNewUserData({ username: '', password: '', role: 'user', is_active: true });
      showToast('User created successfully!', 'success');
    },
    onError: (error: any) => {
      const errorMsg = error.response?.data?.detail
        ? (typeof error.response.data.detail === 'string'
          ? error.response.data.detail
          : error.response.data.detail[0]?.msg || 'Validation error')
        : 'Failed to create user';
      showToast(errorMsg, 'error');
    },
  });

  const updateUserMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: typeof editUserData }) => {
      const response = await api.put(`/users/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setShowEditUserModal(false);
      setSelectedUser(null);
      showToast('User updated successfully!', 'success');
    },
    onError: (error: any) => {
      const errorMsg = error.response?.data?.detail
        ? (typeof error.response.data.detail === 'string'
          ? error.response.data.detail
          : error.response.data.detail[0]?.msg || 'Validation error')
        : 'Failed to update user';
      showToast(errorMsg, 'error');
    },
  });

  const deleteUserMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.delete(`/users/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      showToast('User deleted successfully!', 'success');
    },
    onError: (error: any) => {
      const errorMsg = error.response?.data?.detail
        ? (typeof error.response.data.detail === 'string'
          ? error.response.data.detail
          : error.response.data.detail[0]?.msg || 'Validation error')
        : 'Failed to delete user';
      showToast(errorMsg, 'error');
    },
  });

  const resetPasswordMutation = useMutation({
    mutationFn: async ({ id, password }: { id: number; password: string }) => {
      const response = await api.put(`/users/${id}/password`, { password });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setShowResetPasswordModal(false);
      setSelectedUser(null);
      setResetPasswordData({ password: '' });
      showToast('Password reset successfully!', 'success');
    },
    onError: (error: any) => {
      const errorMsg = error.response?.data?.detail
        ? (typeof error.response.data.detail === 'string'
          ? error.response.data.detail
          : error.response.data.detail[0]?.msg || 'Validation error')
        : 'Failed to reset password';
      showToast(errorMsg, 'error');
    },
  });

  const toggleUserActiveMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.put(`/users/${id}/toggle-active`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (error: any) => {
      const errorMsg = error.response?.data?.detail
        ? (typeof error.response.data.detail === 'string'
          ? error.response.data.detail
          : error.response.data.detail[0]?.msg || 'Validation error')
        : 'Failed to toggle user status';
      showToast(errorMsg, 'error');
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
    setEditValue(setting.value || '');
  };

  const handleSave = (key: string) => {
    updateSettingMutation.mutate({ key, value: editValue });
  };

  const handleCancel = () => {
    setEditingKey(null);
    setEditValue('');
  };

  const handleReset = (key: string) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Reset Setting',
      message: 'Reset this setting to default? This action cannot be undone.',
      onConfirm: () => {
        deleteSettingMutation.mutate(key);
        setConfirmDialog({ isOpen: false, title: '', message: '', onConfirm: () => {} });
      }
    });
  };

  const categoryTitles: Record<string, string> = {
    api_keys: 'API Keys',
    general: 'General',
    paths: 'Root Folders',
    system: 'System',
  };

  if (isLoading) {
    return (
      <div className="min-h-screen">
        {/* Header Section */}
        <div className="bg-gradient-to-r from-slate-600/10 via-gray-600/10 to-zinc-600/10 border-b-2 border-border">
          <div className="container mx-auto px-6 py-8">
            <h1 className="text-4xl font-bold mb-2">Settings</h1>
            <p className="text-muted-foreground">Configure your application preferences</p>
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
      role: user.role,
      is_active: user.is_active,
    });
    setShowEditUserModal(true);
  };

  const handleDeleteUser = (user: AppUser) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Delete User',
      message: `Are you sure you want to delete user "${user.username}"? This action cannot be undone.`,
      onConfirm: () => {
        deleteUserMutation.mutate(user.id);
        setConfirmDialog({ isOpen: false, title: '', message: '', onConfirm: () => {} });
      },
    });
  };

  const handleResetPassword = (user: AppUser) => {
    setSelectedUser(user);
    setResetPasswordData({ password: '' });
    setShowResetPasswordModal(true);
  };

  const toggleCategory = (categoryId: string) => {
    setExpandedCategories(prev => ({
      ...prev,
      [categoryId]: !prev[categoryId]
    }));
  };

  const categories = [
    {
      id: 'auth',
      name: 'Authentication & Security',
      sections: [
        { id: 'users' as SettingsSection, name: 'User Management', count: users?.length || 0 },
        { id: 'authentication' as SettingsSection, name: 'Linked Providers', count: 0 },
        { id: 'oidc-providers' as SettingsSection, name: 'OIDC Providers', count: 0 },
        { id: 'forward-auth' as SettingsSection, name: 'Forward Auth', count: 0 },
      ]
    },
    {
      id: 'general',
      name: 'General Settings',
      sections: [
        { id: 'download-clients' as SettingsSection, name: 'Download Clients', count: downloadClients?.length || 0 },
        { id: 'api-keys' as SettingsSection, name: 'API Keys', count: settingsGroups?.find(g => g.category === 'api_keys')?.settings.length || 0 },
        { id: 'system' as SettingsSection, name: 'System', count: settingsGroups?.find(g => g.category === 'system')?.settings.length || 0 },
      ]
    },
    {
      id: 'storage',
      name: 'Storage & Folders',
      sections: [
        { id: 'root-folders' as SettingsSection, name: 'Root Folders', count: 0 },
        { id: 'folder-health' as SettingsSection, name: 'Folder Health', count: 0 },
      ]
    }
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
                      const isActive = selectedSection === section.id;

                      return (
                        <button
                          key={section.id}
                          onClick={() => setSelectedSection(section.id)}
                          className={`w-full flex items-center justify-between px-3 py-2 rounded-lg transition-colors cursor-pointer ${
                            isActive
                              ? 'bg-primary text-primary-foreground'
                              : 'hover:bg-accent'
                          }`}
                        >
                          <span className="text-sm font-medium">{section.name}</span>
                          {section.count > 0 && (
                            <span className={`text-xs px-2 py-1 rounded-full ${
                              isActive
                                ? 'bg-primary-foreground/20'
                                : 'bg-muted'
                            }`}>
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
          {selectedSection === 'users' && (
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
                    <h2 className="text-xl font-bold">Users</h2>
                    <button
                      onClick={() => setShowCreateUserModal(true)}
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
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Username</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Role</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Status</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Created</th>
                            <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          {users.map((user) => (
                            <tr key={user.id} className="hover:bg-muted/30">
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="font-medium">{user.username}</div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                                  user.role === 'administrator'
                                    ? 'bg-primary text-primary-foreground'
                                    : 'bg-muted text-foreground'
                                }`}>
                                  {user.role}
                                </span>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <button
                                  onClick={() => toggleUserActiveMutation.mutate(user.id)}
                                  className="cursor-pointer"
                                >
                                  <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                                    user.is_active
                                      ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                      : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                                  }`}>
                                    {user.is_active ? 'Active' : 'Inactive'}
                                  </span>
                                </button>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                                {new Date(user.created_at).toLocaleDateString()}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                                <div className="flex items-center justify-end gap-2">
                                  <button
                                    onClick={() => handleEditUser(user)}
                                    className="px-3 py-1 bg-primary text-primary-foreground rounded hover:opacity-90 transition cursor-pointer"
                                  >
                                    Edit
                                  </button>
                                  <button
                                    onClick={() => handleResetPassword(user)}
                                    className="px-3 py-1 bg-blue-600 text-white rounded hover:opacity-90 transition cursor-pointer"
                                  >
                                    Reset Password
                                  </button>
                                  <button
                                    onClick={() => handleDeleteUser(user)}
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

          {/* Authentication Section */}
          {selectedSection === 'authentication' && (
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
          {selectedSection === 'oidc-providers' && (
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
          {selectedSection === 'forward-auth' && (
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
          {selectedSection === 'download-clients' && (
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
                {downloadClients && downloadClients.length > 0 ? (
            <div className="space-y-4">
              {downloadClients.map((client) => (
                <div
                  key={client.id}
                  className="bg-card text-card-foreground border-border border rounded-lg p-4 shadow-sm"
                >
                  {editingClientId === client.id ? (
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium mb-1">Name</label>
                          <input
                            type="text"
                            value={editingClient.name || ''}
                            onChange={(e) => setEditingClient({ ...editingClient, name: e.target.value })}
                            className="w-full px-3 py-2 border border-border rounded-md bg-background"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-1">Host</label>
                          <input
                            type="text"
                            value={editingClient.host || ''}
                            onChange={(e) => setEditingClient({ ...editingClient, host: e.target.value })}
                            className="w-full px-3 py-2 border border-border rounded-md bg-background"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-1">Port</label>
                          <input
                            type="number"
                            value={editingClient.port || ''}
                            onChange={(e) => setEditingClient({ ...editingClient, port: parseInt(e.target.value) })}
                            className="w-full px-3 py-2 border border-border rounded-md bg-background"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-1">Username</label>
                          <input
                            type="text"
                            value={editingClient.username || ''}
                            onChange={(e) => setEditingClient({ ...editingClient, username: e.target.value })}
                            className="w-full px-3 py-2 border border-border rounded-md bg-background"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-1">Password (leave blank to keep current)</label>
                          <input
                            type="password"
                            value={editingClient.password || ''}
                            onChange={(e) => setEditingClient({ ...editingClient, password: e.target.value })}
                            placeholder="********"
                            className="w-full px-3 py-2 border border-border rounded-md bg-background"
                          />
                        </div>
                        <div className="col-span-2 space-y-3">
                          <label className="flex items-center justify-between p-3 bg-muted/50 rounded-md cursor-pointer">
                            <span className="text-sm font-medium">Use SSL</span>
                            <div className="relative inline-flex items-center">
                              <input
                                type="checkbox"
                                checked={editingClient.use_ssl || false}
                                onChange={(e) => setEditingClient({ ...editingClient, use_ssl: e.target.checked })}
                                className="sr-only peer"
                              />
                              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
                            </div>
                          </label>
                          <label className="flex items-center justify-between p-3 bg-muted/50 rounded-md cursor-pointer">
                            <span className="text-sm font-medium">Enabled</span>
                            <div className="relative inline-flex items-center">
                              <input
                                type="checkbox"
                                checked={editingClient.is_enabled || false}
                                onChange={(e) => setEditingClient({ ...editingClient, is_enabled: e.target.checked })}
                                className="sr-only peer"
                              />
                              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
                            </div>
                          </label>
                          <label className="flex items-center justify-between p-3 bg-muted/50 rounded-md cursor-pointer">
                            <span className="text-sm font-medium">Set as Default</span>
                            <div className="relative inline-flex items-center">
                              <input
                                type="checkbox"
                                checked={editingClient.is_default || false}
                                onChange={(e) => setEditingClient({ ...editingClient, is_default: e.target.checked })}
                                className="sr-only peer"
                              />
                              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
                            </div>
                          </label>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleSaveClient(client.id)}
                          className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 cursor-pointer"
                        >
                          Save
                        </button>
                        <button
                          onClick={handleCancelClientEdit}
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
                          <h3 className="font-medium text-lg">{client.name}</h3>
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
                            <span className="text-muted-foreground">Type:</span>
                            <span className="ml-2 font-medium">{client.client_type}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Host:</span>
                            <span className="ml-2 font-mono text-sm">
                              {client.use_ssl ? 'https://' : 'http://'}{client.host}:{client.port}
                            </span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Username:</span>
                            <span className="ml-2 font-medium">{client.username}</span>
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => handleEditClient(client)}
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
          {selectedSection === 'api-keys' && (
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
                {settingsGroups?.find(g => g.category === 'api_keys') && (
                  <SettingsGroupSection
                    group={settingsGroups.find(g => g.category === 'api_keys')!}
                    editingKey={editingKey}
                    editValue={editValue}
                    onEdit={handleEdit}
                    onSave={handleSave}
                    onCancel={handleCancel}
                    onReset={handleReset}
                    setEditValue={setEditValue}
                    updateMutation={updateSettingMutation}
                    deleteMutation={deleteSettingMutation}
                  />
                )}
                </div>
              </div>
            </div>
          )}

          {/* System Section */}
          {selectedSection === 'system' && (
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
                {settingsGroups?.find(g => g.category === 'system') && (
                  <SettingsGroupSection
                    group={settingsGroups.find(g => g.category === 'system')!}
                    editingKey={editingKey}
                    editValue={editValue}
                    onEdit={handleEdit}
                    onSave={handleSave}
                    onCancel={handleCancel}
                    onReset={handleReset}
                    setEditValue={setEditValue}
                    updateMutation={updateSettingMutation}
                    deleteMutation={deleteSettingMutation}
                  />
                )}
                </div>
              </div>
            </div>
          )}

          {/* Root Folders Section */}
          {selectedSection === 'root-folders' && (
            <RootFoldersSection />
          )}

          {/* Folder Health Section */}
          {selectedSection === 'folder-health' && (
            <FolderHealthSection />
          )}
        </div>
      </div>

      {/* Create User Modal */}
      {showCreateUserModal && (
        <div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-50 flex items-center justify-center p-4">
          <div className="bg-background rounded-lg max-w-md w-full border border-border shadow-2xl p-6">
            <h2 className="text-2xl font-bold mb-4">Create New User</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Username</label>
                <input
                  type="text"
                  value={newUserData.username}
                  onChange={(e) => setNewUserData({ ...newUserData, username: e.target.value })}
                  className="w-full px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
                  placeholder="Enter username"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Password</label>
                <input
                  type="password"
                  value={newUserData.password}
                  onChange={(e) => setNewUserData({ ...newUserData, password: e.target.value })}
                  className="w-full px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
                  placeholder="Enter password (min 8 characters)"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Role</label>
                <select
                  value={newUserData.role}
                  onChange={(e) => setNewUserData({ ...newUserData, role: e.target.value })}
                  className="w-full px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary cursor-pointer"
                >
                  <option value="user">User</option>
                  <option value="administrator">Administrator</option>
                </select>
              </div>
              <label className="flex items-center justify-between p-3 bg-muted/50 rounded-lg cursor-pointer">
                <div>
                  <div className="font-semibold">Active</div>
                  <div className="text-xs text-muted-foreground">User can log in and access the system</div>
                </div>
                <div className="relative inline-flex items-center">
                  <input
                    type="checkbox"
                    checked={newUserData.is_active}
                    onChange={(e) => setNewUserData({ ...newUserData, is_active: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
                </div>
              </label>
              <div className="flex gap-3 pt-4">
                <button
                  onClick={() => createUserMutation.mutate(newUserData)}
                  disabled={createUserMutation.isPending || !newUserData.username || !newUserData.password}
                  className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer transition"
                >
                  {createUserMutation.isPending ? 'Creating...' : 'Create User'}
                </button>
                <button
                  onClick={() => {
                    setShowCreateUserModal(false);
                    setNewUserData({ username: '', password: '', role: 'user', is_active: true });
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
          <div className="bg-background rounded-lg max-w-md w-full border border-border shadow-2xl p-6">
            <h2 className="text-2xl font-bold mb-4">Edit User: {selectedUser.username}</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Username</label>
                <input
                  type="text"
                  value={editUserData.username}
                  onChange={(e) => setEditUserData({ ...editUserData, username: e.target.value })}
                  className="w-full px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
                  placeholder="Enter username"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Role</label>
                <select
                  value={editUserData.role}
                  onChange={(e) => setEditUserData({ ...editUserData, role: e.target.value })}
                  className="w-full px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary cursor-pointer"
                >
                  <option value="user">User</option>
                  <option value="administrator">Administrator</option>
                </select>
              </div>
              <label className="flex items-center justify-between p-3 bg-muted/50 rounded-lg cursor-pointer">
                <div>
                  <div className="font-semibold">Active</div>
                  <div className="text-xs text-muted-foreground">User can log in and access the system</div>
                </div>
                <div className="relative inline-flex items-center">
                  <input
                    type="checkbox"
                    checked={editUserData.is_active}
                    onChange={(e) => setEditUserData({ ...editUserData, is_active: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
                </div>
              </label>
              <div className="flex gap-3 pt-4">
                <button
                  onClick={() => updateUserMutation.mutate({ id: selectedUser.id, data: editUserData })}
                  disabled={updateUserMutation.isPending || !editUserData.username}
                  className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer transition"
                >
                  {updateUserMutation.isPending ? 'Updating...' : 'Update User'}
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
            <h2 className="text-2xl font-bold mb-4">Reset Password: {selectedUser.username}</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">New Password</label>
                <input
                  type="password"
                  value={resetPasswordData.password}
                  onChange={(e) => setResetPasswordData({ password: e.target.value })}
                  className="w-full px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
                  placeholder="Enter new password (min 8 characters)"
                />
              </div>
              <div className="flex gap-3 pt-4">
                <button
                  onClick={() => resetPasswordMutation.mutate({ id: selectedUser.id, password: resetPasswordData.password })}
                  disabled={resetPasswordMutation.isPending || !resetPasswordData.password || resetPasswordData.password.length < 8}
                  className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer transition"
                >
                  {resetPasswordMutation.isPending ? 'Resetting...' : 'Reset Password'}
                </button>
                <button
                  onClick={() => {
                    setShowResetPasswordModal(false);
                    setSelectedUser(null);
                    setResetPasswordData({ password: '' });
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

      {/* Confirm Dialog */}
      <ConfirmModal
        isOpen={confirmDialog.isOpen}
        title={confirmDialog.title}
        message={confirmDialog.message}
        confirmText="Delete"
        cancelText="Cancel"
        variant="danger"
        onConfirm={confirmDialog.onConfirm}
        onCancel={() => setConfirmDialog({ isOpen: false, title: '', message: '', onConfirm: () => {} })}
      />

      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-4 right-4 z-[70]">
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
                {setting.key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
              </h3>
              {setting.description && (
                <p className="text-sm text-muted-foreground mb-3">{setting.description}</p>
              )}

              {setting.value_type === 'boolean' && editingKey !== setting.key ? (
                <div className="flex items-center gap-4">
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={setting.value === 'true'}
                      onChange={(e) => {
                        updateMutation.mutate({
                          key: setting.key,
                          value: e.target.checked ? 'true' : 'false'
                        });
                      }}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
                    <span className="ml-3 text-sm font-medium">
                      {setting.value === 'true' ? 'Enabled' : 'Disabled'}
                    </span>
                  </label>
                </div>
              ) : editingKey === setting.key ? (
                <div className="flex gap-2">
                  <input
                    type={setting.is_sensitive ? 'password' : setting.value_type === 'integer' ? 'number' : 'text'}
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    className="flex-1 px-3 py-2 border-input bg-background text-foreground border rounded focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder={`Enter ${setting.key}`}
                    {...(setting.value_type === 'integer' ? { min: 1, step: 1 } : {})}
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
                    {setting.value || '(not set - using default)'}
                  </code>
                  <button
                    onClick={() => onEdit(setting)}
                    className="px-4 py-2 bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
                  >
                    Edit
                  </button>
                  {setting.value && setting.value !== '***HIDDEN***' && (
                    <button
                      onClick={() => onReset(setting.key)}
                      className="px-4 py-2 bg-destructive text-destructive-foreground rounded hover:opacity-90 cursor-pointer"
                      disabled={deleteMutation.isPending}
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
