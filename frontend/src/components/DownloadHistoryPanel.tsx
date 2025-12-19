'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  History,
  ChevronDown,
  ChevronUp,
  Download,
  CheckCircle,
  XCircle,
  Clock,
  ArrowUpCircle,
  ExternalLink,
  HardDrive,
  Calendar,
} from 'lucide-react';

interface DownloadHistoryEntry {
  id: number;
  media_type: string;
  media_id: number;
  episode_id: number | null;
  torrent_hash: string;
  torrent_title: string;
  indexer: string;
  indexer_page_url: string | null;
  quality: string | null;
  source: string | null;
  size: number | null;
  status: string;
  progress: number;
  was_upgrade: boolean;
  started_at: string;
  completed_at: string | null;
}

interface DownloadHistoryPanelProps {
  mediaType: 'movie' | 'show' | 'anime' | 'album';
  mediaId: number;
  defaultExpanded?: boolean;
}

const formatSize = (bytes: number | null): string => {
  if (!bytes) return 'Unknown';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const formatDate = (dateStr: string): string => {
  const date = new Date(dateStr);
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'completed':
      return <CheckCircle className="w-4 h-4 text-green-500" />;
    case 'failed':
      return <XCircle className="w-4 h-4 text-destructive" />;
    case 'downloading':
      return <Download className="w-4 h-4 text-blue-500 animate-pulse" />;
    default:
      return <Clock className="w-4 h-4 text-yellow-500" />;
  }
};

const getStatusLabel = (status: string): string => {
  switch (status) {
    case 'completed':
      return 'Completed';
    case 'failed':
      return 'Failed';
    case 'downloading':
      return 'Downloading';
    case 'pending':
      return 'Pending';
    default:
      return status;
  }
};

export default function DownloadHistoryPanel({
  mediaType,
  mediaId,
  defaultExpanded = false,
}: DownloadHistoryPanelProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const { data: history, isLoading } = useQuery({
    queryKey: ['history', 'media', mediaType, mediaId],
    queryFn: async () => {
      const response = await api.get(`/history/media/${mediaType}/${mediaId}`);
      return response.data as DownloadHistoryEntry[];
    },
    enabled: isExpanded,
  });

  return (
    <div className="bg-muted/30 rounded-lg border border-border">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition rounded-lg"
      >
        <div className="flex items-center gap-3">
          <History className="w-5 h-5 text-muted-foreground" />
          <span className="font-medium">Download History</span>
          {history && history.length > 0 && (
            <span className="px-2 py-0.5 bg-muted text-xs rounded-full">
              {history.length}
            </span>
          )}
        </div>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-5 h-5 text-muted-foreground" />
        )}
      </button>

      {isExpanded && (
        <div className="px-4 pb-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8 text-muted-foreground">
              <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          ) : history && history.length > 0 ? (
            <div className="space-y-3">
              {history.map((entry) => (
                <div
                  key={entry.id}
                  className="bg-background rounded-lg p-4 border border-border"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        {getStatusIcon(entry.status)}
                        <span className="text-sm font-medium">
                          {getStatusLabel(entry.status)}
                        </span>
                        {entry.was_upgrade && (
                          <span className="flex items-center gap-1 px-2 py-0.5 bg-blue-500/20 text-blue-500 text-xs rounded">
                            <ArrowUpCircle className="w-3 h-3" />
                            Upgrade
                          </span>
                        )}
                      </div>
                      <p className="text-sm truncate mb-2" title={entry.torrent_title}>
                        {entry.torrent_title}
                      </p>
                      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                        {entry.quality && (
                          <span className="px-2 py-0.5 bg-primary/20 text-primary rounded">
                            {entry.quality}
                          </span>
                        )}
                        {entry.source && (
                          <span className="px-2 py-0.5 bg-muted rounded">
                            {entry.source}
                          </span>
                        )}
                        <span className="flex items-center gap-1">
                          <HardDrive className="w-3 h-3" />
                          {formatSize(entry.size)}
                        </span>
                        <span className="flex items-center gap-1">
                          {entry.indexer}
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {formatDate(entry.started_at)}
                        </span>
                      </div>
                    </div>
                    {entry.indexer_page_url && (
                      <a
                        href={entry.indexer_page_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-2 bg-muted rounded-lg hover:bg-muted/80 transition"
                        title="View on indexer"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                  </div>
                  {entry.status === 'downloading' && (
                    <div className="mt-3">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-muted-foreground">Progress</span>
                        <span>{Math.round(entry.progress)}%</span>
                      </div>
                      <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary transition-all duration-300"
                          style={{ width: `${entry.progress}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
              <History className="w-10 h-10 mb-2 opacity-50" />
              <p className="text-sm">No download history</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
