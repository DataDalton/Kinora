'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import PageHeader from '@/components/PageHeader';
import Toast from '@/components/Toast';
import ConfirmModal from '@/components/ConfirmModal';
import {
  getRootFolders,
  createRootFolder,
  updateRootFolder,
  deleteRootFolder,
  testRootFolder,
  testFolderPaths,
  getSelectionSettings,
  updateSelectionSettings,
  browseDirectory,
} from '@/lib/api/root-folders';
import type {
  RootFolder,
  MediaType,
  SelectionMode,
  CreateRootFolderRequest,
  UpdateRootFolderRequest,
  BrowseDirectoryResponse,
  FolderTestResult,
} from '@/types/root-folder';
import {
  FolderOpen,
  Plus,
  Trash2,
  HardDrive,
  AlertCircle,
  CheckCircle,
  AlertTriangle,
  Settings2,
  ChevronRight,
  ChevronUp,
  RefreshCw,
  Link,
  X,
  Loader2,
  ArrowUp,
  ArrowDown,
} from 'lucide-react';

const mediaTypes: { id: MediaType; name: string; color: string }[] = [
  { id: 'movies', name: 'Movies', color: 'bg-blue-500' },
  { id: 'shows', name: 'TV Shows', color: 'bg-purple-500' },
  { id: 'anime', name: 'Anime', color: 'bg-pink-500' },
  { id: 'music', name: 'Music', color: 'bg-green-500' },
];

const selectionModes: { id: SelectionMode; name: string; description: string }[] = [
  {
    id: 'most_free_space',
    name: 'Most Free Space',
    description: 'Always use the folder with most available space. Simple and automatic.',
  },
  {
    id: 'priority',
    name: 'Priority Order',
    description: 'Fill folders in your defined order (1→2→3). Skips folders over threshold. Use when you want control over which drives fill first.',
  },
  {
    id: 'fill_threshold',
    name: 'Fill Threshold',
    description: 'Among folders under threshold, always picks most free space. Spreads content evenly across drives.',
  },
];

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return 'Unknown';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

function getHealthStatusIcon(status: string) {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="w-5 h-5 text-green-500" />;
    case 'warning':
      return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
    case 'error':
      return <AlertCircle className="w-5 h-5 text-red-500" />;
    default:
      return <AlertCircle className="w-5 h-5 text-gray-400" />;
  }
}

function getUsageColor(percent: number | null): string {
  if (percent === null) return 'bg-gray-300';
  if (percent >= 90) return 'bg-red-500';
  if (percent >= 75) return 'bg-yellow-500';
  return 'bg-green-500';
}

