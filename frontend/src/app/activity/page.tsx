'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

interface Download {
  id: number;
  media_id: number;
  media_type: string;
  torrent_hash: string;
  torrent_title: string;
  indexer: string;
  quality: string;
  size: number;
  status: string;
  progress: number;
  download_client: string;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export default function ActivityPage() {
  const { data: downloads, isLoading } = useQuery({
    queryKey: ['download-history'],
    queryFn: async () => {
      try {
        const response = await api.get('/download-history', { params: { limit: 50 } });
        return response.data.downloads || [];
      } catch (error) {
        return [];
      }
    },
    refetchInterval: 5000,
  });

  const formatBytes = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  const getStatusBadge = (status: string) => {
    const colors: any = {
      downloading: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
      pending: 'bg-yellow-100 text-yellow-800',
    };

    return (
      <span className={`px-2 py-1 text-xs rounded ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
        {status}
      </span>
    );
  };

  const activeDownloads = downloads?.filter((d: Download) => d.status === 'downloading') || [];
  const completedDownloads = downloads?.filter((d: Download) => d.status === 'completed') || [];
  const failedDownloads = downloads?.filter((d: Download) => d.status === 'failed') || [];

  return (
    <div className="min-h-screen">
      {/* Header Section */}
      <div className="bg-gradient-to-r from-orange-600/10 via-red-600/10 to-pink-600/10 border-b-2 border-border">
        <div className="container mx-auto px-6 py-8">
          <h1 className="text-4xl font-bold mb-2">Activity</h1>
          <p className="text-muted-foreground">Monitor your download progress and history</p>
        </div>
      </div>

      {/* Content Section */}
      <div className="container mx-auto px-6 py-8">
        {isLoading ? (
          <div className="text-center py-12">Loading activity...</div>
        ) : (
          <>
            {activeDownloads.length > 0 && (
              <div className="mb-8">
                <h2 className="text-2xl font-bold mb-4">Active Downloads ({activeDownloads.length})</h2>
                <div className="space-y-3">
                  {activeDownloads.map((download: Download) => (
                    <div key={download.id} className="bg-card text-card-foreground rounded-lg shadow p-4">
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex-1">
                          <h3 className="font-semibold">{download.torrent_title}</h3>
                          <div className="flex gap-3 text-sm text-muted-foreground mt-1">
                            <span className="px-2 py-0.5 bg-muted rounded">{download.indexer}</span>
                            <span>{download.quality}</span>
                            <span>{formatBytes(download.size)}</span>
                          </div>
                        </div>
                        {getStatusBadge(download.status)}
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="flex-1 bg-secondary rounded-full h-2">
                          <div
                            className="bg-primary h-2 rounded-full transition-all"
                            style={{ width: `${download.progress || 0}%` }}
                          />
                        </div>
                        <span className="text-sm font-medium min-w-[4rem] text-right">
                          {(download.progress || 0).toFixed(1)}%
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground mt-2">
                        Started: {formatDate(download.started_at)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {completedDownloads.length > 0 && (
              <div className="mb-8">
                <h2 className="text-2xl font-bold mb-4">Completed ({completedDownloads.length})</h2>
                <div className="space-y-2">
                  {completedDownloads.slice(0, 10).map((download: Download) => (
                    <div key={download.id} className="bg-card text-card-foreground rounded-lg shadow p-4">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <h3 className="font-semibold text-sm">{download.torrent_title}</h3>
                          <div className="flex gap-3 text-xs text-muted-foreground mt-1">
                            <span className="px-2 py-0.5 bg-muted rounded">{download.indexer}</span>
                            <span>{download.quality}</span>
                            <span>{formatBytes(download.size)}</span>
                            <span>Completed: {formatDate(download.completed_at || '')}</span>
                          </div>
                        </div>
                        {getStatusBadge(download.status)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {failedDownloads.length > 0 && (
              <div className="mb-8">
                <h2 className="text-2xl font-bold mb-4">Failed ({failedDownloads.length})</h2>
                <div className="space-y-2">
                  {failedDownloads.map((download: Download) => (
                    <div key={download.id} className="bg-card text-card-foreground rounded-lg shadow p-4">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <h3 className="font-semibold text-sm">{download.torrent_title}</h3>
                          {download.error_message && (
                            <p className="text-xs text-destructive mt-1">{download.error_message}</p>
                          )}
                          <div className="flex gap-3 text-xs text-muted-foreground mt-1">
                            <span className="px-2 py-0.5 bg-muted rounded">{download.indexer}</span>
                            <span>{formatDate(download.started_at)}</span>
                          </div>
                        </div>
                        {getStatusBadge(download.status)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {downloads && downloads.length === 0 && (
              <div className="bg-card text-card-foreground rounded-lg shadow p-12 text-center">
                <h2 className="text-2xl font-bold mb-4">No Download Activity</h2>
                <p className="text-muted-foreground">
                  Downloads will appear here once you start adding media to your library
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
