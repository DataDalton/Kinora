'use client';

import { useEffect, useState } from 'react';
import { CheckCircle, XCircle, AlertCircle, X } from 'lucide-react';
import { audioNotification } from '@/utils/audio';

interface ToastProps {
  message: string;
  type: 'success' | 'error' | 'info';
  onClose: () => void;
  duration?: number;
}

export default function Toast({ message, type, onClose, duration = 3000 }: ToastProps) {
  // Play sound only once when component mounts
  useEffect(() => {
    audioNotification.play(type);
  }, [type]);

  // Handle auto-dismiss timer
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose();
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onClose]);

  const icons = {
    success: <CheckCircle className="w-5 h-5" />,
    error: <XCircle className="w-5 h-5" />,
    info: <AlertCircle className="w-5 h-5" />,
  };

  const colors = {
    success: 'bg-green-500/10 border-green-500/50 text-green-400',
    error: 'bg-red-500/10 border-red-500/50 text-red-400',
    info: 'bg-blue-500/10 border-blue-500/50 text-blue-400',
  };

  const progressColors = {
    success: 'bg-green-500',
    error: 'bg-red-500',
    info: 'bg-blue-500',
  };

  const [progress, setProgress] = useState(100);

  useEffect(() => {
    setProgress(0);
  }, []);

  return (
    <div className={`relative overflow-hidden flex items-center gap-3 px-4 py-3 rounded-lg border ${colors[type]} shadow-lg backdrop-blur-sm animate-in slide-in-from-right`}>
      {icons[type]}
      <p className="flex-1 text-sm font-medium">{message}</p>
      <button
        onClick={onClose}
        className="hover:opacity-70 transition cursor-pointer"
      >
        <X className="w-4 h-4" />
      </button>

      {/* Progress bar */}
      <div
        className={`absolute bottom-0 left-0 h-1 ${progressColors[type]}`}
        style={{
          width: `${progress}%`,
          transition: `width ${duration}ms linear`
        }}
      />
    </div>
  );
}
