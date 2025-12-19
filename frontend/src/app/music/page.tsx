'use client';

import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Search, Plus, Music2, Upload, Check } from 'lucide-react';
import Link from 'next/link';
import PageHeader from '@/components/PageHeader';
import LibraryImportModal from '@/components/LibraryImportModal';
import BulkSelectionToolbar from '@/components/BulkSelectionToolbar';

interface Artist {
  id: number;
  name: string;
  picture: string | null;
  picture_medium: string | null;
  picture_big: string | null;
  picture_xl: string | null;
  deezer_id: number;
  monitored: boolean;
  nb_album: number;
  nb_fan: number;
  has_files: boolean;
}

interface Album {
  id: number;
  title: string;
  cover: string | null;
  cover_medium: string | null;
  cover_big: string | null;
  cover_xl: string | null;
  release_date: string;
  deezer_id: number;
  artist_id: number;
  artist_name: string;
  nb_tracks: number;
  status: string;
  monitored: boolean;
  has_file: boolean;
}

export default function MusicPage() {
  const [view, setView] = useState<'artists' | 'albums'>('artists');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showImportModal, setShowImportModal] = useState(false);
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const queryClient = useQueryClient();

  const { data: artistsData, isLoading: artistsLoading } = useQuery({
    queryKey: ['artists'],
    queryFn: async () => {
      const response = await api.get('/music/artists');
      return response.data;
    },
  });

  const { data: albumsData, isLoading: albumsLoading } = useQuery({
    queryKey: ['albums'],
    queryFn: async () => {
      const response = await api.get('/music/albums');
      return response.data;
    },
  });

  const getPictureUrl = (artist: Artist) => {
    return artist.picture_xl || artist.picture_big || artist.picture_medium || artist.picture || '/placeholder-poster.jpg';
  };

  const getCoverUrl = (album: Album) => {
    return album.cover_xl || album.cover_big || album.cover_medium || album.cover || '/placeholder-poster.jpg';
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

  const filteredArtists = artistsData?.filter((artist: Artist) => {
    const matchesSearch = artist.name.toLowerCase().includes(searchQuery.toLowerCase());
    if (!matchesSearch) return false;

    if (statusFilter === 'all') return true;

    // For wanted/downloading, check if artist has albums with that status
    const artistAlbums = albumsData?.filter((a: Album) => a.artist_id === artist.id) || [];
    if (statusFilter === 'wanted') {
      return artistAlbums.some((a: Album) => a.status === 'wanted' && !a.has_file);
    }
    if (statusFilter === 'downloading') {
      return artistAlbums.some((a: Album) => a.status === 'downloading');
    }

    return true;
  }) || [];

  const filteredAlbums = albumsData?.filter((album: Album) => {
    const matchesSearch = album.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      album.artist_name?.toLowerCase().includes(searchQuery.toLowerCase());
    if (!matchesSearch) return false;

    if (statusFilter === 'all') return true;
    if (statusFilter === 'wanted') return album.status === 'wanted' && !album.has_file;
    if (statusFilter === 'downloading') return album.status === 'downloading';

    return true;
  }) || [];

  const isLoading = view === 'artists' ? artistsLoading : albumsLoading;
  const items = view === 'artists' ? filteredArtists : filteredAlbums;

  const handleToggleSelection = (itemId: number) => {
    setSelectedIds(prev =>
      prev.includes(itemId)
        ? prev.filter(id => id !== itemId)
        : [...prev, itemId]
    );
  };

  const handleSelectAll = () => {
    if (view === 'artists') {
      setSelectedIds(filteredArtists.map((a: Artist) => a.id));
    } else {
      setSelectedIds(filteredAlbums.map((a: Album) => a.id));
    }
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
    queryClient.invalidateQueries({ queryKey: ['artists'] });
    queryClient.invalidateQueries({ queryKey: ['albums'] });
  };

  const handleViewChange = (newView: 'artists' | 'albums') => {
    setView(newView);
    setSelectedIds([]);
    setIsSelectionMode(false);
  };

  return (
    <div className="min-h-screen">
      <PageHeader
        title="Music"
        description="Manage and track your music collection"
        gradientFrom="purple-600/10"
        gradientVia="pink-600/10"
        gradientTo="rose-600/10"
      />

      {/* Content Section */}
      <div className="container mx-auto px-6 py-8">
        {/* Search and Actions Bar */}
        <div className="flex flex-col md:flex-row gap-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <input
              type="text"
              placeholder={`Search your ${view === 'artists' ? 'artists' : 'albums'}...`}
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
            href="/search?type=music"
            className="flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium whitespace-nowrap"
          >
            <Plus className="w-5 h-5" />
            Add Music
          </Link>
        </div>

        {/* View Toggle and Status Filter */}
        <div className="flex flex-col md:flex-row gap-4 mb-6">
          {/* View Toggle */}
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => handleViewChange('artists')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition cursor-pointer ${
                view === 'artists'
                  ? 'bg-primary text-primary-foreground shadow-lg'
                  : 'bg-card text-foreground hover:bg-accent'
              }`}
            >
              Artists
              {artistsData && <span className="text-xs opacity-75">({filteredArtists.length})</span>}
            </button>
            <button
              onClick={() => handleViewChange('albums')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition cursor-pointer ${
                view === 'albums'
                  ? 'bg-primary text-primary-foreground shadow-lg'
                  : 'bg-card text-foreground hover:bg-accent'
              }`}
            >
              Albums
              {albumsData && <span className="text-xs opacity-75">({filteredAlbums.length})</span>}
            </button>
          </div>

          {/* Divider */}
          <div className="hidden md:block w-px bg-border" />

          {/* Status Filter */}
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setStatusFilter('all')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition cursor-pointer ${
                statusFilter === 'all'
                  ? 'bg-primary text-primary-foreground shadow-lg'
                  : 'bg-card text-foreground hover:bg-accent'
              }`}
            >
              All
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
        </div>

        {/* Bulk Selection Toolbar */}
        <div className="mb-6">
          <BulkSelectionToolbar
            mediaType={view === 'artists' ? 'artist' : 'album'}
            selectedIds={selectedIds}
            totalCount={items.length}
            onSelectAll={handleSelectAll}
            onDeselectAll={handleDeselectAll}
            onSelectionModeToggle={handleSelectionModeToggle}
            isSelectionMode={isSelectionMode}
            onOperationComplete={handleOperationComplete}
          />
        </div>

        {isLoading ? (
          <div className="text-center py-12">Loading {view}...</div>
        ) : items.length === 0 ? (
          <div className="text-center py-12">
            <Music2 className="w-16 h-16 mx-auto mb-4 text-muted-foreground opacity-50" />
            <p className="text-muted-foreground mb-4">No {view} found in your library.</p>
            <Link
              href="/search?type=music"
              className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium"
            >
              <Plus className="w-5 h-5" />
              Add Your First {view === 'artists' ? 'Artist' : 'Album'}
            </Link>
          </div>
        ) : (
          <>
            {view === 'artists' ? (
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                {filteredArtists.map((artist: Artist) => {
                  const isSelected = selectedIds.includes(artist.id);
                  const CardWrapper = isSelectionMode ? 'div' : Link;
                  const cardProps = isSelectionMode
                    ? {
                        onClick: () => handleToggleSelection(artist.id),
                      }
                    : {
                        href: `/music/artist/${artist.id}`,
                      };

                  return (
                    <CardWrapper
                      key={artist.id}
                      {...(cardProps as any)}
                      className={`bg-card text-card-foreground rounded-lg shadow border-2 overflow-hidden hover:shadow-lg transition cursor-pointer ${
                        isSelected
                          ? 'border-primary ring-2 ring-primary/50'
                          : 'border-border hover:border-primary/50'
                      }`}
                    >
                      <div className="relative aspect-square">
                        <img
                          src={getPictureUrl(artist)}
                          alt={artist.name}
                          className="w-full h-full object-cover"
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
                        {artist.monitored && (
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
                        <h3 className="font-semibold text-sm truncate" title={artist.name}>
                          {artist.name}
                        </h3>
                        <div className="flex justify-between items-center mt-2">
                          <span className="text-xs text-muted-foreground">
                            {artist.nb_album} {artist.nb_album === 1 ? 'album' : 'albums'}
                          </span>
                          {artist.has_files && (
                            <span className="px-2 py-1 text-xs rounded bg-green-500/20 text-green-400 border border-green-500/50 font-medium">
                              Downloaded
                            </span>
                          )}
                        </div>
                        {artist.nb_fan && (
                          <div className="mt-2 text-xs text-muted-foreground">
                            {artist.nb_fan.toLocaleString()} fans
                          </div>
                        )}
                      </div>
                    </CardWrapper>
                  );
                })}
              </div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                {filteredAlbums.map((album: Album) => {
                  const isSelected = selectedIds.includes(album.id);
                  const CardWrapper = isSelectionMode ? 'div' : Link;
                  const cardProps = isSelectionMode
                    ? {
                        onClick: () => handleToggleSelection(album.id),
                      }
                    : {
                        href: `/music/album/${album.id}`,
                      };

                  return (
                    <CardWrapper
                      key={album.id}
                      {...(cardProps as any)}
                      className={`bg-card text-card-foreground rounded-lg shadow border-2 overflow-hidden hover:shadow-lg transition cursor-pointer ${
                        isSelected
                          ? 'border-primary ring-2 ring-primary/50'
                          : 'border-border hover:border-primary/50'
                      }`}
                    >
                      <div className="relative aspect-square">
                        <img
                          src={getCoverUrl(album)}
                          alt={album.title}
                          className="w-full h-full object-cover"
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
                        {album.monitored && (
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
                        <h3 className="font-semibold text-sm truncate" title={album.title}>
                          {album.title}
                        </h3>
                        <p className="text-xs text-muted-foreground truncate mt-1" title={album.artist_name}>
                          {album.artist_name}
                        </p>
                        <div className="flex justify-between items-center mt-2">
                          <span className="text-xs text-muted-foreground">
                            {album.release_date ? new Date(album.release_date).getFullYear() : 'N/A'}
                          </span>
                          {getStatusBadge(album.status, album.has_file)}
                        </div>
                        {album.nb_tracks && (
                          <div className="mt-2 text-xs text-muted-foreground">
                            {album.nb_tracks} tracks
                          </div>
                        )}
                      </div>
                    </CardWrapper>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>

      {/* Library Import Modal */}
      <LibraryImportModal
        isOpen={showImportModal}
        onClose={() => setShowImportModal(false)}
        mediaType="music"
      />
    </div>
  );
}
