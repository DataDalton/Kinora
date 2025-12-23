'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  ArrowLeft,
  Download,
  Eye,
  EyeOff,
  Music2,
  Plus,
  Calendar,
  Disc3,
  Trash2,
  RefreshCw,
  Search,
  ExternalLink,
  Filter,
} from 'lucide-react';
import Link from 'next/link';
import PageHeader from '@/components/PageHeader';
import ConfirmModal from '@/components/ConfirmModal';
import DeleteConfirmModal from '@/components/DeleteConfirmModal';
import InteractiveSearchModal from '@/components/InteractiveSearchModal';
import MonitoringOptionsDropdown from '@/components/MonitoringOptionsDropdown';
import DownloadHistoryPanel from '@/components/DownloadHistoryPanel';
import TagsEditor from '@/components/TagsEditor';

interface Artist {
  id: number;
  name: string;
  picture: string | null;
  picture_medium: string | null;
  picture_big: string | null;
  picture_xl: string | null;
  deezer_id: number;
  monitored: boolean;
  upgrade_allowed: boolean | null;
  nb_album: number;
  nb_fan: number;
  has_files: boolean;
  root_folder_path: string | null;
  created_at: string;
  updated_at: string;
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
  record_type?: string;
  explicit_lyrics?: boolean;
}

interface DiscographyAlbum {
  deezer_id: number;
  title: string;
  cover: string | null;
  cover_medium: string | null;
  cover_big: string | null;
  cover_xl: string | null;
  release_date: string | null;
  nb_tracks: number | null;
  record_type: string | null;
  explicit_lyrics: boolean;
  in_library: boolean;
  library_id: number | null;
  status: string | null;
  monitored: boolean;
  has_file: boolean;
}

type RecordTypeFilter = 'all' | 'album' | 'single' | 'ep' | 'compilation';
type AlbumView = 'library' | 'all';

