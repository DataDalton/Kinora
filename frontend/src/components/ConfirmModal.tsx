'use client';

import { AlertTriangle } from 'lucide-react';

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  onConfirm: () => void;
  onCancel: () => void;
  variant?: 'danger' | 'warning' | 'info';
}

export default function ConfirmModal({
  isOpen,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  onConfirm,
  onCancel,
  variant = 'warning',
}: ConfirmModalProps) {
  if (!isOpen) return null;

  const variantColors = {
    danger: 'bg-destructive text-destructive-foreground',
    warning: 'bg-yellow-600 text-white',
    info: 'bg-primary text-primary-foreground',
  };

  return (
    <div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-[60] flex items-center justify-center p-4">
      <div className="bg-background rounded-lg max-w-md w-full border border-border shadow-2xl p-6">
        <div className="flex items-start gap-4 mb-4">
          <div className={`p-2 rounded-full ${variant === 'danger' ? 'bg-destructive/20' : 'bg-yellow-500/20'}`}>
            <AlertTriangle className={`w-6 h-6 ${variant === 'danger' ? 'text-destructive' : 'text-yellow-500'}`} />
          </div>
          <div className="flex-1">
            <h2 className="text-xl font-bold mb-2">{title}</h2>
            <p className="text-muted-foreground">{message}</p>
          </div>
        </div>
        <div className="flex gap-3 justify-end pt-4">
          <button
            onClick={onCancel}
            className="px-6 py-2 bg-muted text-foreground rounded-lg hover:opacity-90 cursor-pointer transition"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            className={`px-6 py-2 rounded-lg hover:opacity-90 cursor-pointer transition ${variantColors[variant]}`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
