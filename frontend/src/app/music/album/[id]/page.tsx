'use client';

import { useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import PageHeader from '@/components/PageHeader';
import { Play, Download, Music2, Clock, Disc3, ArrowLeft, Eye, EyeOff } from 'lucide-react';
import Link from 'next/link';

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
  duration: number;
  status: string;
  monitored: boolean;
  has_file: boolean;
}

interface Track {
  id: number;
  title: string;
  duration: number;
  track_position: number;
  disk_number: number;
  preview: string | null;
  has_file: boolean;
  explicit_lyrics: boolean;
  artist_name: string;
}

export default function AlbumDetailPage() {
  const params = useParams();
  const router = useRouter();
  const albumId = parseInt(params.id as string);
  const queryClient = useQueryClient();
  const [currentlyPlaying, setCurrentlyPlaying] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const { data: album, isLoading: albumLoading } = useQuery({
    queryKey: ['album', albumId],
    queryFn: async () => {
      const response = await api.get(`/music/albums/${albumId}`);
      return response.data as Album;
    },
  });

  const { data: tracks, isLoading: tracksLoading } = useQuery({
    queryKey: ['tracks', albumId],
    queryFn: async () => {
      const response = await api.get(`/music/tracks?album_id=${albumId}`);
      return response.data as Track[];
    },
  });

  const addTracksMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/music/albums/${albumId}/add-tracks`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tracks', albumId] });
      queryClient.invalidateQueries({ queryKey: ['album', albumId] });
    },
  });

  const searchDownloadMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/music/albums/${albumId}/search-download`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['album', albumId] });
    },
  });

  const toggleMonitoredMutation = useMutation({
    mutationFn: async (monitored: boolean) => {
      const response = await api.put(`/music/albums/${albumId}`, { monitored });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['album', albumId] });
    },
  });

  const getCoverUrl = (album: Album) => {
    return album.cover_xl || album.cover_big || album.cover_medium || album.cover || '/placeholder-poster.jpg';
  };

  const formatDuration = (seconds: number) => {
    if (!seconds) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${String(secs).padStart(2, '0')}`;
  };

  const formatTotalDuration = (seconds: number) => {
    if (!seconds) return 'Unknown';
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${mins}m`;
    }
    return `${mins}m`;
  };

  const getStatusBadge = (status: string, hasFile: boolean) => {
    if (hasFile) {
      return <span className="px-3 py-1 text-sm rounded bg-green-500/20 text-green-400 border border-green-500/50 font-medium">Downloaded</span>;
    }
    if (status === 'downloading') {
      return <span className="px-3 py-1 text-sm rounded bg-blue-500/20 text-blue-400 border border-blue-500/50 font-medium">Downloading</span>;
    }
    if (status === 'wanted') {
      return <span className="px-3 py-1 text-sm rounded bg-yellow-500/20 text-yellow-400 border border-yellow-500/50 font-medium">Wanted</span>;
    }
    return <span className="px-3 py-1 text-sm rounded bg-gray-500/20 text-gray-400 border border-gray-500/50 font-medium">{status}</span>;
  };

  const getTrackNumber = (track: Track) => {
    const hasMultipleDiscs = tracks && tracks.some(t => t.disk_number > 1);
    if (hasMultipleDiscs) {
      return `${track.disk_number}-${track.track_position}`;
    }
    return track.track_position.toString();
  };

  const handlePlayPreview = (track: Track) => {
    if (!track.preview) return;

    if (currentlyPlaying === track.id) {
      audioRef.current?.pause();
      setCurrentlyPlaying(null);
    } else {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      const audio = new Audio(track.preview);
      audio.addEventListener('ended', () => setCurrentlyPlaying(null));
      audio.play();
      audioRef.current = audio;
      setCurrentlyPlaying(track.id);
    }
  };

  if (albumLoading) {
    return (
      <div className="min-h-screen">
        <PageHeader
          title="Loading..."
          description="Loading album details"
          gradientFrom="purple-600/10"
          gradientVia="pink-600/10"
          gradientTo="rose-600/10"
        />
      </div>
    );
  }

  if (!album) {
    return (
      <div className="min-h-screen">
        <PageHeader
          title="Not Found"
          description="Album not found"
          gradientFrom="purple-600/10"
          gradientVia="pink-600/10"
          gradientTo="rose-600/10"
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <PageHeader
        title={album.title}
        description={`by ${album.artist_name}`}
        gradientFrom="purple-600/10"
        gradientVia="pink-600/10"
        gradientTo="rose-600/10"
      >
        <Link
          href="/music"
          className="flex items-center gap-2 px-4 py-2 bg-card text-foreground border-2 border-border rounded-lg hover:bg-accent transition font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Music
        </Link>
      </PageHeader>

      <div className="container mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Album Info Card */}
          <div className="lg:col-span-1">
            <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border overflow-hidden sticky top-8">
              <div className="relative aspect-square">
                <img
                  src={getCoverUrl(album)}
                  alt={album.title}
                  className="w-full h-full object-cover"
                />
                {album.monitored && (
                  <div className="absolute top-4 right-4 bg-primary text-primary-foreground p-2 rounded-lg shadow-lg">
                    <Eye className="w-5 h-5" />
                  </div>
                )}
              </div>
              <div className="p-6 space-y-4">
                <div>
                  <h2 className="text-2xl font-bold mb-2">{album.title}</h2>
                  {album.artist_id && (
                    <Link
                      href={`/music/artist/${album.artist_id}`}
                      className="text-primary hover:underline font-medium"
                    >
                      {album.artist_name}
                    </Link>
                  )}
                  {!album.artist_id && (
                    <p className="text-muted-foreground">{album.artist_name}</p>
                  )}
                </div>

                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Release Date:</span>
                    <span className="font-medium">
                      {album.release_date ? new Date(album.release_date).toLocaleDateString() : 'Unknown'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Tracks:</span>
                    <span className="font-medium">{album.nb_tracks || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Duration:</span>
                    <span className="font-medium">{formatTotalDuration(album.duration)}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Status:</span>
                    {getStatusBadge(album.status, album.has_file)}
                  </div>
                </div>

                <div className="pt-4 border-t border-border space-y-2">
                  <button
                    onClick={() => toggleMonitoredMutation.mutate(!album.monitored)}
                    disabled={toggleMonitoredMutation.isPending}
                    className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition ${
                      album.monitored
                        ? 'bg-primary text-primary-foreground hover:opacity-90'
                        : 'bg-card text-foreground border-2 border-border hover:bg-accent'
                    }`}
                  >
                    {album.monitored ? (
                      <>
                        <Eye className="w-5 h-5" />
                        Monitored
                      </>
                    ) : (
                      <>
                        <EyeOff className="w-5 h-5" />
                        Not Monitored
                      </>
                    )}
                  </button>

                  <button
                    onClick={() => searchDownloadMutation.mutate()}
                    disabled={searchDownloadMutation.isPending || album.status === 'downloading'}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition font-medium"
                  >
                    <Download className="w-5 h-5" />
                    {searchDownloadMutation.isPending ? 'Searching...' : 'Search & Download'}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Tracks Listing */}
          <div className="lg:col-span-2">
            <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border overflow-hidden">
              <div className="p-6 border-b border-border">
                <div className="flex justify-between items-center">
                  <h3 className="text-xl font-bold flex items-center gap-2">
                    <Music2 className="w-6 h-6" />
                    Track Listing
                  </h3>
                  {tracks && tracks.length === 0 && (
                    <button
                      onClick={() => addTracksMutation.mutate()}
                      disabled={addTracksMutation.isPending}
                      className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition font-medium"
                    >
                      <Download className="w-4 h-4" />
                      {addTracksMutation.isPending ? 'Fetching...' : 'Fetch Tracks from Deezer'}
                    </button>
                  )}
                </div>
              </div>

              {tracksLoading ? (
                <div className="p-12 text-center text-muted-foreground">
                  Loading tracks...
                </div>
              ) : !tracks || tracks.length === 0 ? (
                <div className="p-12 text-center">
                  <Music2 className="w-16 h-16 mx-auto mb-4 text-muted-foreground opacity-50" />
                  <p className="text-muted-foreground mb-4">No tracks found for this album.</p>
                  <button
                    onClick={() => addTracksMutation.mutate()}
                    disabled={addTracksMutation.isPending}
                    className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition font-medium"
                  >
                    <Download className="w-5 h-5" />
                    {addTracksMutation.isPending ? 'Fetching from Deezer...' : 'Fetch Tracks from Deezer'}
                  </button>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-accent/50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                          #
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                          Title
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
                          <Clock className="w-4 h-4 inline" />
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
                          Preview
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
                          Status
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {tracks.map((track) => (
                        <tr
                          key={track.id}
                          className="hover:bg-accent/30 transition"
                        >
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground font-mono">
                            {getTrackNumber(track)}
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-2">
                              {track.explicit_lyrics && (
                                <span className="px-1.5 py-0.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/50 font-bold">
                                  E
                                </span>
                              )}
                              <span className="font-medium">{track.title}</span>
                            </div>
                            {track.artist_name && track.artist_name !== album.artist_name && (
                              <div className="text-xs text-muted-foreground mt-1">
                                {track.artist_name}
                              </div>
                            )}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-center font-mono">
                            {formatDuration(track.duration)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-center">
                            {track.preview ? (
                              <button
                                onClick={() => handlePlayPreview(track)}
                                className={`p-2 rounded-full transition ${
                                  currentlyPlaying === track.id
                                    ? 'bg-primary text-primary-foreground'
                                    : 'bg-accent hover:bg-primary hover:text-primary-foreground'
                                }`}
                                title="Play 30s preview"
                              >
                                <Play className="w-4 h-4" />
                              </button>
                            ) : (
                              <span className="text-xs text-muted-foreground">N/A</span>
                            )}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-center">
                            {track.has_file ? (
                              <span className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded bg-green-500/20 text-green-400 border border-green-500/50 font-medium">
                                <Download className="w-3 h-3" />
                                Downloaded
                              </span>
                            ) : (
                              <span className="text-xs text-muted-foreground">-</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {tracks && tracks.length > 0 && (
                <div className="px-6 py-4 bg-accent/30 border-t border-border">
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-4">
                      <span className="text-muted-foreground">
                        <Disc3 className="w-4 h-4 inline mr-1" />
                        {tracks.length} tracks
                      </span>
                      <span className="text-muted-foreground">
                        <Clock className="w-4 h-4 inline mr-1" />
                        {formatTotalDuration(tracks.reduce((sum, t) => sum + (t.duration || 0), 0))}
                      </span>
                    </div>
                    <div className="text-muted-foreground">
                      {tracks.filter(t => t.has_file).length} / {tracks.length} downloaded
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
