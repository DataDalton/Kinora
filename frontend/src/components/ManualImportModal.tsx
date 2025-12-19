'use client';

import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  X,
  FolderOpen,
  FileVideo,
  FileAudio,
  Upload,
  HardDrive,
  AlertCircle,
  CheckCircle,
  ChevronDown,
} from 'lucide-react';

interface Episode {
  id: number;
  season_number: number;
  episode_number: number;
  title: string;
  has_file: boolean;
}

interface Season {
  id: number;
  season_number: number;
  title: string;
  episode_count: number;
}

interface ManualImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  mediaType: 'movie' | 'show' | 'anime' | 'album';
  mediaId: number;
  mediaTitle: string;
  onImportComplete?: () => void;
}

const formatSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

export default function ManualImportModal({
  isOpen,
  onClose,
  mediaType,
  mediaId,
  mediaTitle,
  onImportComplete,
}: ManualImportModalProps) {
  const [filePath, setFilePath] = useState('');
  const [selectedSeasonId, setSelectedSeasonId] = useState<number | null>(null);
  const [selectedEpisodeId, setSelectedEpisodeId] = useState<number | null>(null);
  const [previewInfo, setPreviewInfo] = useState<{
    filename: string;
    size: number;
    extension: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const queryClient = useQueryClient();

  const needsEpisodeSelection = mediaType === 'show' || mediaType === 'anime';

  const { data: seasons } = useQuery({
    queryKey: ['seasons', mediaType, mediaId],
    queryFn: async () => {
      if (mediaType === 'show') {
        const response = await api.get(`/shows/${mediaId}/seasons`);
        return response.data as Season[];
      }
      return null;
    },
    enabled: isOpen && mediaType === 'show',
  });

  const { data: episodes } = useQuery({
    queryKey: ['episodes', mediaType, mediaId, selectedSeasonId],
    queryFn: async () => {
      if (mediaType === 'show' && selectedSeasonId) {
        const season = seasons?.find(s => s.id === selectedSeasonId);
        if (season) {
          const response = await api.get(`/shows/${mediaId}/seasons/${season.season_number}/episodes`);
          return response.data as Episode[];
        }
      } else if (mediaType === 'anime') {
        const response = await api.get(`/anime/${mediaId}/episodes`);
        return response.data as Episode[];
      }
      return null;
    },
    enabled: isOpen && ((mediaType === 'show' && selectedSeasonId !== null) || mediaType === 'anime'),
  });

  const importMutation = useMutation({
    mutationFn: async () => {
      const payload: {
        file_path: string;
        episode_id?: number;
        copy_file?: boolean;
      } = {
        file_path: filePath,
        copy_file: false,
      };

      if (needsEpisodeSelection && selectedEpisodeId) {
        payload.episode_id = selectedEpisodeId;
      }

      const response = await api.post(`/files/${mediaType}/${mediaId}/manual-import`, payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [mediaType, mediaId] });
      queryClient.invalidateQueries({ queryKey: ['files', mediaType, mediaId] });
      onImportComplete?.();
      handleClose();
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to import file');
    },
  });

  const handlePathChange = (path: string) => {
    setFilePath(path);
    setError(null);

    if (path.trim()) {
      const pathParts = path.split(/[/\\]/);
      const filename = pathParts[pathParts.length - 1] || '';
      const extensionMatch = filename.match(/\.([^.]+)$/);
      const extension = extensionMatch ? extensionMatch[1].toLowerCase() : '';

      setPreviewInfo({
        filename,
        size: 0,
        extension,
      });
    } else {
      setPreviewInfo(null);
    }
  };

  const handleClose = () => {
    setFilePath('');
    setSelectedSeasonId(null);
    setSelectedEpisodeId(null);
    setPreviewInfo(null);
    setError(null);
    onClose();
  };

  const handleImport = () => {
    if (!filePath.trim()) {
      setError('Please enter a file path');
      return;
    }

    if (needsEpisodeSelection && !selectedEpisodeId) {
      setError('Please select an episode');
      return;
    }

    importMutation.mutate();
  };

  const isValidPath = filePath.trim().length > 0;
  const canImport = isValidPath && (!needsEpisodeSelection || selectedEpisodeId !== null);

  useEffect(() => {
    if (isOpen) {
      setFilePath('');
      setSelectedSeasonId(null);
      setSelectedEpisodeId(null);
      setPreviewInfo(null);
      setError(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const isAudio = mediaType === 'album';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />

      <div className="relative bg-background rounded-xl border border-border shadow-2xl w-full max-w-xl mx-4 max-h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/20 rounded-lg">
              <Upload className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">Manual Import</h2>
              <p className="text-sm text-muted-foreground truncate max-w-[300px]">
                {mediaTitle}
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-2 hover:bg-muted rounded-lg transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 space-y-4 overflow-y-auto max-h-[calc(90vh-180px)]">
          <div>
            <label className="block text-sm font-medium mb-2">
              File Path
            </label>
            <div className="relative">
              <FolderOpen className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                value={filePath}
                onChange={(e) => handlePathChange(e.target.value)}
                placeholder={isAudio ? '/path/to/album/track.flac' : '/path/to/media/file.mkv'}
                className="w-full pl-10 pr-4 py-2.5 bg-muted border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary text-sm"
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Enter the full path to the file on the server
            </p>
          </div>

          {previewInfo && (
            <div className="bg-muted/50 rounded-lg p-3 border border-border">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-background rounded-lg">
                  {isAudio ? (
                    <FileAudio className="w-5 h-5 text-primary" />
                  ) : (
                    <FileVideo className="w-5 h-5 text-primary" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate">{previewInfo.filename}</p>
                  <div className="flex items-center gap-2 mt-1">
                    {previewInfo.extension && (
                      <span className="px-2 py-0.5 bg-primary/20 text-primary rounded text-xs uppercase">
                        {previewInfo.extension}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {mediaType === 'show' && seasons && seasons.length > 0 && (
            <div>
              <label className="block text-sm font-medium mb-2">
                Select Season
              </label>
              <div className="relative">
                <select
                  value={selectedSeasonId || ''}
                  onChange={(e) => {
                    setSelectedSeasonId(e.target.value ? Number(e.target.value) : null);
                    setSelectedEpisodeId(null);
                  }}
                  className="w-full px-4 py-2.5 bg-muted border border-border rounded-lg appearance-none focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                >
                  <option value="">Select a season...</option>
                  {seasons.map((season) => (
                    <option key={season.id} value={season.id}>
                      Season {season.season_number}
                      {season.title && ` - ${season.title}`}
                      {` (${season.episode_count} episodes)`}
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
              </div>
            </div>
          )}

          {needsEpisodeSelection && episodes && episodes.length > 0 && (
            <div>
              <label className="block text-sm font-medium mb-2">
                Select Episode
              </label>
              <div className="relative">
                <select
                  value={selectedEpisodeId || ''}
                  onChange={(e) => setSelectedEpisodeId(e.target.value ? Number(e.target.value) : null)}
                  className="w-full px-4 py-2.5 bg-muted border border-border rounded-lg appearance-none focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                >
                  <option value="">Select an episode...</option>
                  {episodes.map((episode) => (
                    <option key={episode.id} value={episode.id}>
                      {mediaType === 'show'
                        ? `S${String(episode.season_number).padStart(2, '0')}E${String(episode.episode_number).padStart(2, '0')}`
                        : `Episode ${episode.episode_number}`}
                      {episode.title && ` - ${episode.title}`}
                      {episode.has_file && ' (has file)'}
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
              </div>
            </div>
          )}

          {mediaType === 'anime' && !episodes && (
            <div className="bg-muted/50 rounded-lg p-3 border border-border">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <HardDrive className="w-4 h-4" />
                <span>Loading episodes...</span>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-destructive text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {importMutation.isSuccess && (
            <div className="flex items-center gap-2 p-3 bg-green-500/10 border border-green-500/20 rounded-lg text-green-500 text-sm">
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
              <span>File imported successfully</span>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 p-4 border-t border-border bg-muted/30">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-sm font-medium hover:bg-muted rounded-lg transition"
          >
            Cancel
          </button>
          <button
            onClick={handleImport}
            disabled={!canImport || importMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:bg-primary/90 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {importMutation.isPending ? (
              <>
                <div className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
                Importing...
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                Import File
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
