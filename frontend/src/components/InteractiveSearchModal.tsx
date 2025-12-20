'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  X,
  Search,
  Download,
  Ban,
  Loader2,
  HardDrive,
  Users,
  Clock,
  Filter,
  SortAsc,
  SortDesc,
  ChevronDown,
} from 'lucide-react';
import Toast from './Toast';

interface TorrentResult {
  title: string;
  size: number;
  seeders: number;
  leechers: number;
  quality: string;
  source: string;
  indexer: string;
  indexer_page_url: string;
  torrent_url: string;
  magnet_link: string;
  info_hash: string;
  upload_date: string;
}

interface InteractiveSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  mediaType: 'movie' | 'show' | 'anime' | 'album';
  mediaId: number;
  mediaTitle: string;
  episodeId?: number;
  episodeInfo?: string;
}

type SortField = 'seeders' | 'size' | 'upload_date' | 'quality';
type SortDirection = 'asc' | 'desc';

const formatSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const qualityOrder: Record<string, number> = {
  '2160p': 1,
  '4K': 1,
  '1080p': 2,
  '720p': 3,
  '480p': 4,
  'HDTV': 5,
  'SDTV': 6,
  'Unknown': 7,
};

export default function InteractiveSearchModal({
  isOpen,
  onClose,
  mediaType,
  mediaId,
  mediaTitle,
  episodeId,
  episodeInfo,
}: InteractiveSearchModalProps) {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState(mediaTitle);
  const [sortField, setSortField] = useState<SortField>('seeders');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [qualityFilter, setQualityFilter] = useState<string>('all');
  const [indexerFilter, setIndexerFilter] = useState<string>('all');
  const [showFilters, setShowFilters] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' | 'info') => {
    setToast(null);
    setTimeout(() => setToast({ message, type }), 0);
  };

  useEffect(() => {
    if (isOpen) {
      setSearchQuery(mediaTitle);
    }
  }, [isOpen, mediaTitle]);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  const { data: searchResults, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['interactive-search', mediaType, mediaId, searchQuery],
    queryFn: async () => {
      const response = await api.post('/search/interactive', {
        query: searchQuery,
        media_type: mediaType,
        media_id: mediaId,
        episode_id: episodeId,
      });
      return response.data.results as TorrentResult[];
    },
    enabled: false,
  });

  const downloadMutation = useMutation({
    mutationFn: async (result: TorrentResult) => {
      const response = await api.post('/search/download-release', {
        torrent_url: result.torrent_url,
        magnet_link: result.magnet_link,
        media_type: mediaType,
        media_id: mediaId,
        episode_id: episodeId,
        indexer: result.indexer,
        indexer_page_url: result.indexer_page_url,
        quality: result.quality,
        size: result.size,
        seeders: result.seeders,
      });
      return response.data;
    },
    onSuccess: () => {
      showToast('Download started successfully', 'success');
      queryClient.invalidateQueries({ queryKey: ['history'] });
    },
    onError: (error: any) => {
      showToast(error.response?.data?.detail || 'Failed to start download', 'error');
    },
  });

  const blocklistMutation = useMutation({
    mutationFn: async (result: TorrentResult) => {
      const response = await api.post('/blocklist', {
        media_type: mediaType,
        media_id: mediaId,
        release_title: result.title,
        reason: 'Manually blocklisted from search',
      });
      return response.data;
    },
    onSuccess: () => {
      showToast('Added to blocklist', 'info');
      queryClient.invalidateQueries({ queryKey: ['blocklist'] });
    },
    onError: (error: any) => {
      showToast(error.response?.data?.detail || 'Failed to add to blocklist', 'error');
    },
  });

  const handleSearch = () => {
    if (searchQuery.trim()) {
      refetch();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const sortResults = (results: TorrentResult[]): TorrentResult[] => {
    return [...results].sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case 'seeders':
          comparison = a.seeders - b.seeders;
          break;
        case 'size':
          comparison = a.size - b.size;
          break;
        case 'upload_date':
          comparison = new Date(a.upload_date).getTime() - new Date(b.upload_date).getTime();
          break;
        case 'quality':
          comparison = (qualityOrder[a.quality] || 99) - (qualityOrder[b.quality] || 99);
          break;
      }
      return sortDirection === 'desc' ? -comparison : comparison;
    });
  };

  const filterResults = (results: TorrentResult[]): TorrentResult[] => {
    return results.filter((r) => {
      if (qualityFilter !== 'all' && r.quality !== qualityFilter) return false;
      if (indexerFilter !== 'all' && r.indexer !== indexerFilter) return false;
      return true;
    });
  };

  const processedResults = searchResults ? sortResults(filterResults(searchResults)) : [];

  const uniqueQualities = searchResults
    ? [...new Set(searchResults.map((r) => r.quality))].filter(Boolean)
    : [];
  const uniqueIndexers = searchResults
    ? [...new Set(searchResults.map((r) => r.indexer))].filter(Boolean)
    : [];

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-[60] flex items-center justify-center p-4">
      <div className="bg-background rounded-lg w-full max-w-5xl max-h-[90vh] border border-border shadow-2xl flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div>
            <h2 className="text-xl font-bold">Interactive Search</h2>
            <p className="text-sm text-muted-foreground">
              {mediaTitle}
              {episodeInfo && <span className="ml-2">{episodeInfo}</span>}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-muted rounded-lg transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 border-b border-border space-y-3">
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Search for releases..."
                className="w-full pl-10 pr-4 py-2 bg-muted border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <button
              onClick={handleSearch}
              disabled={isLoading || isFetching}
              className="px-6 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {(isLoading || isFetching) ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Search className="w-5 h-5" />
              )}
              Search
            </button>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`px-4 py-2 rounded-lg transition cursor-pointer flex items-center gap-2 ${
                showFilters ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-muted/80'
              }`}
            >
              <Filter className="w-5 h-5" />
              <ChevronDown className={`w-4 h-4 transition ${showFilters ? 'rotate-180' : ''}`} />
            </button>
          </div>

          {showFilters && (
            <div className="flex flex-wrap gap-4 pt-2">
              <div className="flex items-center gap-2">
                <label className="text-sm text-muted-foreground">Quality:</label>
                <select
                  value={qualityFilter}
                  onChange={(e) => setQualityFilter(e.target.value)}
                  className="px-3 py-1.5 bg-muted border border-border rounded-lg text-sm"
                >
                  <option value="all">All</option>
                  {uniqueQualities.map((q) => (
                    <option key={q} value={q}>{q}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-sm text-muted-foreground">Indexer:</label>
                <select
                  value={indexerFilter}
                  onChange={(e) => setIndexerFilter(e.target.value)}
                  className="px-3 py-1.5 bg-muted border border-border rounded-lg text-sm"
                >
                  <option value="all">All</option>
                  {uniqueIndexers.map((i) => (
                    <option key={i} value={i}>{i}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-sm text-muted-foreground">Sort by:</label>
                <select
                  value={sortField}
                  onChange={(e) => setSortField(e.target.value as SortField)}
                  className="px-3 py-1.5 bg-muted border border-border rounded-lg text-sm"
                >
                  <option value="seeders">Seeders</option>
                  <option value="size">Size</option>
                  <option value="quality">Quality</option>
                  <option value="upload_date">Date</option>
                </select>
                <button
                  onClick={() => setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')}
                  className="p-1.5 bg-muted rounded-lg hover:bg-muted/80 transition cursor-pointer"
                >
                  {sortDirection === 'desc' ? (
                    <SortDesc className="w-4 h-4" />
                  ) : (
                    <SortAsc className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {isLoading || isFetching ? (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 className="w-10 h-10 animate-spin text-primary mb-4" />
              <p className="text-muted-foreground">Searching indexers...</p>
            </div>
          ) : processedResults.length > 0 ? (
            <div className="space-y-2">
              <div className="text-sm text-muted-foreground mb-3">
                {processedResults.length} results found
                {searchResults && processedResults.length !== searchResults.length && (
                  <span> ({searchResults.length - processedResults.length} filtered)</span>
                )}
              </div>
              {processedResults.map((result, index) => (
                <div
                  key={index}
                  className="bg-muted/50 rounded-lg p-4 border border-border hover:border-primary/50 transition"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <h4 className="font-medium text-sm truncate mb-2" title={result.title}>
                        {result.title}
                      </h4>
                      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <HardDrive className="w-3.5 h-3.5" />
                          {formatSize(result.size)}
                        </span>
                        <span className="flex items-center gap-1 text-green-500">
                          <Users className="w-3.5 h-3.5" />
                          {result.seeders} seeders
                        </span>
                        {result.quality && (
                          <span className="px-2 py-0.5 bg-primary/20 text-primary rounded">
                            {result.quality}
                          </span>
                        )}
                        {result.source && (
                          <span className="px-2 py-0.5 bg-muted rounded">
                            {result.source}
                          </span>
                        )}
                        <span className="flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5" />
                          {result.indexer}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => downloadMutation.mutate(result)}
                        disabled={downloadMutation.isPending}
                        className="p-2 bg-green-600 text-white rounded-lg hover:opacity-90 transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Download"
                      >
                        {downloadMutation.isPending ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Download className="w-4 h-4" />
                        )}
                      </button>
                      <button
                        onClick={() => blocklistMutation.mutate(result)}
                        disabled={blocklistMutation.isPending}
                        className="p-2 bg-destructive text-destructive-foreground rounded-lg hover:opacity-90 transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Add to blocklist"
                      >
                        {blocklistMutation.isPending ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Ban className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : searchResults ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Search className="w-12 h-12 mb-4 opacity-50" />
              <p>No results found</p>
              <p className="text-sm">Try a different search term or adjust filters</p>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Search className="w-12 h-12 mb-4 opacity-50" />
              <p>Click Search to find releases</p>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-border flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2 bg-muted text-foreground rounded-lg hover:opacity-90 transition cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}
