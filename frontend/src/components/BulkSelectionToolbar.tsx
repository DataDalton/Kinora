'use client';

import { useState, useRef, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  CheckSquare,
  Square,
  ChevronDown,
  Eye,
  EyeOff,
  Trash2,
  RefreshCw,
  HardDrive,
  Tag,
  Folder,
  X,
  AlertTriangle,
  Check,
  Minus,
} from 'lucide-react';

interface BulkSelectionToolbarProps {
  mediaType: 'movie' | 'show' | 'anime' | 'album' | 'artist';
  selectedIds: number[];
  totalCount: number;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  onSelectionModeToggle: () => void;
  isSelectionMode: boolean;
  onOperationComplete?: () => void;
}

interface TagItem {
  id: number;
  name: string;
  color: string | null;
}

interface MediaProfile {
  id: number;
  name: string;
}

type BulkAction =
  | 'monitor'
  | 'unmonitor'
  | 'delete'
  | 'delete-files'
  | 'rename'
  | 'refresh-metadata'
  | 'rescan'
  | 'add-tags'
  | 'remove-tags'
  | 'change-profile';

export default function BulkSelectionToolbar({
  mediaType,
  selectedIds,
  totalCount,
  onSelectAll,
  onDeselectAll,
  onSelectionModeToggle,
  isSelectionMode,
  onOperationComplete,
}: BulkSelectionToolbarProps) {
  const [isActionsOpen, setIsActionsOpen] = useState(false);
  const [activeAction, setActiveAction] = useState<BulkAction | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [pendingAction, setPendingAction] = useState<BulkAction | null>(null);
  const [showTagSelector, setShowTagSelector] = useState(false);
  const [showProfileSelector, setShowProfileSelector] = useState(false);
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);
  const [operationProgress, setOperationProgress] = useState<{
    current: number;
    total: number;
    message: string;
  } | null>(null);

  const actionsRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const { data: tags } = useQuery({
    queryKey: ['tags'],
    queryFn: async () => {
      const response = await api.get('/tags/');
      return response.data as TagItem[];
    },
    enabled: showTagSelector,
  });

  const { data: profiles } = useQuery({
    queryKey: ['media-profiles'],
    queryFn: async () => {
      const response = await api.get('/media-profiles/');
      return response.data as MediaProfile[];
    },
    enabled: showProfileSelector,
  });

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (actionsRef.current && !actionsRef.current.contains(event.target as Node)) {
        setIsActionsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const bulkMutation = useMutation({
    mutationFn: async ({ action, payload }: { action: BulkAction; payload: Record<string, unknown> }) => {
      let endpoint = '';
      let method = 'post';

      switch (action) {
        case 'monitor':
        case 'unmonitor':
          endpoint = `/bulk/${mediaType}/monitor`;
          payload = { ...payload, monitored: action === 'monitor' };
          break;
        case 'delete':
          endpoint = `/bulk/${mediaType}/delete`;
          payload = { ...payload, delete_files: false };
          break;
        case 'delete-files':
          endpoint = `/bulk/${mediaType}/delete`;
          payload = { ...payload, delete_files: true };
          break;
        case 'rename':
          endpoint = `/bulk/${mediaType}/rename`;
          break;
        case 'refresh-metadata':
          endpoint = `/bulk/${mediaType}/refresh-metadata`;
          break;
        case 'rescan':
          endpoint = `/bulk/${mediaType}/rescan`;
          break;
        case 'add-tags':
          endpoint = `/bulk/${mediaType}/tags`;
          payload = { ...payload, add_tags: selectedTagIds, remove_tags: [] };
          break;
        case 'remove-tags':
          endpoint = `/bulk/${mediaType}/tags`;
          payload = { ...payload, add_tags: [], remove_tags: selectedTagIds };
          break;
        case 'change-profile':
          endpoint = `/bulk/${mediaType}/media-profile`;
          payload = { ...payload, media_profile_id: selectedProfileId };
          break;
      }

      const response = await api.post(endpoint, { ids: selectedIds, ...payload });
      return response.data;
    },
    onMutate: ({ action }) => {
      setActiveAction(action);
      setOperationProgress({
        current: 0,
        total: selectedIds.length,
        message: getActionProgressMessage(action),
      });
    },
    onSuccess: (data, { action }) => {
      queryClient.invalidateQueries({ queryKey: [mediaType] });
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      setOperationProgress(null);
      setActiveAction(null);
      onDeselectAll();
      onOperationComplete?.();
    },
    onError: () => {
      setOperationProgress(null);
      setActiveAction(null);
    },
  });

  const getActionProgressMessage = (action: BulkAction): string => {
    switch (action) {
      case 'monitor':
        return 'Monitoring items...';
      case 'unmonitor':
        return 'Unmonitoring items...';
      case 'delete':
        return 'Removing from library...';
      case 'delete-files':
        return 'Deleting files...';
      case 'rename':
        return 'Renaming files...';
      case 'refresh-metadata':
        return 'Refreshing metadata...';
      case 'rescan':
        return 'Rescanning files...';
      case 'add-tags':
        return 'Adding tags...';
      case 'remove-tags':
        return 'Removing tags...';
      case 'change-profile':
        return 'Changing media profile...';
      default:
        return 'Processing...';
    }
  };

  const handleAction = (action: BulkAction) => {
    setIsActionsOpen(false);

    if (action === 'delete' || action === 'delete-files') {
      setPendingAction(action);
      setShowConfirmModal(true);
      return;
    }

    if (action === 'add-tags' || action === 'remove-tags') {
      setPendingAction(action);
      setShowTagSelector(true);
      return;
    }

    if (action === 'change-profile') {
      setPendingAction(action);
      setShowProfileSelector(true);
      return;
    }

    bulkMutation.mutate({ action, payload: {} });
  };

  const confirmAction = () => {
    if (pendingAction) {
      bulkMutation.mutate({ action: pendingAction, payload: {} });
    }
    setShowConfirmModal(false);
    setPendingAction(null);
  };

  const confirmTagAction = () => {
    if (pendingAction && selectedTagIds.length > 0) {
      bulkMutation.mutate({ action: pendingAction, payload: {} });
    }
    setShowTagSelector(false);
    setPendingAction(null);
    setSelectedTagIds([]);
  };

  const confirmProfileAction = () => {
    if (pendingAction && selectedProfileId) {
      bulkMutation.mutate({ action: pendingAction, payload: {} });
    }
    setShowProfileSelector(false);
    setPendingAction(null);
    setSelectedProfileId(null);
  };

  const actions: { id: BulkAction; label: string; icon: React.ReactNode; destructive?: boolean }[] = [
    { id: 'monitor', label: 'Monitor Selected', icon: <Eye className="w-4 h-4" /> },
    { id: 'unmonitor', label: 'Unmonitor Selected', icon: <EyeOff className="w-4 h-4" /> },
    { id: 'refresh-metadata', label: 'Refresh Metadata', icon: <RefreshCw className="w-4 h-4" /> },
    { id: 'rescan', label: 'Rescan Files', icon: <HardDrive className="w-4 h-4" /> },
    { id: 'rename', label: 'Rename Files', icon: <Folder className="w-4 h-4" /> },
    { id: 'add-tags', label: 'Add Tags', icon: <Tag className="w-4 h-4" /> },
    { id: 'remove-tags', label: 'Remove Tags', icon: <Tag className="w-4 h-4" /> },
    { id: 'change-profile', label: 'Change Media Profile', icon: <Folder className="w-4 h-4" /> },
    { id: 'delete', label: 'Remove from Library', icon: <Trash2 className="w-4 h-4" />, destructive: true },
    { id: 'delete-files', label: 'Delete from Disk', icon: <Trash2 className="w-4 h-4" />, destructive: true },
  ];

  const allSelected = selectedIds.length === totalCount && totalCount > 0;
  const someSelected = selectedIds.length > 0 && selectedIds.length < totalCount;

  return (
    <>
      <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg border border-border">
        <button
          onClick={onSelectionModeToggle}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition text-sm font-medium ${
            isSelectionMode
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted hover:bg-muted/80'
          }`}
        >
          {isSelectionMode ? (
            <CheckSquare className="w-4 h-4" />
          ) : (
            <Square className="w-4 h-4" />
          )}
          Select
        </button>

        {isSelectionMode && (
          <>
            <div className="h-6 w-px bg-border" />

            <button
              onClick={allSelected ? onDeselectAll : onSelectAll}
              className="flex items-center gap-2 px-3 py-1.5 bg-muted hover:bg-muted/80 rounded-lg transition text-sm"
            >
              {allSelected ? (
                <Minus className="w-4 h-4" />
              ) : someSelected ? (
                <Minus className="w-4 h-4" />
              ) : (
                <Check className="w-4 h-4" />
              )}
              {allSelected ? 'Deselect All' : 'Select All'}
            </button>

            {selectedIds.length > 0 && (
              <>
                <span className="text-sm text-muted-foreground">
                  {selectedIds.length} of {totalCount} selected
                </span>

                <div className="h-6 w-px bg-border" />

                <div className="relative" ref={actionsRef}>
                  <button
                    onClick={() => setIsActionsOpen(!isActionsOpen)}
                    disabled={bulkMutation.isPending}
                    className="flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition text-sm font-medium"
                  >
                    {bulkMutation.isPending ? (
                      <div className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <>
                        Actions
                        <ChevronDown className={`w-4 h-4 transition-transform ${isActionsOpen ? 'rotate-180' : ''}`} />
                      </>
                    )}
                  </button>

                  {isActionsOpen && (
                    <div className="absolute z-20 mt-2 w-56 bg-background rounded-lg border border-border shadow-xl">
                      <div className="p-1">
                        {actions.map((action, index) => (
                          <div key={action.id}>
                            {index === actions.length - 2 && (
                              <div className="my-1 border-t border-border" />
                            )}
                            <button
                              onClick={() => handleAction(action.id)}
                              className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg transition text-sm text-left ${
                                action.destructive
                                  ? 'text-destructive hover:bg-destructive/10'
                                  : 'hover:bg-muted'
                              }`}
                            >
                              {action.icon}
                              {action.label}
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <button
                  onClick={onDeselectAll}
                  className="p-1.5 hover:bg-muted rounded-lg transition"
                  title="Clear selection"
                >
                  <X className="w-4 h-4" />
                </button>
              </>
            )}
          </>
        )}

        {operationProgress && (
          <div className="flex items-center gap-2 ml-auto text-sm text-muted-foreground">
            <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <span>{operationProgress.message}</span>
          </div>
        )}
      </div>

      {showConfirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => {
            setShowConfirmModal(false);
            setPendingAction(null);
          }} />
          <div className="relative bg-background rounded-xl border border-border shadow-2xl w-full max-w-md mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-destructive/20 rounded-lg">
                <AlertTriangle className="w-6 h-6 text-destructive" />
              </div>
              <h3 className="text-lg font-semibold">
                {pendingAction === 'delete-files' ? 'Delete Files?' : 'Remove from Library?'}
              </h3>
            </div>
            <p className="text-muted-foreground mb-6">
              {pendingAction === 'delete-files'
                ? `This will permanently delete ${selectedIds.length} item(s) from disk. This action cannot be undone.`
                : `This will remove ${selectedIds.length} item(s) from your library. Files will remain on disk.`}
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowConfirmModal(false);
                  setPendingAction(null);
                }}
                className="px-4 py-2 text-sm font-medium hover:bg-muted rounded-lg transition"
              >
                Cancel
              </button>
              <button
                onClick={confirmAction}
                className="px-4 py-2 bg-destructive text-destructive-foreground text-sm font-medium rounded-lg hover:bg-destructive/90 transition"
              >
                {pendingAction === 'delete-files' ? 'Delete Files' : 'Remove'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showTagSelector && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => {
            setShowTagSelector(false);
            setPendingAction(null);
            setSelectedTagIds([]);
          }} />
          <div className="relative bg-background rounded-xl border border-border shadow-2xl w-full max-w-md mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-primary/20 rounded-lg">
                <Tag className="w-6 h-6 text-primary" />
              </div>
              <h3 className="text-lg font-semibold">
                {pendingAction === 'add-tags' ? 'Add Tags' : 'Remove Tags'}
              </h3>
            </div>
            <p className="text-muted-foreground mb-4">
              Select tags to {pendingAction === 'add-tags' ? 'add to' : 'remove from'} {selectedIds.length} item(s)
            </p>
            <div className="max-h-60 overflow-y-auto mb-6 space-y-1">
              {tags?.map((tag) => (
                <button
                  key={tag.id}
                  onClick={() => {
                    setSelectedTagIds(prev =>
                      prev.includes(tag.id)
                        ? prev.filter(id => id !== tag.id)
                        : [...prev, tag.id]
                    );
                  }}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition text-left ${
                    selectedTagIds.includes(tag.id) ? 'bg-primary/20' : 'hover:bg-muted'
                  }`}
                >
                  <span
                    className="w-3 h-3 rounded-full flex-shrink-0"
                    style={{ backgroundColor: tag.color || '#6b7280' }}
                  />
                  <span className="flex-1">{tag.name}</span>
                  {selectedTagIds.includes(tag.id) && (
                    <Check className="w-4 h-4 text-primary" />
                  )}
                </button>
              ))}
              {(!tags || tags.length === 0) && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No tags available
                </p>
              )}
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowTagSelector(false);
                  setPendingAction(null);
                  setSelectedTagIds([]);
                }}
                className="px-4 py-2 text-sm font-medium hover:bg-muted rounded-lg transition"
              >
                Cancel
              </button>
              <button
                onClick={confirmTagAction}
                disabled={selectedTagIds.length === 0}
                className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:bg-primary/90 transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {pendingAction === 'add-tags' ? 'Add Tags' : 'Remove Tags'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showProfileSelector && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => {
            setShowProfileSelector(false);
            setPendingAction(null);
            setSelectedProfileId(null);
          }} />
          <div className="relative bg-background rounded-xl border border-border shadow-2xl w-full max-w-md mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-primary/20 rounded-lg">
                <Folder className="w-6 h-6 text-primary" />
              </div>
              <h3 className="text-lg font-semibold">Change Media Profile</h3>
            </div>
            <p className="text-muted-foreground mb-4">
              Select a media profile for {selectedIds.length} item(s)
            </p>
            <div className="max-h-60 overflow-y-auto mb-6 space-y-1">
              {profiles?.map((profile) => (
                <button
                  key={profile.id}
                  onClick={() => setSelectedProfileId(profile.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition text-left ${
                    selectedProfileId === profile.id ? 'bg-primary/20' : 'hover:bg-muted'
                  }`}
                >
                  <Folder className="w-4 h-4 text-muted-foreground" />
                  <span className="flex-1">{profile.name}</span>
                  {selectedProfileId === profile.id && (
                    <Check className="w-4 h-4 text-primary" />
                  )}
                </button>
              ))}
              {(!profiles || profiles.length === 0) && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No media profiles available
                </p>
              )}
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowProfileSelector(false);
                  setPendingAction(null);
                  setSelectedProfileId(null);
                }}
                className="px-4 py-2 text-sm font-medium hover:bg-muted rounded-lg transition"
              >
                Cancel
              </button>
              <button
                onClick={confirmProfileAction}
                disabled={!selectedProfileId}
                className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:bg-primary/90 transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Change Profile
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