export default function ArtistDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const artistId = params?.id as string;

  const [downloadingAlbumId, setDownloadingAlbumId] = useState<number | null>(null);
  const [addingAlbumId, setAddingAlbumId] = useState<number | null>(null);
  const [showDiscographyModal, setShowDiscographyModal] = useState(false);
  const [showDownloadAllModal, setShowDownloadAllModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showInteractiveSearch, setShowInteractiveSearch] = useState(false);
  const [recordTypeFilter, setRecordTypeFilter] = useState<RecordTypeFilter>('all');
  const [albumView, setAlbumView] = useState<AlbumView>('all');

  const { data: artist, isLoading: artistLoading } = useQuery({
    queryKey: ['artist', artistId],
    queryFn: async () => {
      const response = await api.get(`/music/artists/${artistId}`);
      return response.data as Artist;
    },
    enabled: !!artistId,
  });

  const { data: albums, isLoading: albumsLoading } = useQuery({
    queryKey: ['albums', artistId, recordTypeFilter],
    queryFn: async () => {
      let url = `/music/artists/${artistId}/albums`;
      if (recordTypeFilter !== 'all') {
        url += `?record_type=${recordTypeFilter}`;
      }
      const response = await api.get(url);
      return response.data as Album[];
    },
    enabled: !!artistId && albumView === 'library',
  });

  const { data: discography, isLoading: discographyLoading } = useQuery({
    queryKey: ['discography', artistId, recordTypeFilter],
    queryFn: async () => {
      let url = `/music/artists/${artistId}/discography`;
      if (recordTypeFilter !== 'all') {
        url += `?record_type=${recordTypeFilter}`;
      }
      const response = await api.get(url);
      return response.data as DiscographyAlbum[];
    },
    enabled: !!artistId && albumView === 'all',
  });

  const toggleMonitoredMutation = useMutation({
    mutationFn: async (monitored: boolean) => {
      const response = await api.put(`/music/artists/${artistId}`, { monitored });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['artist', artistId] });
      queryClient.invalidateQueries({ queryKey: ['artists'] });
    },
  });

  const addDiscographyMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/music/artists/${artistId}/add-discography`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['albums', artistId] });
      queryClient.invalidateQueries({ queryKey: ['albums'] });
    },
  });

  const downloadAllWantedMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/music/artists/${artistId}/search-download-all`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['albums', artistId] });
    },
  });

  const downloadAlbumMutation = useMutation({
    mutationFn: async (albumId: number) => {
      const response = await api.post(`/music/albums/${albumId}/search-download`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['albums', artistId] });
      setDownloadingAlbumId(null);
    },
    onError: () => {
      setDownloadingAlbumId(null);
    },
  });

  const refreshMetadataMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/music/artists/${artistId}/refresh-metadata`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['artist', artistId] });
    },
  });

  const deleteArtistMutation = useMutation({
    mutationFn: async (deleteFiles: boolean) => {
      const response = await api.delete(`/music/artists/${artistId}/delete?delete_files=${deleteFiles}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['artists'] });
      router.push('/music');
    },
  });

  const monitorAllAlbumsMutation = useMutation({
    mutationFn: async (monitored: boolean) => {
      const response = await api.put(`/music/artists/${artistId}/monitor-all-albums?monitored=${monitored}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['albums', artistId] });
      queryClient.invalidateQueries({ queryKey: ['discography', artistId] });
    },
  });

  const addAlbumMutation = useMutation({
    mutationFn: async (album: DiscographyAlbum) => {
      const response = await api.post('/music/albums', {
        title: album.title,
        cover: album.cover,
        cover_medium: album.cover_medium,
        cover_big: album.cover_big,
        cover_xl: album.cover_xl,
        release_date: album.release_date,
        deezer_id: album.deezer_id,
        artist_id: parseInt(artistId),
        nb_tracks: album.nb_tracks,
        record_type: album.record_type,
        explicit_lyrics: album.explicit_lyrics,
        monitored: true,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['albums', artistId] });
      queryClient.invalidateQueries({ queryKey: ['discography', artistId] });
      setAddingAlbumId(null);
    },
    onError: () => {
      setAddingAlbumId(null);
    },
  });

  const getPictureUrl = (artist: Artist) => {
    return artist.picture_xl || artist.picture_big || artist.picture_medium || artist.picture || '/placeholder-poster.jpg';
  };

  const getCoverUrl = (album: Album | DiscographyAlbum) => {
    return album.cover_xl || album.cover_big || album.cover_medium || album.cover || '/placeholder-poster.jpg';
  };

  const handleAddAlbum = (album: DiscographyAlbum) => {
    setAddingAlbumId(album.deezer_id);
    addAlbumMutation.mutate(album);
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

  const handleToggleMonitored = () => {
    if (artist) {
      toggleMonitoredMutation.mutate(!artist.monitored);
    }
  };

  const handleAddDiscography = () => {
    setShowDiscographyModal(true);
  };

  const handleConfirmDiscography = () => {
    setShowDiscographyModal(false);
    addDiscographyMutation.mutate();
  };

  const handleDownloadAllWanted = () => {
    setShowDownloadAllModal(true);
  };

  const handleConfirmDownloadAll = () => {
    setShowDownloadAllModal(false);
    downloadAllWantedMutation.mutate();
  };

  const handleDownloadAlbum = (albumId: number) => {
    setDownloadingAlbumId(albumId);
    downloadAlbumMutation.mutate(albumId);
  };

  const handleDeleteConfirm = (deleteFiles: boolean) => {
    setShowDeleteModal(false);
    deleteArtistMutation.mutate(deleteFiles);
  };

  const handleMonitoringUpdate = (newState: { monitored: boolean; upgradeAllowed: boolean | null }) => {
    queryClient.invalidateQueries({ queryKey: ['artist', artistId] });
  };

  if (artistLoading) {
    return (
      <div className="min-h-screen">
        <PageHeader
          title="Loading..."
          description="Loading artist details"
          gradientFrom="purple-600/10"
          gradientVia="pink-600/10"
          gradientTo="rose-600/10"
        />
        <div className="container mx-auto px-6 py-8">
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        </div>
      </div>
    );
  }

  if (!artist) {
    return (
      <div className="min-h-screen">
        <PageHeader
          title="Not Found"
          description="Artist not found"
          gradientFrom="purple-600/10"
          gradientVia="pink-600/10"
          gradientTo="rose-600/10"
        />
        <div className="container mx-auto px-6 py-8">
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">Artist not found</p>
            <Link
              href="/music"
              className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium"
            >
              <ArrowLeft className="w-5 h-5" />
              Back to Music
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const libraryAlbums = albumView === 'library' ? albums : discography?.filter(a => a.in_library);
  const wantedAlbumsCount = libraryAlbums?.filter(a => a.status === 'wanted' && a.monitored).length || 0;
  const monitoredAlbumsCount = libraryAlbums?.filter(a => a.monitored).length || 0;
  const downloadedAlbumsCount = libraryAlbums?.filter(a => a.has_file).length || 0;
  const inLibraryCount = discography?.filter(a => a.in_library).length || 0;
  const totalDiscographyCount = discography?.length || 0;

  const recordTypeFilters: { value: RecordTypeFilter; label: string }[] = [
    { value: 'all', label: 'All' },
    { value: 'album', label: 'Albums' },
    { value: 'single', label: 'Singles' },
    { value: 'ep', label: 'EPs' },
    { value: 'compilation', label: 'Compilations' },
  ];

  return (
    <div className="min-h-screen">
      <PageHeader
        title={artist.name}
        description={`${artist.nb_album || 0} ${artist.nb_album === 1 ? 'album' : 'albums'} • ${artist.nb_fan?.toLocaleString() || 0} fans`}
        gradientFrom="purple-600/10"
        gradientVia="pink-600/10"
        gradientTo="rose-600/10"
      >
        <Link
          href="/music"
          className="flex items-center gap-2 px-4 py-2 bg-card text-foreground rounded-lg hover:bg-accent transition font-medium border-2 border-border cursor-pointer"
        >
          <ArrowLeft className="w-5 h-5" />
          Back
        </Link>
      </PageHeader>

      <div className="container mx-auto px-6 py-8">
        {/* Artist Info Section */}
        <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6 mb-8">
          <div className="flex flex-col md:flex-row gap-6">
            <div className="flex-shrink-0">
              <img
                src={getPictureUrl(artist)}
                alt={artist.name}
                className="w-48 h-48 object-cover rounded-lg shadow-lg"
              />
            </div>
            <div className="flex-1">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-3xl font-bold mb-2">{artist.name}</h2>
                  <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                    {artist.nb_album && (
                      <div className="flex items-center gap-1">
                        <Disc3 className="w-4 h-4" />
                        {artist.nb_album} {artist.nb_album === 1 ? 'album' : 'albums'}
                      </div>
                    )}
                    {artist.nb_fan && (
                      <div className="flex items-center gap-1">
                        <Music2 className="w-4 h-4" />
                        {artist.nb_fan.toLocaleString()} fans
                      </div>
                    )}
                    {albums && (
                      <div className="flex items-center gap-1">
                        <Download className="w-4 h-4" />
                        {downloadedAlbumsCount}/{albums.length} downloaded
                      </div>
                    )}
                  </div>
                </div>
                <MonitoringOptionsDropdown
                  mediaType="artist"
                  mediaId={artist.id}
                  currentState={{
                    monitored: artist.monitored,
                    upgradeAllowed: artist.upgrade_allowed,
                  }}
                  onUpdate={handleMonitoringUpdate}
                />
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap gap-3 mt-6">
                <button
                  onClick={() => setShowInteractiveSearch(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium cursor-pointer"
                >
                  <Search className="w-5 h-5" />
                  Interactive Search
                </button>
                <button
                  onClick={handleAddDiscography}
                  disabled={addDiscographyMutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-card text-foreground rounded-lg hover:bg-accent transition font-medium border-2 border-border cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Plus className="w-5 h-5" />
                  {addDiscographyMutation.isPending ? 'Adding...' : 'Add Discography'}
                </button>
                {wantedAlbumsCount > 0 && (
                  <button
                    onClick={handleDownloadAllWanted}
                    disabled={downloadAllWantedMutation.isPending}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Download className="w-5 h-5" />
                    {downloadAllWantedMutation.isPending
                      ? 'Downloading...'
                      : `Download Wanted (${wantedAlbumsCount})`}
                  </button>
                )}
                <button
                  onClick={() => refreshMetadataMutation.mutate()}
                  disabled={refreshMetadataMutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-card text-foreground rounded-lg hover:bg-accent transition font-medium border-2 border-border cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <RefreshCw className={`w-5 h-5 ${refreshMetadataMutation.isPending ? 'animate-spin' : ''}`} />
                  Refresh
                </button>
                <button
                  onClick={() => setShowDeleteModal(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-destructive text-destructive-foreground rounded-lg hover:opacity-90 transition font-medium cursor-pointer"
                >
                  <Trash2 className="w-5 h-5" />
                  Delete
                </button>
              </div>

              {/* Batch Album Monitoring */}
              <div className="flex items-center gap-3 mt-4 pt-4 border-t border-border">
                <span className="text-sm text-muted-foreground">Album Monitoring:</span>
                <button
                  onClick={() => monitorAllAlbumsMutation.mutate(true)}
                  disabled={monitorAllAlbumsMutation.isPending}
                  className="flex items-center gap-1 px-3 py-1.5 bg-muted hover:bg-muted/80 rounded-lg transition text-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Eye className="w-4 h-4" />
                  Monitor All
                </button>
                <button
                  onClick={() => monitorAllAlbumsMutation.mutate(false)}
                  disabled={monitorAllAlbumsMutation.isPending}
                  className="flex items-center gap-1 px-3 py-1.5 bg-muted hover:bg-muted/80 rounded-lg transition text-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <EyeOff className="w-4 h-4" />
                  Unmonitor All
                </button>
                <span className="text-sm text-muted-foreground ml-2">
                  {monitoredAlbumsCount}/{albums?.length || 0} monitored
                </span>
              </div>

              {/* Success Messages */}
              {addDiscographyMutation.isSuccess && (
                <div className="mt-4 p-3 bg-green-500/20 text-green-400 border border-green-500/50 rounded-lg">
                  {addDiscographyMutation.data.message}
                </div>
              )}
              {downloadAllWantedMutation.isSuccess && (
                <div className="mt-4 p-3 bg-green-500/20 text-green-400 border border-green-500/50 rounded-lg">
                  {downloadAllWantedMutation.data.message}
                </div>
              )}
              {refreshMetadataMutation.isSuccess && (
                <div className="mt-4 p-3 bg-green-500/20 text-green-400 border border-green-500/50 rounded-lg">
                  Metadata refreshed successfully
                </div>
              )}
            </div>
          </div>
        </div>

        {/* External Links & Tags Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* External Links */}
          <div className="bg-muted/30 rounded-lg border border-border p-4">
            <h4 className="font-medium mb-3 flex items-center gap-2">
              <ExternalLink className="w-5 h-5 text-muted-foreground" />
              External Links
            </h4>
            <div className="flex flex-wrap gap-2">
              {artist.deezer_id && (
                <a
                  href={`https://www.deezer.com/artist/${artist.deezer_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-3 py-2 bg-background hover:bg-muted rounded-lg transition text-sm cursor-pointer"
                >
                  <img src="https://www.deezer.com/favicon.ico" alt="Deezer" className="w-4 h-4" />
                  Deezer
                  <ExternalLink className="w-3 h-3 text-muted-foreground" />
                </a>
              )}
              <a
                href={`https://www.last.fm/music/${encodeURIComponent(artist.name)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-3 py-2 bg-background hover:bg-muted rounded-lg transition text-sm cursor-pointer"
              >
                <img src="https://www.last.fm/static/images/lastfm_avatar_twitter.52a5d69a85ac.png" alt="Last.fm" className="w-4 h-4 rounded" />
                Last.fm
                <ExternalLink className="w-3 h-3 text-muted-foreground" />
              </a>
              <a
                href={`https://musicbrainz.org/search?query=${encodeURIComponent(artist.name)}&type=artist`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-3 py-2 bg-background hover:bg-muted rounded-lg transition text-sm cursor-pointer"
              >
                <img src="https://musicbrainz.org/static/images/favicons/favicon-32x32.png" alt="MusicBrainz" className="w-4 h-4" />
                MusicBrainz
                <ExternalLink className="w-3 h-3 text-muted-foreground" />
              </a>
            </div>
          </div>

          {/* Tags */}
          <TagsEditor
            mediaType="artist"
            mediaId={artist.id}
          />
        </div>

        {/* Download History */}
        <div className="mb-8">
          <DownloadHistoryPanel
            mediaType="album"
            mediaId={artist.id}
          />
        </div>

        {/* Albums Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
          <div>
            <h3 className="text-2xl font-bold">Discography</h3>
            <p className="text-muted-foreground">
              {albumView === 'all'
                ? `${inLibraryCount} of ${totalDiscographyCount} albums in library`
                : `${albums?.length || 0} ${albums?.length === 1 ? 'album' : 'albums'} in library`}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            {/* View Toggle */}
            <div className="flex items-center bg-muted rounded-lg p-1">
              <button
                onClick={() => setAlbumView('all')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition cursor-pointer ${
                  albumView === 'all'
                    ? 'bg-primary text-primary-foreground'
                    : 'hover:bg-background'
                }`}
              >
                All Albums
              </button>
              <button
                onClick={() => setAlbumView('library')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition cursor-pointer ${
                  albumView === 'library'
                    ? 'bg-primary text-primary-foreground'
                    : 'hover:bg-background'
                }`}
              >
                In Library
              </button>
            </div>

            {/* Record Type Filter */}
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-muted-foreground" />
              <div className="flex items-center bg-muted rounded-lg p-1">
                {recordTypeFilters.map((filter) => (
                  <button
                    key={filter.value}
                    onClick={() => setRecordTypeFilter(filter.value)}
                    className={`px-3 py-1.5 rounded-md text-sm font-medium transition cursor-pointer ${
                      recordTypeFilter === filter.value
                        ? 'bg-primary text-primary-foreground'
                        : 'hover:bg-background'
                    }`}
                  >
                    {filter.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {(albumView === 'library' ? albumsLoading : discographyLoading) ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : albumView === 'library' ? (
          /* Library View */
          !albums || albums.length === 0 ? (
            <div className="text-center py-12">
              <Disc3 className="w-16 h-16 mx-auto mb-4 text-muted-foreground opacity-50" />
              <p className="text-muted-foreground mb-4">
                {recordTypeFilter !== 'all'
                  ? `No ${recordTypeFilter}s found for this artist.`
                  : 'No albums found in library for this artist.'}
              </p>
              {recordTypeFilter === 'all' && (
                <button
                  onClick={handleAddDiscography}
                  disabled={addDiscographyMutation.isPending}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Plus className="w-5 h-5" />
                  {addDiscographyMutation.isPending ? 'Adding...' : 'Add Full Discography'}
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
              {albums.map((album) => (
                <div
                  key={album.id}
                  className="bg-card text-card-foreground rounded-lg shadow border-2 border-border overflow-hidden hover:shadow-lg hover:border-primary/50 transition group"
                >
                  <Link href={`/music/album/${album.id}`}>
                    <div className="relative aspect-square">
                      <img
                        src={getCoverUrl(album)}
                        alt={album.title}
                        className="w-full h-full object-cover"
                      />
                      {album.monitored && (
                        <div className="absolute top-2 right-2 bg-primary text-primary-foreground p-1 rounded">
                          <Eye className="w-4 h-4" />
                        </div>
                      )}
                      {!album.has_file && album.status === 'wanted' && (
                        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/60 transition flex items-center justify-center opacity-0 group-hover:opacity-100">
                          <button
                            onClick={(e) => {
                              e.preventDefault();
                              handleDownloadAlbum(album.id);
                            }}
                            disabled={downloadingAlbumId === album.id}
                            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <Download className="w-4 h-4" />
                            {downloadingAlbumId === album.id ? 'Downloading...' : 'Download'}
                          </button>
                        </div>
                      )}
                    </div>
                  </Link>
                  <div className="p-3">
                    <div className="flex items-center gap-1.5">
                      <Link href={`/music/album/${album.id}`} className="flex-1 min-w-0 cursor-pointer">
                        <h3 className="font-semibold text-sm truncate hover:text-primary transition" title={album.title}>
                          {album.title}
                        </h3>
                      </Link>
                      {album.explicit_lyrics && (
                        <div className="px-1.5 py-0.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/50 font-bold shrink-0">
                          E
                        </div>
                      )}
                    </div>
                    <div className="flex justify-between items-center mt-2">
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Calendar className="w-3 h-3" />
                        {album.release_date ? new Date(album.release_date).getFullYear() : 'N/A'}
                      </div>
                      {getStatusBadge(album.status, album.has_file)}
                    </div>
                    <div className="flex justify-between items-center mt-2">
                      {album.nb_tracks && (
                        <div className="text-xs text-muted-foreground">
                          {album.nb_tracks} tracks
                        </div>
                      )}
                      {album.record_type && (
                        <div className="text-xs text-muted-foreground uppercase">
                          {album.record_type}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : (
          /* All Albums View (Discography) */
          !discography || discography.length === 0 ? (
            <div className="text-center py-12">
              <Disc3 className="w-16 h-16 mx-auto mb-4 text-muted-foreground opacity-50" />
              <p className="text-muted-foreground mb-4">
                {recordTypeFilter !== 'all'
                  ? `No ${recordTypeFilter}s found for this artist.`
                  : 'No albums found in discography.'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
              {discography.map((album) => (
                <div
                  key={album.deezer_id}
                  className={`bg-card text-card-foreground rounded-lg shadow border-2 overflow-hidden hover:shadow-lg transition group ${
                    album.in_library ? 'border-border hover:border-primary/50' : 'border-dashed border-muted-foreground/30 hover:border-primary/50'
                  }`}
                >
                  {album.in_library ? (
                    <Link href={`/music/album/${album.library_id}`}>
                      <div className="relative aspect-square">
                        <img
                          src={getCoverUrl(album)}
                          alt={album.title}
                          className="w-full h-full object-cover"
                        />
                        {album.monitored && (
                          <div className="absolute top-2 right-2 bg-primary text-primary-foreground p-1 rounded">
                            <Eye className="w-4 h-4" />
                          </div>
                        )}
                        {!album.has_file && album.status === 'wanted' && (
                          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/60 transition flex items-center justify-center opacity-0 group-hover:opacity-100">
                            <button
                              onClick={(e) => {
                                e.preventDefault();
                                if (album.library_id) handleDownloadAlbum(album.library_id);
                              }}
                              disabled={downloadingAlbumId === album.library_id}
                              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              <Download className="w-4 h-4" />
                              {downloadingAlbumId === album.library_id ? 'Downloading...' : 'Download'}
                            </button>
                          </div>
                        )}
                      </div>
                    </Link>
                  ) : (
                    <div className="relative aspect-square">
                      <img
                        src={getCoverUrl(album)}
                        alt={album.title}
                        className="w-full h-full object-cover opacity-70"
                      />
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/60 transition flex items-center justify-center opacity-0 group-hover:opacity-100">
                        <button
                          onClick={() => handleAddAlbum(album)}
                          disabled={addingAlbumId === album.deezer_id}
                          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          <Plus className="w-4 h-4" />
                          {addingAlbumId === album.deezer_id ? 'Adding...' : 'Add to Library'}
                        </button>
                      </div>
                    </div>
                  )}
                  <div className="p-3">
                    <div className="flex items-center gap-1.5">
                      {album.in_library ? (
                        <Link href={`/music/album/${album.library_id}`} className="flex-1 min-w-0 cursor-pointer">
                          <h3 className="font-semibold text-sm truncate hover:text-primary transition" title={album.title}>
                            {album.title}
                          </h3>
                        </Link>
                      ) : (
                        <h3 className="font-semibold text-sm truncate text-muted-foreground flex-1" title={album.title}>
                          {album.title}
                        </h3>
                      )}
                      {album.explicit_lyrics && (
                        <div className="px-1.5 py-0.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/50 font-bold shrink-0">
                          E
                        </div>
                      )}
                    </div>
                    <div className="flex justify-between items-center mt-2">
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Calendar className="w-3 h-3" />
                        {album.release_date ? new Date(album.release_date).getFullYear() : 'N/A'}
                      </div>
                      {album.in_library ? (
                        getStatusBadge(album.status || 'wanted', album.has_file)
                      ) : (
                        <span className="px-2 py-1 text-xs rounded bg-muted text-muted-foreground font-medium">
                          Not in Library
                        </span>
                      )}
                    </div>
                    <div className="flex justify-between items-center mt-2">
                      {album.nb_tracks && (
                        <div className="text-xs text-muted-foreground">
                          {album.nb_tracks} tracks
                        </div>
                      )}
                      {album.record_type && (
                        <div className="text-xs text-muted-foreground uppercase">
                          {album.record_type}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        )}
      </div>

      {/* Modals */}
      <ConfirmModal
        isOpen={showDiscographyModal}
        title="Add Full Discography"
        message={`This will add all albums from ${artist?.name || 'this artist'} to your library. Continue?`}
        confirmText="Add Discography"
        cancelText="Cancel"
        onConfirm={handleConfirmDiscography}
        onCancel={() => setShowDiscographyModal(false)}
        variant="info"
      />

      <ConfirmModal
        isOpen={showDownloadAllModal}
        title="Download All Wanted"
        message={`This will search and download all wanted albums for ${artist?.name || 'this artist'}. Continue?`}
        confirmText="Download All"
        cancelText="Cancel"
        onConfirm={handleConfirmDownloadAll}
        onCancel={() => setShowDownloadAllModal(false)}
        variant="info"
      />

      <DeleteConfirmModal
        isOpen={showDeleteModal}
        onCancel={() => setShowDeleteModal(false)}
        onConfirm={handleDeleteConfirm}
        title={artist.name}
        itemName="artist"
        hasFiles={artist.has_files}
      />

      <InteractiveSearchModal
        isOpen={showInteractiveSearch}
        onClose={() => setShowInteractiveSearch(false)}
        mediaType="album"
        mediaId={artist.id}
        mediaTitle={artist.name}
        searchQuery={artist.name}
      />
    </div>
  );
}
