'use client';

import { useState, useRef, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import PageHeader from '@/components/PageHeader';
import DeleteConfirmModal from '@/components/DeleteConfirmModal';
import InteractiveSearchModal from '@/components/InteractiveSearchModal';
import ManualImportModal from '@/components/ManualImportModal';
import MonitoringOptionsDropdown from '@/components/MonitoringOptionsDropdown';
import DownloadHistoryPanel from '@/components/DownloadHistoryPanel';
import FileQualityInfo from '@/components/FileQualityInfo';
import TagsEditor from '@/components/TagsEditor';
import {
  Play,
  Pause,
  Download,
  Music2,
  Clock,
  Disc3,
  ArrowLeft,
  Trash2,
  RefreshCw,
  Search,
  ExternalLink,
  Upload,
  User,
  Album,
  Volume2,
} from 'lucide-react';
import Link from 'next/link';

interface Track {
  id: number;
  title: string;
  duration: number;
  track_position: number;
  disk_number: number;
  deezer_id: number;
  album_id: number;
  isrc: string | null;
  explicit_lyrics: boolean;
  preview: string | null;
  artist_name: string;
  album_title: string;
  album_cover: string | null;
  album_cover_medium: string | null;
  album_cover_big: string | null;
  album_cover_xl: string | null;
  album_release_date: string | null;
  has_file: boolean;
  file_path: string | null;
  file_size: number | null;
  monitored: boolean;
  upgrade_allowed: boolean | null;
  created_at: string;
  updated_at: string;
}

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

export default function TrackDetailPage() {
  const params = useParams();
  const router = useRouter();
  const trackId = parseInt(params.id as string);
  const queryClient = useQueryClient();

  const [isPlaying, setIsPlaying] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showInteractiveSearch, setShowInteractiveSearch] = useState(false);
  const [showManualImport, setShowManualImport] = useState(false);
  const [volume, setVolume] = useState(0.7);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const { data: track, isLoading: trackLoading } = useQuery({
    queryKey: ['track', trackId],
    queryFn: async () => {
      const response = await api.get(`/music/tracks/${trackId}`);
      return response.data as Track;
    },
  });

  const { data: files } = useQuery({
    queryKey: ['files', 'track', trackId],
    queryFn: async () => {
      const response = await api.get(`/files/track/${trackId}`);
      return response.data.files as FileInfo[];
    },
    enabled: !!track?.has_file,
  });

  const refreshMetadataMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/music/tracks/${trackId}/refresh-metadata`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['track', trackId] });
    },
  });

  const deleteTrackMutation = useMutation({
    mutationFn: async (deleteFiles: boolean) => {
      const response = await api.delete(`/music/tracks/${trackId}/delete?delete_files=${deleteFiles}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tracks'] });
      if (track?.album_id) {
        router.push(`/music/album/${track.album_id}`);
      } else {
        router.push('/music');
      }
    },
  });

  const searchDownloadMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/music/tracks/${trackId}/search-download`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['track', trackId] });
    },
  });

  const formatDuration = (seconds: number) => {
    if (!seconds) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${String(secs).padStart(2, '0')}`;
  };

  const getCoverUrl = () => {
    if (!track) return null;
    return track.album_cover_xl || track.album_cover_big || track.album_cover_medium || track.album_cover || null;
  };

  const getStatusBadge = (hasFile: boolean) => {
    if (hasFile) {
      return <span className="px-3 py-1 text-sm rounded bg-green-500/20 text-green-400 border border-green-500/50 font-medium">Downloaded</span>;
    }
    return <span className="px-3 py-1 text-sm rounded bg-yellow-500/20 text-yellow-400 border border-yellow-500/50 font-medium">Wanted</span>;
  };

  const resetPlayback = () => {
    setCurrentTime(0);
    setDuration(0);
  };

  const handlePlayPreview = async () => {
    if (!track?.preview) return;

    if (isPlaying) {
      audioRef.current?.pause();
      resetPlayback();
      setIsPlaying(false);
    } else {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      resetPlayback();

      const audio = new Audio(track.preview);
      audio.volume = volume;

      // Track time updates for progress bar
      audio.addEventListener('timeupdate', () => {
        setCurrentTime(audio.currentTime);
        setDuration(audio.duration || 30);
      });
      audio.addEventListener('loadedmetadata', () => {
        setDuration(audio.duration || 30);
      });
      audio.addEventListener('ended', () => {
        resetPlayback();
        setIsPlaying(false);
      });
      audio.addEventListener('error', () => {
        resetPlayback();
        setIsPlaying(false);
        console.error('Failed to load audio preview');
      });

      try {
        await audio.play();
        audioRef.current = audio;
        setIsPlaying(true);
      } catch (err) {
        console.error('Failed to play preview:', err);
        resetPlayback();
        setIsPlaying(false);
      }
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
      }
    };
  }, []);

  const handleVolumeChange = (newVolume: number) => {
    setVolume(newVolume);
    if (audioRef.current) {
      audioRef.current.volume = newVolume;
    }
  };

  const formatPlaybackTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${String(secs).padStart(2, '0')}`;
  };

  const handleDeleteConfirm = (deleteFiles: boolean) => {
    setShowDeleteModal(false);
    deleteTrackMutation.mutate(deleteFiles);
  };

  if (trackLoading) {
    return (
      <div className="min-h-screen">
        <PageHeader
          title="Loading..."
          description="Loading track details"
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

  if (!track) {
    return (
      <div className="min-h-screen">
        <PageHeader
          title="Not Found"
          description="Track not found"
          gradientFrom="purple-600/10"
          gradientVia="pink-600/10"
          gradientTo="rose-600/10"
        />
        <div className="container mx-auto px-6 py-8">
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">Track not found</p>
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

  const backLink = track.album_id ? `/music/album/${track.album_id}` : '/music';
  const backText = track.album_id ? `Back to ${track.album_title}` : 'Back to Music';

  return (
    <div className="min-h-screen">
      <PageHeader
        title={track.title}
        description={`by ${track.artist_name}`}
        gradientFrom="purple-600/10"
        gradientVia="pink-600/10"
        gradientTo="rose-600/10"
      >
        <Link
          href={backLink}
          className="flex items-center gap-2 px-4 py-2 bg-card text-foreground border-2 border-border rounded-lg hover:bg-accent transition font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          {backText}
        </Link>
      </PageHeader>

      <div className="container mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Track Info Card */}
          <div className="lg:col-span-1 space-y-6">
            <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border overflow-hidden sticky top-8">
              <div className="relative aspect-square">
                {getCoverUrl() ? (
                  <img
                    src={getCoverUrl()!}
                    alt={track.title}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full bg-accent/50 flex items-center justify-center">
                    <Music2 className="w-32 h-32 text-muted-foreground/30" />
                  </div>
                )}
              </div>
              <div className="p-6 space-y-4">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <h2 className="text-2xl font-bold">{track.title}</h2>
                    {track.explicit_lyrics && (
                      <div className="px-1.5 py-0.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/50 font-bold shrink-0">
                        E
                      </div>
                    )}
                  </div>
                  <p className="flex items-center gap-2 text-muted-foreground">
                    <User className="w-4 h-4" />
                    {track.artist_name}
                  </p>
                  {track.album_id && (
                    <Link
                      href={`/music/album/${track.album_id}`}
                      className="flex items-center gap-2 text-primary hover:underline font-medium mt-1"
                    >
                      <Album className="w-4 h-4" />
                      {track.album_title}
                    </Link>
                  )}
                </div>

                <div className="space-y-2 text-sm">
                  {track.album_release_date && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Release Date:</span>
                      <span className="font-medium">
                        {new Date(track.album_release_date).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Duration:</span>
                    <span className="font-medium font-mono">{formatDuration(track.duration)}</span>
                  </div>
                  {track.track_position && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Track #:</span>
                      <span className="font-medium">
                        {track.disk_number > 1 ? `${track.disk_number}-` : ''}{track.track_position}
                      </span>
                    </div>
                  )}
                  {track.isrc && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">ISRC:</span>
                      <span className="font-mono text-xs">{track.isrc}</span>
                    </div>
                  )}
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Status:</span>
                    {getStatusBadge(track.has_file)}
                  </div>
                </div>

                {/* Monitoring Options */}
                <div className="pt-4 border-t border-border">
                  <MonitoringOptionsDropdown
                    mediaType="track"
                    mediaId={track.id}
                    currentState={{
                      monitored: track.monitored,
                      upgradeAllowed: track.upgrade_allowed,
                    }}
                    onUpdate={() => {
                      queryClient.invalidateQueries({ queryKey: ['track', trackId] });
                    }}
                  />
                </div>

                {/* Preview Player */}
                {track.preview && (
                  <div className="pt-4 border-t border-border space-y-3">
                    <button
                      onClick={handlePlayPreview}
                      className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-accent text-foreground rounded-lg hover:bg-accent/80 transition font-medium cursor-pointer"
                    >
                      {isPlaying ? (
                        <>
                          <Pause className="w-5 h-5" />
                          Stop Preview
                        </>
                      ) : (
                        <>
                          <Play className="w-5 h-5" />
                          Play 30s Preview
                        </>
                      )}
                    </button>

                    {/* Progress Bar - only shown when playing */}
                    {isPlaying && (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground font-mono w-10">
                          {formatPlaybackTime(currentTime)}
                        </span>
                        <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary transition-all duration-100"
                            style={{ width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%` }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground font-mono w-10 text-right">
                          {formatPlaybackTime(duration)}
                        </span>
                      </div>
                    )}

                    {/* Volume Control */}
                    <div className="flex items-center gap-2">
                      <Volume2 className="w-4 h-4 text-muted-foreground" />
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.01"
                        value={volume}
                        onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
                        className="flex-1 h-1.5 bg-muted rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer [&::-moz-range-thumb]:w-3 [&::-moz-range-thumb]:h-3 [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer"
                        title={`Volume: ${Math.round(volume * 100)}%`}
                      />
                      <span className="text-xs text-muted-foreground w-8 text-right">
                        {Math.round(volume * 100)}%
                      </span>
                    </div>
                  </div>
                )}

                <div className="space-y-2 pt-4 border-t border-border">
                  <button
                    onClick={() => setShowInteractiveSearch(true)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium cursor-pointer"
                  >
                    <Search className="w-5 h-5" />
                    Interactive Search
                  </button>

                  <button
                    onClick={() => searchDownloadMutation.mutate()}
                    disabled={searchDownloadMutation.isPending}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition font-medium cursor-pointer"
                  >
                    <Download className="w-5 h-5" />
                    {searchDownloadMutation.isPending ? 'Searching...' : 'Auto Search & Download'}
                  </button>

                  <button
                    onClick={() => setShowManualImport(true)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-card text-foreground border-2 border-border rounded-lg hover:bg-accent transition font-medium cursor-pointer"
                  >
                    <Upload className="w-5 h-5" />
                    Manual Import
                  </button>

                  <div className="flex gap-2">
                    <button
                      onClick={() => refreshMetadataMutation.mutate()}
                      disabled={refreshMetadataMutation.isPending}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-card text-foreground border-2 border-border rounded-lg hover:bg-accent transition font-medium disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                    >
                      <RefreshCw className={`w-5 h-5 ${refreshMetadataMutation.isPending ? 'animate-spin' : ''}`} />
                      Refresh
                    </button>
                    <button
                      onClick={() => setShowDeleteModal(true)}
                      className="flex items-center justify-center gap-2 px-4 py-3 bg-destructive text-destructive-foreground rounded-lg hover:opacity-90 transition font-medium cursor-pointer"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                </div>

                {/* External Links */}
                {track.deezer_id && (
                  <div className="pt-4 border-t border-border">
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">External Links</h4>
                    <a
                      href={`https://www.deezer.com/track/${track.deezer_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 px-3 py-2 bg-muted hover:bg-muted/80 rounded-lg transition text-sm cursor-pointer"
                    >
                      <img src="https://www.deezer.com/favicon.ico" alt="Deezer" className="w-4 h-4" />
                      View on Deezer
                      <ExternalLink className="w-3 h-3 text-muted-foreground ml-auto" />
                    </a>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Column - File Info & History */}
          <div className="lg:col-span-2 space-y-6">
            {/* File Quality Info */}
            {track.has_file && (
              <FileQualityInfo
                mediaType="track"
                mediaId={track.id}
                files={files || []}
              />
            )}

            {/* Tags */}
            <TagsEditor
              mediaType="track"
              mediaId={track.id}
            />

            {/* Download History */}
            <DownloadHistoryPanel
              mediaType="track"
              mediaId={track.id}
            />

            {/* Track Details */}
            <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border overflow-hidden">
              <div className="p-6 border-b border-border">
                <h3 className="text-xl font-bold flex items-center gap-2">
                  <Disc3 className="w-6 h-6" />
                  Track Details
                </h3>
              </div>
              <div className="p-6 space-y-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Title</span>
                    <p className="font-medium mt-1">{track.title}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Artist</span>
                    <p className="font-medium mt-1">{track.artist_name}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Album</span>
                    <p className="font-medium mt-1">{track.album_title || '-'}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Duration</span>
                    <p className="font-medium font-mono mt-1">{formatDuration(track.duration)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Track Position</span>
                    <p className="font-medium mt-1">
                      {track.disk_number > 1 ? `Disc ${track.disk_number}, ` : ''}
                      Track {track.track_position || '-'}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">ISRC</span>
                    <p className="font-mono text-xs mt-1">{track.isrc || '-'}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Explicit</span>
                    <p className="font-medium mt-1">{track.explicit_lyrics ? 'Yes' : 'No'}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Deezer ID</span>
                    <p className="font-mono text-xs mt-1">{track.deezer_id || '-'}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Modals */}
      <DeleteConfirmModal
        isOpen={showDeleteModal}
        onCancel={() => setShowDeleteModal(false)}
        onConfirm={handleDeleteConfirm}
        title={track.title}
        itemName="track"
        hasFiles={track.has_file}
      />

      <InteractiveSearchModal
        isOpen={showInteractiveSearch}
        onClose={() => setShowInteractiveSearch(false)}
        mediaType="track"
        mediaId={track.id}
        mediaTitle={track.title}
        searchQuery={`${track.artist_name} ${track.title}`}
      />

      <ManualImportModal
        isOpen={showManualImport}
        onClose={() => setShowManualImport(false)}
        mediaType="track"
        mediaId={track.id}
        mediaTitle={track.title}
        onImportComplete={() => {
          queryClient.invalidateQueries({ queryKey: ['track', trackId] });
          queryClient.invalidateQueries({ queryKey: ['files', 'track', trackId] });
        }}
      />
    </div>
  );
}
