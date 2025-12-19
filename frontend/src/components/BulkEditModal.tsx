'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  X,
  AlertTriangle,
  Trash2,
  Tag,
  Folder,
  Check,
  CheckCircle,
  XCircle,
  ChevronDown,
} from 'lucide-react';

type BulkEditAction = 'delete' | 'tags' | 'media-profile';

interface MediaItem {
  id: number;
  title: string;
  poster_path?: string | null;
  has_file?: boolean;
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

interface BulkEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  mediaType: 'movie' | 'show' | 'anime' | 'album' | 'artist';
  action: BulkEditAction;
  selectedItems: MediaItem[];
  onComplete?: () => void;
}

interface OperationResult {
  success: boolean;
  processed: number;
  failed: number;
  errors?: string[];
}

export default function BulkEditModal({
  isOpen,
  onClose,
  mediaType,
  action,
  selectedItems,
  onComplete,
}: BulkEditModalProps) {
  const [deleteFiles, setDeleteFiles] = useState(false);
  const [addTagIds, setAddTagIds] = useState<number[]>([]);
  const [removeTagIds, setRemoveTagIds] = useState<number[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);
  const [operationResult, setOperationResult] = useState<OperationResult | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);

  const queryClient = useQueryClient();

  const { data: tags } = useQuery({
    queryKey: ['tags'],
    queryFn: async () => {
      const response = await api.get('/tags/');
      return response.data as TagItem[];
    },
    enabled: isOpen && action === 'tags',
  });

  const { data: profiles } = useQuery({
    queryKey: ['media-profiles'],
    queryFn: async () => {
      const response = await api.get('/media-profiles/');
      return response.data as MediaProfile[];
    },
    enabled: isOpen && action === 'media-profile',
  });

  const bulkMutation = useMutation({
    mutationFn: async () => {
      setIsProcessing(true);
      setProgress(0);

      const ids = selectedItems.map(item => item.id);
      let endpoint = '';
      let payload: Record<string, unknown> = { ids };

      switch (action) {
        case 'delete':
          endpoint = `/bulk/${mediaType}/delete`;
          payload.delete_files = deleteFiles;
          break;
        case 'tags':
          endpoint = `/bulk/${mediaType}/tags`;
          payload.add_tags = addTagIds;
          payload.remove_tags = removeTagIds;
          break;
        case 'media-profile':
          endpoint = `/bulk/${mediaType}/media-profile`;
          payload.media_profile_id = selectedProfileId;
          break;
      }

      const response = await api.post(endpoint, payload);
      return response.data;
    },
    onSuccess: (data) => {
      setProgress(100);
      setOperationResult({
        success: true,
        processed: selectedItems.length,
        failed: 0,
      });
      queryClient.invalidateQueries({ queryKey: [mediaType] });
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      setTimeout(() => {
        onComplete?.();
        handleClose();
      }, 1500);
    },
    onError: (error: Error) => {
      setOperationResult({
        success: false,
        processed: 0,
        failed: selectedItems.length,
        errors: [error.message || 'An error occurred'],
      });
      setIsProcessing(false);
    },
  });

  const handleClose = () => {
    if (isProcessing && !operationResult) return;

    setDeleteFiles(false);
    setAddTagIds([]);
    setRemoveTagIds([]);
    setSelectedProfileId(null);
    setOperationResult(null);
    setIsProcessing(false);
    setProgress(0);
    onClose();
  };

  const handleExecute = () => {
    if (action === 'tags' && addTagIds.length === 0 && removeTagIds.length === 0) {
      return;
    }
    if (action === 'media-profile' && !selectedProfileId) {
      return;
    }
    bulkMutation.mutate();
  };

  const canExecute = () => {
    switch (action) {
      case 'delete':
        return true;
      case 'tags':
        return addTagIds.length > 0 || removeTagIds.length > 0;
      case 'media-profile':
        return selectedProfileId !== null;
      default:
        return false;
    }
  };

  const getActionTitle = () => {
    switch (action) {
      case 'delete':
        return 'Delete Items';
      case 'tags':
        return 'Manage Tags';
      case 'media-profile':
        return 'Change Media Profile';
      default:
        return 'Bulk Edit';
    }
  };

  const getActionIcon = () => {
    switch (action) {
      case 'delete':
        return <Trash2 className="w-6 h-6 text-destructive" />;
      case 'tags':
        return <Tag className="w-6 h-6 text-primary" />;
      case 'media-profile':
        return <Folder className="w-6 h-6 text-primary" />;
      default:
        return null;
    }
  };

  const toggleAddTag = (tagId: number) => {
    setAddTagIds(prev =>
      prev.includes(tagId) ? prev.filter(id => id !== tagId) : [...prev, tagId]
    );
    setRemoveTagIds(prev => prev.filter(id => id !== tagId));
  };

  const toggleRemoveTag = (tagId: number) => {
    setRemoveTagIds(prev =>
      prev.includes(tagId) ? prev.filter(id => id !== tagId) : [...prev, tagId]
    );
    setAddTagIds(prev => prev.filter(id => id !== tagId));
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />

      <div className="relative bg-background rounded-xl border border-border shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${action === 'delete' ? 'bg-destructive/20' : 'bg-primary/20'}`}>
              {getActionIcon()}
            </div>
            <div>
              <h2 className="text-lg font-semibold">{getActionTitle()}</h2>
              <p className="text-sm text-muted-foreground">
                {selectedItems.length} item{selectedItems.length !== 1 ? 's' : ''} selected
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            disabled={isProcessing && !operationResult}
            className="p-2 hover:bg-muted rounded-lg transition disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 overflow-y-auto max-h-[calc(90vh-200px)]">
          {operationResult ? (
            <div className="flex flex-col items-center justify-center py-8">
              {operationResult.success ? (
                <>
                  <CheckCircle className="w-16 h-16 text-green-500 mb-4" />
                  <h3 className="text-lg font-semibold mb-2">Operation Complete</h3>
                  <p className="text-muted-foreground">
                    Successfully processed {operationResult.processed} item{operationResult.processed !== 1 ? 's' : ''}
                  </p>
                </>
              ) : (
                <>
                  <XCircle className="w-16 h-16 text-destructive mb-4" />
                  <h3 className="text-lg font-semibold mb-2">Operation Failed</h3>
                  <p className="text-muted-foreground mb-4">
                    Failed to process {operationResult.failed} item{operationResult.failed !== 1 ? 's' : ''}
                  </p>
                  {operationResult.errors && operationResult.errors.length > 0 && (
                    <div className="w-full max-w-md bg-destructive/10 border border-destructive/20 rounded-lg p-3">
                      {operationResult.errors.map((error, index) => (
                        <p key={index} className="text-sm text-destructive">{error}</p>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          ) : isProcessing ? (
            <div className="flex flex-col items-center justify-center py-8">
              <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4" />
              <h3 className="text-lg font-semibold mb-2">Processing...</h3>
              <p className="text-muted-foreground mb-4">
                Please wait while the operation completes
              </p>
              <div className="w-full max-w-md">
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            </div>
          ) : (
            <>
              <div className="mb-6">
                <h4 className="text-sm font-medium text-muted-foreground mb-2">
                  Selected Items
                </h4>
                <div className="max-h-40 overflow-y-auto bg-muted/30 rounded-lg border border-border p-2 space-y-1">
                  {selectedItems.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center gap-2 px-2 py-1 text-sm"
                    >
                      <span className="truncate">{item.title}</span>
                      {item.has_file && (
                        <span className="text-xs text-green-500">(has file)</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {action === 'delete' && (
                <div className="space-y-4">
                  <div className="flex items-start gap-3 p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
                    <AlertTriangle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium text-destructive">Warning</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        This action will remove the selected items from your library.
                        {deleteFiles && ' Files will also be permanently deleted from disk.'}
                      </p>
                    </div>
                  </div>

                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={deleteFiles}
                      onChange={(e) => setDeleteFiles(e.target.checked)}
                      className="w-4 h-4 rounded border-border"
                    />
                    <span className="text-sm">
                      Also delete files from disk
                    </span>
                  </label>
                </div>
              )}

              {action === 'tags' && (
                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-medium mb-2">Add Tags</h4>
                    <div className="flex flex-wrap gap-2">
                      {tags?.map((tag) => (
                        <button
                          key={`add-${tag.id}`}
                          onClick={() => toggleAddTag(tag.id)}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm transition ${
                            addTagIds.includes(tag.id)
                              ? 'ring-2 ring-green-500'
                              : 'hover:ring-2 hover:ring-muted'
                          }`}
                          style={{
                            backgroundColor: tag.color || '#6b7280',
                            color: '#ffffff',
                          }}
                        >
                          {addTagIds.includes(tag.id) && <Check className="w-3 h-3" />}
                          {tag.name}
                        </button>
                      ))}
                      {(!tags || tags.length === 0) && (
                        <p className="text-sm text-muted-foreground">No tags available</p>
                      )}
                    </div>
                  </div>

                  <div>
                    <h4 className="text-sm font-medium mb-2">Remove Tags</h4>
                    <div className="flex flex-wrap gap-2">
                      {tags?.map((tag) => (
                        <button
                          key={`remove-${tag.id}`}
                          onClick={() => toggleRemoveTag(tag.id)}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm transition ${
                            removeTagIds.includes(tag.id)
                              ? 'ring-2 ring-destructive'
                              : 'hover:ring-2 hover:ring-muted'
                          }`}
                          style={{
                            backgroundColor: tag.color || '#6b7280',
                            color: '#ffffff',
                          }}
                        >
                          {removeTagIds.includes(tag.id) && <X className="w-3 h-3" />}
                          {tag.name}
                        </button>
                      ))}
                      {(!tags || tags.length === 0) && (
                        <p className="text-sm text-muted-foreground">No tags available</p>
                      )}
                    </div>
                  </div>

                  {(addTagIds.length > 0 || removeTagIds.length > 0) && (
                    <div className="p-3 bg-muted/30 rounded-lg border border-border">
                      <h4 className="text-sm font-medium mb-2">Preview Changes</h4>
                      <div className="space-y-1 text-sm">
                        {addTagIds.length > 0 && (
                          <p className="text-green-500">
                            + Adding {addTagIds.length} tag{addTagIds.length !== 1 ? 's' : ''}
                          </p>
                        )}
                        {removeTagIds.length > 0 && (
                          <p className="text-destructive">
                            - Removing {removeTagIds.length} tag{removeTagIds.length !== 1 ? 's' : ''}
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {action === 'media-profile' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Select Media Profile
                    </label>
                    <div className="relative">
                      <select
                        value={selectedProfileId || ''}
                        onChange={(e) => setSelectedProfileId(e.target.value ? Number(e.target.value) : null)}
                        className="w-full px-4 py-2.5 bg-muted border border-border rounded-lg appearance-none focus:outline-none focus:ring-2 focus:ring-primary"
                      >
                        <option value="">Select a profile...</option>
                        {profiles?.map((profile) => (
                          <option key={profile.id} value={profile.id}>
                            {profile.name}
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                    </div>
                  </div>

                  {selectedProfileId && (
                    <div className="p-3 bg-muted/30 rounded-lg border border-border">
                      <h4 className="text-sm font-medium mb-1">Preview</h4>
                      <p className="text-sm text-muted-foreground">
                        {selectedItems.length} item{selectedItems.length !== 1 ? 's' : ''} will be assigned to{' '}
                        <span className="font-medium text-foreground">
                          {profiles?.find(p => p.id === selectedProfileId)?.name}
                        </span>
                      </p>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {!operationResult && !isProcessing && (
          <div className="flex items-center justify-end gap-3 p-4 border-t border-border bg-muted/30">
            <button
              onClick={handleClose}
              className="px-4 py-2 text-sm font-medium hover:bg-muted rounded-lg transition"
            >
              Cancel
            </button>
            <button
              onClick={handleExecute}
              disabled={!canExecute()}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed ${
                action === 'delete'
                  ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90'
                  : 'bg-primary text-primary-foreground hover:bg-primary/90'
              }`}
            >
              {action === 'delete' ? (
                <>
                  <Trash2 className="w-4 h-4" />
                  {deleteFiles ? 'Delete Files' : 'Remove from Library'}
                </>
              ) : action === 'tags' ? (
                <>
                  <Tag className="w-4 h-4" />
                  Apply Tags
                </>
              ) : (
                <>
                  <Folder className="w-4 h-4" />
                  Apply Profile
                </>
              )}
            </button>
          </div>
        )}

        {operationResult && !operationResult.success && (
          <div className="flex items-center justify-end gap-3 p-4 border-t border-border bg-muted/30">
            <button
              onClick={handleClose}
              className="px-4 py-2 text-sm font-medium hover:bg-muted rounded-lg transition"
            >
              Close
            </button>
            <button
              onClick={() => {
                setOperationResult(null);
                setIsProcessing(false);
              }}
              className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:bg-primary/90 transition"
            >
              Try Again
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
