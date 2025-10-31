'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import PageHeader from '@/components/PageHeader';

interface Setting {
  key: string;
  value: string | null;
  category: string;
  description: string | null;
  is_sensitive: boolean;
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

type SettingsSection = 'download-clients' | 'api-keys' | 'paths' | 'system';

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [selectedSection, setSelectedSection] = useState<SettingsSection>('download-clients');

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
    if (confirm('Reset this setting to default?')) {
      deleteSettingMutation.mutate(key);
    }
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

  const sections = [
    { id: 'download-clients' as SettingsSection, name: 'Download Clients', count: downloadClients?.length || 0 },
    { id: 'api-keys' as SettingsSection, name: 'API Keys', count: settingsGroups?.find(g => g.category === 'api_keys')?.settings.length || 0 },
    { id: 'paths' as SettingsSection, name: 'Root Folders', count: settingsGroups?.find(g => g.category === 'paths')?.settings.length || 0 },
    { id: 'system' as SettingsSection, name: 'System', count: settingsGroups?.find(g => g.category === 'system')?.settings.length || 0 },
  ];

  return (
    <div className="min-h-screen bg-background">
      <div className="flex">
        {/* Left Navigation */}
        <div className="w-64 bg-card border-r border-border p-6 min-h-screen">
          <h2 className="text-xl font-bold mb-6">Settings</h2>
          <nav className="space-y-2">
            {sections.map((section) => {
              const isActive = selectedSection === section.id;

              return (
                <button
                  key={section.id}
                  onClick={() => setSelectedSection(section.id)}
                  className={`w-full flex items-center justify-between px-4 py-3 rounded-lg transition-colors ${
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
          </nav>
        </div>

        {/* Main Content */}
        <div className="flex-1">
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
                  </div>
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

          {/* Root Folders Section */}
          {selectedSection === 'paths' && (
            <div>
              <PageHeader
                title="Root Folders"
                description="Configure where your media files are organized"
                gradientFrom="yellow-600/10"
                gradientVia="orange-600/10"
                gradientTo="red-600/10"
              />
              <div className="p-8">
                <div className="max-w-6xl mx-auto">
                {settingsGroups?.find(g => g.category === 'paths') && (
                  <SettingsGroupSection
                    group={settingsGroups.find(g => g.category === 'paths')!}
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
        </div>
      </div>
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

              {editingKey === setting.key ? (
                <div className="flex gap-2">
                  <input
                    type={setting.is_sensitive ? 'password' : 'text'}
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    className="flex-1 px-3 py-2 border-input bg-background text-foreground border rounded focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder={`Enter ${setting.key}`}
                  />
                  <button
                    onClick={() => onSave(setting.key)}
                    className="px-4 py-2 bg-primary text-primary-foreground rounded hover:opacity-90"
                    disabled={updateMutation.isPending}
                  >
                    Save
                  </button>
                  <button
                    onClick={onCancel}
                    className="px-4 py-2 bg-secondary text-secondary-foreground rounded hover:opacity-90"
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
                    className="px-4 py-2 bg-primary text-primary-foreground rounded hover:opacity-90"
                  >
                    Edit
                  </button>
                  {setting.value && setting.value !== '***HIDDEN***' && (
                    <button
                      onClick={() => onReset(setting.key)}
                      className="px-4 py-2 bg-destructive text-destructive-foreground rounded hover:opacity-90"
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
