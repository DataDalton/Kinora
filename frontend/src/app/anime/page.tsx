'use client';

import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Search, Plus, Upload, Check } from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';
import LibraryImportModal from '@/components/LibraryImportModal';
import PageHeader from '@/components/PageHeader';
import BulkSelectionToolbar from '@/components/BulkSelectionToolbar';

interface Tag {
  id: number;
  name: string;
  color: string | null;
}

interface Anime {
  id: number;
  title: string;
  original_title: string;
  overview: string;
  poster_path: string | null;
  release_date: string;
  rating: number;
  status: string;
  monitored: boolean;
  episodes: number;
  season_year: number;
  has_file: boolean;
  tags?: Tag[];
  season_count?: number;
}

export default function AnimePage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showImportModal, setShowImportModal] = useState(false);
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['anime', page, statusFilter],
    queryFn: async () => {
      const params: any = { page, limit: 20 };
      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }
      const response = await api.get('/anime', { params });
      return response.data;
    },
  });

  const getPosterUrl = (path: string | null) => {
    if (!path) return '/placeholder-poster.svg';
    if (path.startsWith('http')) return path;
    return `https://image.tmdb.org/t/p/w500${path}`;
  };

  const getStatusBadge = (status: string, hasFile: boolean) => {
    if (hasFile) {
      return <span className="px-2 py-1 text-xs rounded bg-green-500/20 text-green-400 border border-green-500/50 font-medium">Downloaded</span>;
    }
    if (status === 'downloading') {
      return <span className="px-2 py-1 text-xs rounded bg-blue-500/20 text-blue-400 border border-blue-500/50 font-medium">Downloading</span>;
    }
    if (status === 'wanted') {
      return <span className="px-2 py-1 text-xs rounded bg-yellow-500/20 text-yellow-400 border border-yellow-500/50 font-medium">Wanted</span>;
    }
    return <span className="px-2 py-1 text-xs rounded bg-gray-500/20 text-gray-400 border border-gray-500/50 font-medium">{status}</span>;
  };

  const filteredAnime = data?.anime?.filter((anime: Anime) =>
    anime.title.toLowerCase().includes(searchQuery.toLowerCase())
  ) || [];

  const totalItems = data?.total || 0;
  const limit = 20;
  const totalPages = totalItems > 0 ? Math.ceil(totalItems / limit) : 1;

  const handleToggleSelection = (animeId: number) => {
    setSelectedIds(prev =>
      prev.includes(animeId)
        ? prev.filter(id => id !== animeId)
        : [...prev, animeId]
    );
  };

  const handleSelectAll = () => {
    setSelectedIds(filteredAnime.map((a: Anime) => a.id));
  };

  const handleDeselectAll = () => {
    setSelectedIds([]);
  };

  const handleSelectionModeToggle = () => {
    setIsSelectionMode(!isSelectionMode);
    if (isSelectionMode) {
      setSelectedIds([]);
    }
  };

  const handleOperationComplete = () => {
    setIsSelectionMode(false);
    setSelectedIds([]);
    queryClient.invalidateQueries({ queryKey: ['anime'] });
  };

  const handleSelectByTag = (ids: number[]) => {
    setSelectedIds(ids);
  };

  return (
    <div className="min-h-screen">
      <PageHeader
        title="Anime"
        description="Manage and track your anime collection"
        gradientFrom="pink-600/10"
        gradientVia="purple-600/10"
        gradientTo="red-600/10"
      />

      {/* Content Section */}
      <div className="container mx-auto px-6 py-8">
        {/* Search and Actions Bar */}
        <div className="flex flex-col md:flex-row gap-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search your anime library..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-12 pr-4 py-3 bg-card border-2 border-border rounded-lg focus:outline-none focus:border-primary transition-colors"
            />
          </div>
          <button
            onClick={() => setShowImportModal(true)}
            className="flex items-center gap-2 px-6 py-3 bg-card border-2 border-border text-foreground rounded-lg hover:bg-accent transition font-medium whitespace-nowrap cursor-pointer"
          >
            <Upload className="w-5 h-5" />
            Import Library
          </button>
          <Link
            href="/search?type=anime"
            className="flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium whitespace-nowrap"
          >
            <Plus className="w-5 h-5" />
            Add New Anime
          </Link>
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-2 flex-wrap mb-6">
          <button
            onClick={() => setStatusFilter('all')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition cursor-pointer ${
              statusFilter === 'all'
                ? 'bg-primary text-primary-foreground shadow-lg'
                : 'bg-card text-foreground hover:bg-accent'
            }`}
          >
            All
            {data?.anime && <span className="text-xs opacity-75">({data.anime.length})</span>}
          </button>
          <button
            onClick={() => setStatusFilter('wanted')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition cursor-pointer ${
              statusFilter === 'wanted'
                ? 'bg-primary text-primary-foreground shadow-lg'
                : 'bg-card text-foreground hover:bg-accent'
            }`}
          >
            Wanted
          </button>
          <button
            onClick={() => setStatusFilter('downloading')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition cursor-pointer ${
              statusFilter === 'downloading'
                ? 'bg-primary text-primary-foreground shadow-lg'
                : 'bg-card text-foreground hover:bg-accent'
            }`}
          >
            Downloading
          </button>
        </div>

        {/* Bulk Selection Toolbar */}
        <div className="mb-6">
          <BulkSelectionToolbar
            mediaType="anime"
            selectedIds={selectedIds}
            totalCount={filteredAnime.length}
            onSelectAll={handleSelectAll}
            onDeselectAll={handleDeselectAll}
            onSelectionModeToggle={handleSelectionModeToggle}
            isSelectionMode={isSelectionMode}
            onOperationComplete={handleOperationComplete}
            items={filteredAnime}
            onSelectByTag={handleSelectByTag}
          />
        </div>

        {isLoading ? (
          <div className="text-center py-12">Loading anime...</div>
        ) : filteredAnime.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No anime found matching your search.</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
              {filteredAnime.map((anime: Anime) => {
                const isSelected = selectedIds.includes(anime.id);
                const CardWrapper = isSelectionMode ? 'div' : Link;
                const cardProps = isSelectionMode
                  ? {
                      onClick: () => handleToggleSelection(anime.id),
                    }
                  : {
                      href: `/anime/${anime.id}`,
                    };

                return (
                  <CardWrapper
                    key={anime.id}
                    {...(cardProps as any)}
                    className={`bg-card text-card-foreground rounded-lg shadow border-2 overflow-hidden hover:shadow-lg transition cursor-pointer ${
                      isSelected
                        ? 'border-primary ring-2 ring-primary/50'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    <div className="relative aspect-2/3">
                      <Image
                        src={getPosterUrl(anime.poster_path)}
                        alt={anime.title}
                        fill
                        sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw"
                        className="object-cover"
                      />
                      {isSelectionMode && (
                        <div className="absolute top-2 left-2">
                          <div
                            className={`w-6 h-6 rounded border-2 flex items-center justify-center transition ${
                              isSelected
                                ? 'bg-primary border-primary'
                                : 'bg-black/50 border-white/50'
                            }`}
                          >
                            {isSelected && <Check className="w-4 h-4 text-white" />}
                          </div>
                        </div>
                      )}
                      {anime.monitored && (
                        <div className="absolute top-2 right-2 bg-primary text-primary-foreground p-1 rounded">
                          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
                            <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd"/>
                          </svg>
                        </div>
                      )}
                      {isSelectionMode && (
                        <div className="absolute inset-0 bg-black/20 pointer-events-none" />
                      )}
                    </div>
                    <div className="p-3">
                      <h3 className="font-semibold text-sm truncate" title={anime.title}>
                        {anime.title}
                      </h3>
                      <div className="flex justify-between items-center mt-2">
                        <span className="text-xs text-muted-foreground">
                          {anime.season_count && anime.season_count > 1
                            ? `${anime.season_count} Seasons`
                            : anime.episodes
                              ? `${anime.episodes} eps`
                              : anime.season_year || 'N/A'}
                        </span>
                        {getStatusBadge(anime.status, anime.has_file)}
                      </div>
                      {anime.rating && (
                        <div className="mt-2 flex items-center text-xs">
                          <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
                          </svg>
                          {anime.rating.toFixed(1)}
                        </div>
                      )}
                      {anime.tags && anime.tags.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {anime.tags.slice(0, 2).map((tag) => (
                            <span
                              key={tag.id}
                              className="px-1.5 py-0.5 text-xs rounded"
                              style={{
                                backgroundColor: tag.color ? `${tag.color}20` : 'rgba(var(--primary), 0.2)',
                                color: tag.color || 'rgb(var(--primary))',
                                border: `1px solid ${tag.color || 'rgb(var(--primary))'}40`,
                              }}
                            >
                              {tag.name}
                            </span>
                          ))}
                          {anime.tags.length > 2 && (
                            <span className="px-1.5 py-0.5 text-xs rounded bg-muted text-muted-foreground">
                              +{anime.tags.length - 2}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </CardWrapper>
                );
              })}
            </div>

            <div className="mt-8 flex flex-col items-center gap-2">
              <div className="flex justify-center gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-4 py-2 bg-card border border-border text-foreground rounded-lg disabled:opacity-50 hover:bg-accent transition cursor-pointer"
                >
                  Previous
                </button>
                <span className="px-4 py-2 text-muted-foreground">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => setPage(p => p + 1)}
                  disabled={page >= totalPages}
                  className="px-4 py-2 bg-card border border-border text-foreground rounded-lg disabled:opacity-50 hover:bg-accent transition cursor-pointer"
                >
                  Next
                </button>
              </div>
              {totalItems > 0 && (
                <span className="text-sm text-muted-foreground">
                  Showing {filteredAnime.length} of {totalItems} anime
                </span>
              )}
            </div>
          </>
        )}
      </div>

      {/* Library Import Modal */}
      <LibraryImportModal
        isOpen={showImportModal}
        onClose={() => setShowImportModal(false)}
        mediaType="anime"
      />
    </div>
  );
}
