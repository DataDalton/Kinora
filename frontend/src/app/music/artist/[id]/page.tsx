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
  Disc3
} from 'lucide-react';
import Link from 'next/link';
import PageHeader from '@/components/PageHeader';
import ConfirmModal from '@/components/ConfirmModal';

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
}

export default function ArtistDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const artistId = params?.id as string;
  const [downloadingAlbumId, setDownloadingAlbumId] = useState<number | null>(null);
  const [showDiscographyModal, setShowDiscographyModal] = useState(false);
  const [showDownloadAllModal, setShowDownloadAllModal] = useState(false);

  const { data: artist, isLoading: artistLoading } = useQuery({
    queryKey: ['artist', artistId],
    queryFn: async () => {
      const response = await api.get(`/music/artists/${artistId}`);
      return response.data as Artist;
    },
    enabled: !!artistId,
  });

  const { data: albums, isLoading: albumsLoading } = useQuery({
    queryKey: ['albums', artistId],
    queryFn: async () => {
      const response = await api.get(`/music/albums?artist_id=${artistId}`);
      return response.data as Album[];
    },
    enabled: !!artistId,
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
          <div className="text-center py-12">Loading artist...</div>
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

  const wantedAlbumsCount = albums?.filter(a => a.status === 'wanted' && a.monitored).length || 0;

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
          className="flex items-center gap-2 px-4 py-2 bg-card text-foreground rounded-lg hover:bg-accent transition font-medium border-2 border-border"
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
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {artist.monitored ? (
                    <span className="px-3 py-1.5 text-sm rounded bg-primary text-primary-foreground border border-primary font-medium flex items-center gap-2">
                      <Eye className="w-4 h-4" />
                      Monitored
                    </span>
                  ) : (
                    <span className="px-3 py-1.5 text-sm rounded bg-gray-500/20 text-gray-400 border border-gray-500/50 font-medium flex items-center gap-2">
                      <EyeOff className="w-4 h-4" />
                      Not Monitored
                    </span>
                  )}
                  {artist.has_files && (
                    <span className="px-3 py-1.5 text-sm rounded bg-green-500/20 text-green-400 border border-green-500/50 font-medium flex items-center gap-2">
                      <Download className="w-4 h-4" />
                      Has Files
                    </span>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap gap-3 mt-6">
                <button
                  onClick={handleToggleMonitored}
                  disabled={toggleMonitoredMutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-card text-foreground rounded-lg hover:bg-accent transition font-medium border-2 border-border disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {artist.monitored ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  {toggleMonitoredMutation.isPending
                    ? 'Updating...'
                    : artist.monitored
                    ? 'Unmonitor'
                    : 'Monitor'}
                </button>
                <button
                  onClick={handleAddDiscography}
                  disabled={addDiscographyMutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Plus className="w-5 h-5" />
                  {addDiscographyMutation.isPending ? 'Adding...' : 'Add Full Discography'}
                </button>
                {wantedAlbumsCount > 0 && (
                  <button
                    onClick={handleDownloadAllWanted}
                    disabled={downloadAllWantedMutation.isPending}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Download className="w-5 h-5" />
                    {downloadAllWantedMutation.isPending
                      ? 'Downloading...'
                      : `Download All Wanted (${wantedAlbumsCount})`}
                  </button>
                )}
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
            </div>
          </div>
        </div>

        {/* Albums Section */}
        <div className="mb-4">
          <h3 className="text-2xl font-bold">Albums</h3>
          <p className="text-muted-foreground">
            {albums?.length || 0} {albums?.length === 1 ? 'album' : 'albums'} in library
          </p>
        </div>

        {albumsLoading ? (
          <div className="text-center py-12">Loading albums...</div>
        ) : !albums || albums.length === 0 ? (
          <div className="text-center py-12">
            <Disc3 className="w-16 h-16 mx-auto mb-4 text-muted-foreground opacity-50" />
            <p className="text-muted-foreground mb-4">No albums found in library for this artist.</p>
            <button
              onClick={handleAddDiscography}
              disabled={addDiscographyMutation.isPending}
              className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Plus className="w-5 h-5" />
              {addDiscographyMutation.isPending ? 'Adding...' : 'Add Full Discography'}
            </button>
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
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
                          <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd"/>
                        </svg>
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
                          className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          <Download className="w-4 h-4" />
                          {downloadingAlbumId === album.id ? 'Downloading...' : 'Download'}
                        </button>
                      </div>
                    )}
                  </div>
                </Link>
                <div className="p-3">
                  <Link href={`/music/album/${album.id}`}>
                    <h3 className="font-semibold text-sm truncate hover:text-primary transition" title={album.title}>
                      {album.title}
                    </h3>
                  </Link>
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
        )}
      </div>

      {/* Confirmation Modals */}
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
    </div>
  );
}
