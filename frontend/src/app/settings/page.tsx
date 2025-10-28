'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

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

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  const { data: settingsGroups, isLoading } = useQuery<SettingsGroup[]>({
    queryKey: ['settings'],
    queryFn: async () => {
      const response = await api.get('/settings');
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

  return (
    <div className="min-h-screen">
      {/* Header Section */}
      <div className="bg-gradient-to-r from-slate-600/10 via-gray-600/10 to-zinc-600/10 border-b-2 border-border">
        <div className="container mx-auto px-6 py-8">
          <div className="flex justify-between items-start mb-2">
            <div>
              <h1 className="text-4xl font-bold mb-2">Settings</h1>
              <p className="text-muted-foreground">Configure your application preferences</p>
            </div>
            {settingsGroups && settingsGroups.length > 0 && (
              <button
                onClick={() => initializeDefaultsMutation.mutate()}
                className="px-4 py-2 bg-primary text-primary-foreground rounded hover:opacity-90"
                disabled={initializeDefaultsMutation.isPending}
              >
                Initialize Defaults
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Content Section */}
      <div className="container mx-auto px-6 py-8">
        {settingsGroups && settingsGroups.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24">
            <div className="text-center max-w-md">
              <div className="text-6xl mb-6">⚙️</div>
              <h2 className="text-2xl font-bold mb-3">No Settings Yet</h2>
              <p className="text-muted-foreground mb-8">
                Initialize default settings to configure API keys and other application preferences.
              </p>
              <button
                onClick={() => initializeDefaultsMutation.mutate()}
                className="px-8 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 font-medium shadow-md cursor-pointer text-lg"
                disabled={initializeDefaultsMutation.isPending}
              >
                {initializeDefaultsMutation.isPending ? 'Initializing...' : 'Initialize Default Settings'}
              </button>
            </div>
          </div>
        ) : null}

        {settingsGroups?.map((group) => (
          <div key={group.category} className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 border-b pb-2">
              {categoryTitles[group.category] || group.category}
            </h2>

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
                            onClick={() => handleSave(setting.key)}
                            className="px-4 py-2 bg-primary text-primary-foreground rounded hover:opacity-90"
                            disabled={updateSettingMutation.isPending}
                          >
                            Save
                          </button>
                          <button
                            onClick={handleCancel}
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
                            onClick={() => handleEdit(setting)}
                            className="px-4 py-2 bg-primary text-primary-foreground rounded hover:opacity-90"
                          >
                            Edit
                          </button>
                          {setting.value && (
                            <button
                              onClick={() => handleReset(setting.key)}
                              className="px-4 py-2 bg-destructive text-destructive-foreground rounded hover:opacity-90"
                              disabled={deleteSettingMutation.isPending}
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
          </div>
        ))}
      </div>
    </div>
  );
}
