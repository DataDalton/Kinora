'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  HardDrive,
  FolderOpen,
  Film,
  Music,
  FileVideo,
  FileAudio,
  RefreshCw,
  CheckCircle,
  ArrowUpCircle,
  Copy,
  Check,
} from 'lucide-react';

interface FileInfo {
  file_path: string;
  file_name: string;
  file_size: number | null;
  quality: string | null;
  resolution: string | null;
  codec: string | null;
  audio_codec: string | null;
  audio_channels: string | null;
  container: string | null;
  bit_depth: string | null;
  hdr: boolean;
  created_at: string | null;
}

interface QualityCutoff {
  meets_cutoff: boolean;
  current_quality: string | null;
  cutoff_quality: string;
  upgrade_allowed: boolean;
}

interface FileQualityInfoProps {
  mediaType: 'movie' | 'show' | 'anime' | 'album';
  mediaId: number;
  files: FileInfo[];
  qualityCutoff?: QualityCutoff;
  onRescanComplete?: () => void;
}

const formatSize = (bytes: number | null): string => {
  if (!bytes) return 'Unknown';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const formatPath = (path: string): { directory: string; filename: string } => {
  const lastSeparator = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
  if (lastSeparator === -1) {
    return { directory: '', filename: path };
  }
  return {
    directory: path.substring(0, lastSeparator),
    filename: path.substring(lastSeparator + 1),
  };
};

export default function FileQualityInfo({
  mediaType,
  mediaId,
  files,
  qualityCutoff,
  onRescanComplete,
}: FileQualityInfoProps) {
  const [copiedPath, setCopiedPath] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const rescanMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/files/${mediaType}/${mediaId}/rescan`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [mediaType, mediaId] });
      queryClient.invalidateQueries({ queryKey: ['files', mediaType, mediaId] });
      onRescanComplete?.();
    },
  });

  const copyToClipboard = async (path: string) => {
    try {
      await navigator.clipboard.writeText(path);
      setCopiedPath(path);
      setTimeout(() => setCopiedPath(null), 2000);
    } catch {
      console.error('Failed to copy path');
    }
  };

  if (!files || files.length === 0) {
    return (
      <div className="bg-muted/30 rounded-lg border border-border p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <HardDrive className="w-5 h-5 text-muted-foreground" />
            <span className="font-medium">File Information</span>
          </div>
          <button
            onClick={() => rescanMutation.mutate()}
            disabled={rescanMutation.isPending}
            className="flex items-center gap-2 px-3 py-1.5 bg-muted hover:bg-muted/80 rounded-lg transition text-sm"
          >
            <RefreshCw className={`w-4 h-4 ${rescanMutation.isPending ? 'animate-spin' : ''}`} />
            Rescan
          </button>
        </div>
        <div className="flex flex-col items-center justify-center py-6 text-muted-foreground">
          <FileVideo className="w-10 h-10 mb-2 opacity-50" />
          <p className="text-sm">No files found</p>
          <p className="text-xs mt-1">Files will appear here once downloaded</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-muted/30 rounded-lg border border-border p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <HardDrive className="w-5 h-5 text-muted-foreground" />
          <span className="font-medium">File Information</span>
          {files.length > 1 && (
            <span className="px-2 py-0.5 bg-muted text-xs rounded-full">
              {files.length} files
            </span>
          )}
        </div>
        <button
          onClick={() => rescanMutation.mutate()}
          disabled={rescanMutation.isPending}
          className="flex items-center gap-2 px-3 py-1.5 bg-muted hover:bg-muted/80 rounded-lg transition text-sm"
        >
          <RefreshCw className={`w-4 h-4 ${rescanMutation.isPending ? 'animate-spin' : ''}`} />
          Rescan
        </button>
      </div>

      {qualityCutoff && (
        <div className="mb-4 p-3 rounded-lg border border-border bg-background">
          <div className="flex items-center gap-3">
            {qualityCutoff.meets_cutoff ? (
              <>
                <CheckCircle className="w-5 h-5 text-green-500" />
                <div>
                  <p className="text-sm font-medium text-green-500">Quality Cutoff Met</p>
                  <p className="text-xs text-muted-foreground">
                    Current: {qualityCutoff.current_quality || 'Unknown'} | Cutoff: {qualityCutoff.cutoff_quality}
                  </p>
                </div>
              </>
            ) : qualityCutoff.upgrade_allowed ? (
              <>
                <ArrowUpCircle className="w-5 h-5 text-yellow-500" />
                <div>
                  <p className="text-sm font-medium text-yellow-500">Upgrade Available</p>
                  <p className="text-xs text-muted-foreground">
                    Current: {qualityCutoff.current_quality || 'Unknown'} | Target: {qualityCutoff.cutoff_quality}
                  </p>
                </div>
              </>
            ) : (
              <>
                <CheckCircle className="w-5 h-5 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Below Cutoff</p>
                  <p className="text-xs text-muted-foreground">
                    Current: {qualityCutoff.current_quality || 'Unknown'} | Cutoff: {qualityCutoff.cutoff_quality} (upgrades disabled)
                  </p>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      <div className="space-y-3">
        {files.map((file, index) => {
          const { directory, filename } = formatPath(file.file_path);
          const isAudio = mediaType === 'album';

          return (
            <div
              key={file.file_path || index}
              className="bg-background rounded-lg p-3 border border-border"
            >
              <div className="flex items-start gap-3">
                <div className="p-2 bg-muted rounded-lg">
                  {isAudio ? (
                    <Music className="w-5 h-5 text-primary" />
                  ) : (
                    <Film className="w-5 h-5 text-primary" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate" title={filename}>
                    {filename}
                  </p>
                  {directory && (
                    <div className="flex items-center gap-1 mt-1">
                      <FolderOpen className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                      <p className="text-xs text-muted-foreground truncate" title={directory}>
                        {directory}
                      </p>
                      <button
                        onClick={() => copyToClipboard(file.file_path)}
                        className="p-1 hover:bg-muted rounded transition flex-shrink-0"
                        title="Copy full path"
                      >
                        {copiedPath === file.file_path ? (
                          <Check className="w-3 h-3 text-green-500" />
                        ) : (
                          <Copy className="w-3 h-3 text-muted-foreground" />
                        )}
                      </button>
                    </div>
                  )}

                  <div className="flex flex-wrap gap-2 mt-2">
                    {file.file_size && (
                      <span className="flex items-center gap-1 px-2 py-0.5 bg-muted rounded text-xs">
                        <HardDrive className="w-3 h-3" />
                        {formatSize(file.file_size)}
                      </span>
                    )}

                    {file.quality && (
                      <span className="px-2 py-0.5 bg-primary/20 text-primary rounded text-xs font-medium">
                        {file.quality}
                      </span>
                    )}

                    {file.resolution && (
                      <span className="px-2 py-0.5 bg-blue-500/20 text-blue-500 rounded text-xs">
                        {file.resolution}
                      </span>
                    )}

                    {file.hdr && (
                      <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-500 rounded text-xs font-medium">
                        HDR
                      </span>
                    )}

                    {file.codec && (
                      <span className="flex items-center gap-1 px-2 py-0.5 bg-muted rounded text-xs">
                        <FileVideo className="w-3 h-3" />
                        {file.codec}
                      </span>
                    )}

                    {file.audio_codec && (
                      <span className="flex items-center gap-1 px-2 py-0.5 bg-muted rounded text-xs">
                        <FileAudio className="w-3 h-3" />
                        {file.audio_codec}
                        {file.audio_channels && ` ${file.audio_channels}`}
                      </span>
                    )}

                    {file.container && (
                      <span className="px-2 py-0.5 bg-muted rounded text-xs uppercase">
                        {file.container}
                      </span>
                    )}

                    {file.bit_depth && (
                      <span className="px-2 py-0.5 bg-muted rounded text-xs">
                        {file.bit_depth}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {files.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              Total size: {formatSize(files.reduce((sum, f) => sum + (f.file_size || 0), 0))}
            </span>
            {files.length > 1 && (
              <span>{files.length} files</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
