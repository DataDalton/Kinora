'use client';

import { useState } from 'react';
import { Trash2, AlertTriangle, Loader2 } from 'lucide-react';

interface DeleteConfirmModalProps {
  isOpen: boolean;
  title: string;
  itemName: string;
  hasFiles: boolean;
  onConfirm: (deleteFiles: boolean) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export default function DeleteConfirmModal({
  isOpen,
  title,
  itemName,
  hasFiles,
  onConfirm,
  onCancel,
  isLoading = false,
}: DeleteConfirmModalProps) {
  const [deleteFiles, setDeleteFiles] = useState(false);

  if (!isOpen) return null;

  const handleConfirm = () => {
    onConfirm(deleteFiles);
  };

  return (
    <div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-[60] flex items-center justify-center p-4">
      <div className="bg-background rounded-lg max-w-md w-full border border-border shadow-2xl p-6">
        <div className="flex items-start gap-4 mb-4">
          <div className="p-2 rounded-full bg-destructive/20">
            <AlertTriangle className="w-6 h-6 text-destructive" />
          </div>
          <div className="flex-1">
            <h2 className="text-xl font-bold mb-2">{title}</h2>
            <p className="text-muted-foreground">
              Are you sure you want to remove <span className="font-semibold text-foreground">{itemName}</span> from your library?
            </p>
          </div>
        </div>

        {hasFiles && (
          <div className="bg-muted/50 rounded-lg p-4 mb-4 border border-border">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={deleteFiles}
                onChange={(e) => setDeleteFiles(e.target.checked)}
                className="mt-1 w-4 h-4 rounded border-border bg-muted text-destructive focus:ring-destructive"
              />
              <div>
                <span className="font-medium text-foreground flex items-center gap-2">
                  <Trash2 className="w-4 h-4" />
                  Also delete files from disk
                </span>
                <p className="text-sm text-muted-foreground mt-1">
                  This will permanently delete all downloaded files associated with this item. This action cannot be undone.
                </p>
              </div>
            </label>
          </div>
        )}

        {deleteFiles && (
          <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-3 mb-4">
            <p className="text-sm text-destructive flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              Warning: Files will be permanently deleted from your disk
            </p>
          </div>
        )}

        <div className="flex gap-3 justify-end pt-4">
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="px-6 py-2 bg-muted text-foreground rounded-lg hover:opacity-90 cursor-pointer transition disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={isLoading}
            className="px-6 py-2 rounded-lg hover:opacity-90 cursor-pointer transition bg-destructive text-destructive-foreground flex items-center gap-2 disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Deleting...
              </>
            ) : (
              <>
                <Trash2 className="w-4 h-4" />
                {deleteFiles ? 'Delete Everything' : 'Remove from Library'}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