export default function RootFoldersPage() {
  const queryClient = useQueryClient();
  const [selectedMediaType, setSelectedMediaType] = useState<MediaType>('movies');
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingFolder, setEditingFolder] = useState<RootFolder | null>(null);
  const [showBrowseModal, setShowBrowseModal] = useState(false);
  const [browseTarget, setBrowseTarget] = useState<'root' | 'download'>('root');
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({ isOpen: false, title: '', message: '', onConfirm: () => {} });

  // Form state for add/edit
  const [formData, setFormData] = useState<Partial<CreateRootFolderRequest>>({
    name: '',
    rootPath: '',
    downloadPath: '',
    priority: 0,
    fillThresholdPercent: undefined,
    fillThresholdGb: undefined,
  });

  // Browse state
  const [currentBrowsePath, setCurrentBrowsePath] = useState<string>('');

  // Path test state for modal
  const [pathTestStatus, setPathTestStatus] = useState<{
    testing: boolean;
    result: FolderTestResult | null;
  }>({ testing: false, result: null });
  const testTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Test paths when they change in the modal
  const testPaths = useCallback(async (rootPath: string, downloadPath: string) => {
    if (!rootPath || !downloadPath) {
      setPathTestStatus({ testing: false, result: null });
      return;
    }

    setPathTestStatus({ testing: true, result: null });

    try {
      const result = await testFolderPaths(rootPath, downloadPath);
      setPathTestStatus({ testing: false, result });
    } catch {
      setPathTestStatus({
        testing: false,
        result: {
          success: false,
          rootPathAccessible: false,
          rootPathWritable: false,
          downloadPathAccessible: false,
          downloadPathWritable: false,
          sameFilesystem: false,
          hardlinkSupported: false,
          message: 'Failed to test folder configuration',
        },
      });
    }
  }, []);

  // Debounced path testing
  useEffect(() => {
    if (!showAddModal && !editingFolder) {
      setPathTestStatus({ testing: false, result: null });
      return;
    }

    if (testTimeoutRef.current) {
      clearTimeout(testTimeoutRef.current);
    }

    testTimeoutRef.current = setTimeout(() => {
      testPaths(formData.rootPath || '', formData.downloadPath || '');
    }, 500);

    return () => {
      if (testTimeoutRef.current) {
        clearTimeout(testTimeoutRef.current);
      }
    };
  }, [formData.rootPath, formData.downloadPath, showAddModal, editingFolder, testPaths]);

  const showToast = (message: string, type: 'success' | 'error' | 'info') => {
    setToast(null);
    setTimeout(() => setToast({ message, type }), 0);
  };

  // Queries
  const { data: folders = [], isLoading: foldersLoading } = useQuery({
    queryKey: ['root-folders', selectedMediaType],
    queryFn: () => getRootFolders(selectedMediaType),
  });

  const { data: selectionSettings } = useQuery({
    queryKey: ['selection-settings', selectedMediaType],
    queryFn: () => getSelectionSettings(selectedMediaType),
  });

  const { data: browseData } = useQuery({
    queryKey: ['browse-directory', currentBrowsePath],
    queryFn: () => browseDirectory(currentBrowsePath || undefined),
    enabled: showBrowseModal,
  });

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: CreateRootFolderRequest) => createRootFolder(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['root-folders'] });
      setShowAddModal(false);
      resetForm();
      showToast('Folder created successfully', 'success');
    },
    onError: (error: Error) => {
      showToast(error.message || 'Failed to create folder', 'error');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateRootFolderRequest }) =>
      updateRootFolder(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['root-folders'] });
      setEditingFolder(null);
      resetForm();
      showToast('Folder updated successfully', 'success');
    },
    onError: (error: Error) => {
      showToast(error.message || 'Failed to update folder', 'error');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteRootFolder(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['root-folders'] });
      showToast('Folder deleted successfully', 'success');
    },
    onError: (error: Error) => {
      showToast(error.message || 'Failed to delete folder', 'error');
    },
  });

  const updateSettingsMutation = useMutation({
    mutationFn: ({ mediaType, mode }: { mediaType: MediaType; mode: SelectionMode }) =>
      updateSelectionSettings(mediaType, mode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['selection-settings'] });
      showToast('Selection mode updated', 'success');
    },
    onError: (error: Error) => {
      showToast(error.message || 'Failed to update selection mode', 'error');
    },
  });

  const testMutation = useMutation({
    mutationFn: (id: number) => testRootFolder(id),
    onSuccess: (result) => {
      if (result.success) {
        showToast('Folder test passed', 'success');
      } else {
        showToast(result.message || 'Folder test failed', 'error');
      }
      queryClient.invalidateQueries({ queryKey: ['root-folders'] });
    },
    onError: (error: Error) => {
      showToast(error.message || 'Failed to test folder', 'error');
    },
  });

  // Move folder up or down in priority order
  const handleMovePriority = async (folderId: number, direction: 'up' | 'down') => {
    const currentIndex = folders.findIndex(f => f.id === folderId);
    if (currentIndex === -1) return;

    const swapIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1;
    if (swapIndex < 0 || swapIndex >= folders.length) return;

    const currentFolder = folders[currentIndex];
    const swapFolder = folders[swapIndex];

    // Swap priorities
    try {
      await Promise.all([
        updateRootFolder(currentFolder.id, { priority: swapFolder.priority }),
        updateRootFolder(swapFolder.id, { priority: currentFolder.priority }),
      ]);
      queryClient.invalidateQueries({ queryKey: ['root-folders'] });
    } catch {
      showToast('Failed to update priority', 'error');
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      rootPath: '',
      downloadPath: '',
      priority: 0,
      fillThresholdPercent: undefined,
      fillThresholdGb: undefined,
    });
    setPathTestStatus({ testing: false, result: null });
  };

  const handleAddFolder = () => {
    resetForm();
    setShowAddModal(true);
  };

  const handleEditFolder = (folder: RootFolder) => {
    setFormData({
      name: folder.name,
      rootPath: folder.rootPath,
      downloadPath: folder.downloadPath,
      priority: folder.priority,
      fillThresholdPercent: folder.fillThresholdPercent || undefined,
      fillThresholdGb: folder.fillThresholdGb || undefined,
    });
    setEditingFolder(folder);
  };

  const handleSaveFolder = () => {
    if (editingFolder) {
      updateMutation.mutate({
        id: editingFolder.id,
        data: {
          name: formData.name,
          rootPath: formData.rootPath,
          downloadPath: formData.downloadPath,
          priority: formData.priority,
          fillThresholdPercent: formData.fillThresholdPercent,
          fillThresholdGb: formData.fillThresholdGb,
        },
      });
    } else {
      createMutation.mutate({
        mediaType: selectedMediaType,
        name: formData.name || '',
        rootPath: formData.rootPath || '',
        downloadPath: formData.downloadPath,
        priority: formData.priority,
        fillThresholdPercent: formData.fillThresholdPercent,
        fillThresholdGb: formData.fillThresholdGb,
      });
    }
  };

  const handleDeleteFolder = (folder: RootFolder) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Folder',
      message: `Are you sure you want to delete "${folder.name}"? This cannot be undone.`,
      onConfirm: () => {
        deleteMutation.mutate(folder.id);
        setConfirmDialog({ isOpen: false, title: '', message: '', onConfirm: () => {} });
      },
    });
  };

  const handleBrowse = (target: 'root' | 'download') => {
    setBrowseTarget(target);
    setCurrentBrowsePath(target === 'root' ? formData.rootPath || '' : formData.downloadPath || '');
    setShowBrowseModal(true);
  };

  const handleSelectPath = (path: string) => {
    if (browseTarget === 'root') {
      setFormData({ ...formData, rootPath: path });
    } else {
      setFormData({ ...formData, downloadPath: path });
    }
    setShowBrowseModal(false);
  };

  const handleNavigateBrowse = (dir: string) => {
    if (browseData?.path) {
      // Navigate to subdirectory
      const newPath = browseData.path.endsWith('\\') || browseData.path.endsWith('/')
        ? `${browseData.path}${dir}`
        : `${browseData.path}/${dir}`;
      setCurrentBrowsePath(newPath);
    } else {
      // At root, navigate to drive
      setCurrentBrowsePath(dir);
    }
  };

  const handleBrowseUp = () => {
    if (browseData?.parent) {
      setCurrentBrowsePath(browseData.parent);
    } else {
      setCurrentBrowsePath('');
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <PageHeader
        title="Root Folders"
        description="Configure where your media files are stored and organized"
        gradientFrom="yellow-600/10"
        gradientVia="orange-600/10"
        gradientTo="red-600/10"
      />

      <div className="container mx-auto px-6 py-8">
        <div className="max-w-6xl mx-auto">
          {/* Media Type Tabs */}
          <div className="flex gap-2 mb-6">
            {mediaTypes.map((type) => (
              <button
                key={type.id}
                onClick={() => setSelectedMediaType(type.id)}
                className={`px-4 py-2 rounded-lg font-medium transition-colors cursor-pointer ${
                  selectedMediaType === type.id
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted hover:bg-muted/80 text-foreground'
                }`}
              >
                {type.name}
              </button>
            ))}
          </div>

          {/* Selection Mode */}
          <div className="bg-card border border-border rounded-lg p-4 mb-6">
            <div className="flex items-center gap-2 mb-3">
              <Settings2 className="w-5 h-5 text-muted-foreground" />
              <h3 className="font-medium">Folder Selection Mode</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {selectionModes.map((mode) => (
                <button
                  key={mode.id}
                  onClick={() =>
                    updateSettingsMutation.mutate({
                      mediaType: selectedMediaType,
                      mode: mode.id,
                    })
                  }
                  className={`p-3 rounded-lg border text-left transition-colors cursor-pointer ${
                    selectionSettings?.selectionMode === mode.id
                      ? 'border-primary bg-primary/10'
                      : 'border-border hover:bg-muted/50'
                  }`}
                >
                  <div className="font-medium text-sm">{mode.name}</div>
                  <div className="text-xs text-muted-foreground mt-1">{mode.description}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Folders List */}
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold">
              {mediaTypes.find((t) => t.id === selectedMediaType)?.name} Folders
            </h2>
            <button
              onClick={handleAddFolder}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              Add Folder
            </button>
          </div>

          {foldersLoading ? (
            <div className="text-center py-12 text-muted-foreground">Loading folders...</div>
          ) : folders.length === 0 ? (
            <div className="text-center py-12 bg-card border border-border rounded-lg">
              <FolderOpen className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground mb-4">No folders configured for {selectedMediaType}</p>
              <button
                onClick={handleAddFolder}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition cursor-pointer"
              >
                Add First Folder
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {folders.map((folder, index) => (
                <div
                  key={folder.id}
                  className="bg-card border border-border rounded-lg p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between gap-4">
                    {/* Priority Reorder Controls */}
                    {selectionSettings?.selectionMode === 'priority' && folders.length > 1 && (
                      <div className="flex flex-col items-center gap-1 py-1">
                        <button
                          onClick={() => handleMovePriority(folder.id, 'up')}
                          disabled={index === 0}
                          className="p-1 rounded hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition"
                          title="Move up in priority"
                        >
                          <ArrowUp className="w-4 h-4" />
                        </button>
                        <span className="text-xs font-medium text-muted-foreground w-5 text-center">
                          {index + 1}
                        </span>
                        <button
                          onClick={() => handleMovePriority(folder.id, 'down')}
                          disabled={index === folders.length - 1}
                          className="p-1 rounded hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition"
                          title="Move down in priority"
                        >
                          <ArrowDown className="w-4 h-4" />
                        </button>
                      </div>
                    )}

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-medium text-lg truncate">{folder.name}</h3>
                        {getHealthStatusIcon(folder.healthStatus)}
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm mb-3">
                        <div>
                          <span className="text-muted-foreground">Root Path:</span>
                          <code className="ml-2 text-xs bg-muted px-2 py-1 rounded">{folder.rootPath}</code>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Download Path:</span>
                          <code className="ml-2 text-xs bg-muted px-2 py-1 rounded">{folder.downloadPath}</code>
                        </div>
                      </div>

                      {/* Disk Usage Bar */}
                      <div className="flex items-center gap-4">
                        <div className="flex-1">
                          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                            <span>{formatBytes(folder.usedSpaceBytes)} used</span>
                            <span>{formatBytes(folder.freeSpaceBytes)} free</span>
                          </div>
                          <div className="h-2 bg-muted rounded-full overflow-hidden">
                            <div
                              className={`h-full ${getUsageColor(folder.usedPercent)} transition-all`}
                              style={{ width: `${folder.usedPercent || 0}%` }}
                            />
                          </div>
                          <div className="text-xs text-muted-foreground mt-1">
                            {formatBytes(folder.totalSpaceBytes)} total
                          </div>
                        </div>
                        <div className="flex items-center gap-1 text-xs text-muted-foreground">
                          <HardDrive className="w-4 h-4" />
                          {folder.usedPercent?.toFixed(1)}%
                        </div>
                      </div>

                      {folder.healthMessage && folder.healthStatus !== 'healthy' && (
                        <div className="mt-2 text-sm text-yellow-600 dark:text-yellow-400">
                          {folder.healthMessage}
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex flex-col gap-2">
                      <button
                        onClick={() => handleEditFolder(folder)}
                        className="px-3 py-1.5 text-sm bg-muted hover:bg-muted/80 rounded transition cursor-pointer"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => testMutation.mutate(folder.id)}
                        disabled={testMutation.isPending}
                        className="px-3 py-1.5 text-sm bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200 hover:opacity-80 rounded transition cursor-pointer flex items-center gap-1"
                      >
                        <RefreshCw className={`w-3 h-3 ${testMutation.isPending ? 'animate-spin' : ''}`} />
                        Test
                      </button>
                      <button
                        onClick={() => handleDeleteFolder(folder)}
                        className="px-3 py-1.5 text-sm bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-200 hover:opacity-80 rounded transition cursor-pointer flex items-center gap-1"
                      >
                        <Trash2 className="w-3 h-3" />
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Add/Edit Modal */}
      {(showAddModal || editingFolder) && (
        <div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-50 flex items-center justify-center p-4">
          <div className="bg-background rounded-lg max-w-lg w-full border border-border shadow-2xl p-6 max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold mb-4">
              {editingFolder ? 'Edit Folder' : 'Add New Folder'}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Name</label>
                <input
                  type="text"
                  value={formData.name || ''}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
                  placeholder="e.g., Primary Storage"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Root Path</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={formData.rootPath || ''}
                    onChange={(e) => setFormData({ ...formData, rootPath: e.target.value })}
                    className="flex-1 px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
                    placeholder="e.g., D:\Media\Movies"
                  />
                  <button
                    onClick={() => handleBrowse('root')}
                    className="px-4 py-3 bg-muted hover:bg-muted/80 rounded-lg transition cursor-pointer"
                  >
                    Browse
                  </button>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Where organized media files will be stored
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Download Path (Optional)</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={formData.downloadPath || ''}
                    onChange={(e) => setFormData({ ...formData, downloadPath: e.target.value })}
                    className="flex-1 px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
                    placeholder="Auto-generated if empty"
                  />
                  <button
                    onClick={() => handleBrowse('download')}
                    className="px-4 py-3 bg-muted hover:bg-muted/80 rounded-lg transition cursor-pointer"
                  >
                    Browse
                  </button>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Must be on the same filesystem as root path for hardlinks
                </p>
              </div>

              {/* Hardlink Status Banner */}
              {(pathTestStatus.testing || pathTestStatus.result) && (
                <div className={`flex items-center gap-2 p-3 rounded-lg text-sm ${
                  pathTestStatus.testing
                    ? 'bg-muted/50 text-muted-foreground'
                    : pathTestStatus.result?.success && pathTestStatus.result?.hardlinkSupported
                    ? 'bg-green-500/10 text-green-500 border border-green-500/20'
                    : pathTestStatus.result?.success && !pathTestStatus.result?.hardlinkSupported
                    ? 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20'
                    : 'bg-red-500/10 text-red-500 border border-red-500/20'
                }`}>
                  {pathTestStatus.testing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                      <span>Testing folder configuration...</span>
                    </>
                  ) : pathTestStatus.result?.success && pathTestStatus.result?.hardlinkSupported ? (
                    <>
                      <Link className="w-4 h-4 shrink-0" />
                      <span>Hardlinks supported - paths are on the same filesystem</span>
                    </>
                  ) : pathTestStatus.result?.success && !pathTestStatus.result?.hardlinkSupported ? (
                    <>
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      <span>Hardlinks not supported - files will need to be copied</span>
                    </>
                  ) : (
                    <>
                      <X className="w-4 h-4 shrink-0" />
                      <span>{pathTestStatus.result?.message || 'Folder configuration error'}</span>
                    </>
                  )}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium mb-1">Priority</label>
                <input
                  type="number"
                  min={0}
                  value={formData.priority || 0}
                  onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                  className="w-full px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none [-moz-appearance:textfield]"
                />
                <p className="text-xs text-muted-foreground mt-1">Lower = higher priority</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Max Disk Usage
                    <span className="ml-2 text-primary font-semibold">
                      {formData.fillThresholdPercent ?? 'Off'}
                      {formData.fillThresholdPercent ? '%' : ''}
                    </span>
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={5}
                    value={formData.fillThresholdPercent ?? 0}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        fillThresholdPercent: parseInt(e.target.value) || undefined,
                      })
                    }
                    className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  />
                  <div className="grid grid-cols-3 text-xs text-muted-foreground mt-1">
                    <span>Off</span>
                    <span className="text-center">50%</span>
                    <span className="text-right">100%</span>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Min Free Space</label>
                  <input
                    type="number"
                    min={0}
                    value={formData.fillThresholdGb ?? ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        fillThresholdGb: e.target.value ? parseInt(e.target.value) : undefined,
                      })
                    }
                    className="w-full px-4 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary [&::-webkit-inner-spin-button]:dark:invert [&::-webkit-outer-spin-button]:dark:invert"
                    placeholder="GB"
                  />
                </div>
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  onClick={handleSaveFolder}
                  disabled={createMutation.isPending || updateMutation.isPending || !formData.name || !formData.rootPath}
                  className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer transition"
                >
                  {createMutation.isPending || updateMutation.isPending ? 'Saving...' : 'Save Folder'}
                </button>
                <button
                  onClick={() => {
                    setShowAddModal(false);
                    setEditingFolder(null);
                    resetForm();
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

      {/* Browse Directory Modal */}
      {showBrowseModal && (
        <div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-50 flex items-center justify-center p-4">
          <div className="bg-background rounded-lg max-w-lg w-full border border-border shadow-2xl p-6 max-h-[80vh] flex flex-col">
            <h2 className="text-xl font-bold mb-4">Browse Directory</h2>

            <div className="flex items-center gap-2 mb-4 p-2 bg-muted rounded-lg">
              <button
                onClick={handleBrowseUp}
                disabled={browseData?.isRoot}
                className="p-2 hover:bg-background rounded disabled:opacity-50 cursor-pointer"
              >
                <ChevronUp className="w-4 h-4" />
              </button>
              <code className="flex-1 text-sm truncate">{browseData?.path || 'Computer'}</code>
            </div>

            <div className="flex-1 overflow-y-auto border border-border rounded-lg">
              {browseData?.directories.map((dir) => (
                <button
                  key={dir}
                  onClick={() => handleNavigateBrowse(dir)}
                  className="w-full flex items-center gap-2 px-4 py-2 hover:bg-muted border-b border-border last:border-b-0 text-left cursor-pointer"
                >
                  <FolderOpen className="w-4 h-4 text-muted-foreground" />
                  <span className="truncate">{dir}</span>
                  <ChevronRight className="w-4 h-4 ml-auto text-muted-foreground" />
                </button>
              ))}
              {browseData?.directories.length === 0 && (
                <div className="p-4 text-center text-muted-foreground">No subdirectories</div>
              )}
            </div>

            <div className="flex gap-3 pt-4">
              <button
                onClick={() => handleSelectPath(browseData?.path || '')}
                disabled={!browseData?.path}
                className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer transition"
              >
                Select This Folder
              </button>
              <button
                onClick={() => setShowBrowseModal(false)}
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
        onCancel={() => setConfirmDialog({ isOpen: false, title: '', message: '', onConfirm: () => {} })}
      />

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-4 right-4 z-[70]">
          <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />
        </div>
      )}
    </div>
  );
}
