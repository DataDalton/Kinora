'use client';

import { useState } from 'react';
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
import CastCrewSection from '@/components/CastCrewSection';
import {
  ArrowLeft,
  Eye,
  Trash2,
  RefreshCw,
  Search,
  ExternalLink,
  Upload,
  Download,
  Clock,
  Calendar,
  Star,
  Film,
  Tv,
  Play,
  ScanLine,
  Check,
  X,
} from 'lucide-react';
import Link from 'next/link';

interface Anime {
  id: number;
  title: string;
  original_title: string;
  overview: string;
  poster_path: string | null;
  backdrop_path: string | null;
  release_date: string;
  genres: { id?: number; name: string }[] | string[];
  rating: number;
  vote_count: number | null;
  popularity: number;
  status: string;
  monitored: boolean;
  upgrade_allowed: boolean | null;
  has_file: boolean;
  episodes: number | null;
  duration: number | null;
  season_year: number | null;
  season_period: string | null;
  format: string | null;
  source: string | null;
  studios: string[] | null;
  is_adult: boolean;
  absolute_numbering: boolean;
  episode_monitoring: string;
  anilist_id: number | null;
  mal_id: number | null;
  root_folder_path: string | null;
}

interface Character {
  id: number;
  name: string;
  image: string | null;
}

interface Staff {
  id: number;
  name: string;
  role: string;
}

interface Episode {
  id: number;
  anime_id: number;
  episode_number: number;
  season_number: number | null;
  season_episode: number | null;
  title: string | null;
  air_date: string | null;
  monitored: boolean;
  has_file: boolean;
  file_path: string | null;
  file_size: number | null;
  quality_detected: string | null;
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

export default function AnimeDetailPage() {
  const params = useParams();
  const router = useRouter();
  const animeId = parseInt(params.id as string);
  const queryClient = useQueryClient();

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showInteractiveSearch, setShowInteractiveSearch] = useState(false);
  const [showManualImport, setShowManualImport] = useState(false);
  const [expandedEpisodes, setExpandedEpisodes] = useState(true);

  const { data: anime, isLoading: animeLoading } = useQuery({
    queryKey: ['anime', animeId],
    queryFn: async () => {
      const response = await api.get(`/anime/${animeId}`);
      return response.data as Anime;
    },
  });

  const { data: credits } = useQuery({
    queryKey: ['anime-credits', animeId],
    queryFn: async () => {
      const response = await api.get(`/anime/${animeId}/credits`);
      return response.data as { characters: Character[]; staff: Staff[]; studios: string[] };
    },
    enabled: !!anime?.anilist_id,
  });

  const { data: episodesData } = useQuery({
    queryKey: ['anime-episodes', animeId],
    queryFn: async () => {
      const response = await api.get(`/anime/${animeId}/episodes`);
      return response.data as { episodes: Episode[]; total_episodes: number; absolute_numbering: boolean };
    },
  });

  const { data: files } = useQuery({
    queryKey: ['files', 'anime', animeId],
    queryFn: async () => {
      const response = await api.get(`/files/anime/${animeId}`);
      return response.data.files as FileInfo[];
    },
    enabled: !!anime?.has_file,
  });

  const searchDownloadMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/search/search-download`, {
        media_type: 'anime',
        media_id: animeId,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anime', animeId] });
    },
  });

  const refreshMetadataMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/anime/${animeId}/refresh-metadata`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anime', animeId] });
      queryClient.invalidateQueries({ queryKey: ['anime-credits', animeId] });
    },
  });

  const rescanFilesMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/anime/${animeId}/rescan`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anime', animeId] });
      queryClient.invalidateQueries({ queryKey: ['files', 'anime', animeId] });
      queryClient.invalidateQueries({ queryKey: ['anime-episodes', animeId] });
    },
  });

  const deleteAnimeMutation = useMutation({
    mutationFn: async (deleteFiles: boolean) => {
      const response = await api.delete(`/anime/${animeId}/delete?delete_files=${deleteFiles}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anime'] });
      router.push('/anime');
    },
  });

  const toggleEpisodeMonitorMutation = useMutation({
    mutationFn: async ({ episodeNumber, monitored }: { episodeNumber: number; monitored: boolean }) => {
      const response = await api.put(`/anime/${animeId}/episodes/${episodeNumber}`, null, {
        params: { monitored },
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anime-episodes', animeId] });
    },
  });

  const getPosterUrl = (path: string | null) => {
    if (!path) return '/placeholder-poster.jpg';
    if (path.startsWith('http')) return path;
    return `https://image.tmdb.org/t/p/w500${path}`;
  };

  const formatDuration = (minutes: number | null) => {
    if (!minutes) return 'Unknown';
    return `${minutes} min/ep`;
  };

  const formatFileSize = (bytes: number | null) => {
    if (!bytes) return 'Unknown';
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 1) {
      return `${gb.toFixed(2)} GB`;
    }
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(0)} MB`;
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
    return <span className="px-3 py-1 text-sm rounded bg-gray-500/20 text-gray-400 border border-gray-500/50 font-medium capitalize">{status}</span>;
  };

  const getFormatBadge = (format: string | null) => {
    if (!format) return null;
    const colors: Record<string, string> = {
      TV: 'bg-blue-500/20 text-blue-400 border-blue-500/50',
      TV_SHORT: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50',
      MOVIE: 'bg-purple-500/20 text-purple-400 border-purple-500/50',
      SPECIAL: 'bg-orange-500/20 text-orange-400 border-orange-500/50',
      OVA: 'bg-pink-500/20 text-pink-400 border-pink-500/50',
      ONA: 'bg-green-500/20 text-green-400 border-green-500/50',
      MUSIC: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50',
    };
    return (
      <span className={`px-2 py-1 text-xs rounded border font-medium ${colors[format] || 'bg-gray-500/20 text-gray-400 border-gray-500/50'}`}>
        {format.replace('_', ' ')}
      </span>
    );
  };

  const parseGenres = (genres: Anime['genres']): string[] => {
    if (!genres) return [];
    if (Array.isArray(genres)) {
      return genres.map(g => typeof g === 'string' ? g : g.name);
    }
    if (typeof genres === 'string') {
      try {
        const parsed = JSON.parse(genres);
        return Array.isArray(parsed) ? parsed.map((g: any) => typeof g === 'string' ? g : g.name) : [];
      } catch {
        return [];
      }
    }
    return [];
  };

  const parseStudios = (studios: Anime['studios']): string[] => {
    if (!studios) return [];
    if (Array.isArray(studios)) {
      return studios.filter(s => typeof s === 'string') as string[];
    }
    if (typeof studios === 'string') {
      try {
        const parsed = JSON.parse(studios);
        return Array.isArray(parsed) ? parsed : [];
      } catch {
        return [];
      }
    }
    return [];
  };

  const handleDeleteConfirm = (deleteFiles: boolean) => {
    setShowDeleteModal(false);
    deleteAnimeMutation.mutate(deleteFiles);
  };

  const handleMonitoringUpdate = () => {
    queryClient.invalidateQueries({ queryKey: ['anime', animeId] });
  };

  const generateEpisodeList = () => {
    if (!anime?.episodes) return [];
    const episodes = episodesData?.episodes || [];
    const episodeMap = new Map(episodes.map(ep => [ep.episode_number, ep]));

    return Array.from({ length: anime.episodes }, (_, i) => {
      const epNum = i + 1;
      const existing = episodeMap.get(epNum);
      return existing || {
        episode_number: epNum,
        title: null,
        monitored: true,
        has_file: false,
        file_path: null,
        file_size: null,
        quality_detected: null,
      };
    });
  };

  if (animeLoading) {
    return (
      <div className="min-h-screen">
        <PageHeader
          title="Loading..."
          description="Loading anime details"
          gradientFrom="pink-600/10"
          gradientVia="purple-600/10"
          gradientTo="red-600/10"
        />
        <div className="container mx-auto px-6 py-8">
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        </div>
      </div>
    );
  }

  if (!anime) {
    return (
      <div className="min-h-screen">
        <PageHeader
          title="Not Found"
          description="Anime not found"
          gradientFrom="pink-600/10"
          gradientVia="purple-600/10"
          gradientTo="red-600/10"
        />
        <div className="container mx-auto px-6 py-8">
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">Anime not found</p>
            <Link
              href="/anime"
              className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium"
            >
              <ArrowLeft className="w-5 h-5" />
              Back to Anime
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const genres = parseGenres(anime.genres);
  const studios = parseStudios(anime.studios);
  const episodeList = generateEpisodeList();
  const downloadedCount = episodeList.filter(ep => ep.has_file).length;

  return (
    <div className="min-h-screen">
      {/* Backdrop */}
      {anime.backdrop_path && (
        <div className="fixed inset-0 z-0">
          <img
            src={getPosterUrl(anime.backdrop_path)}
            alt=""
            className="w-full h-full object-cover opacity-10"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-background/50 via-background to-background" />
        </div>
      )}

      <div className="relative z-10">
        <PageHeader
          title={anime.title}
          description={`${anime.season_year || ''} ${anime.season_period || ''} • ${anime.episodes || '?'} episodes`.trim()}
          gradientFrom="pink-600/10"
          gradientVia="purple-600/10"
          gradientTo="red-600/10"
        >
          <Link
            href="/anime"
            className="flex items-center gap-2 px-4 py-2 bg-card text-foreground border-2 border-border rounded-lg hover:bg-accent transition font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Anime
          </Link>
        </PageHeader>

        <div className="container mx-auto px-6 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left Column - Poster & Actions */}
            <div className="lg:col-span-1 space-y-6">
              <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border overflow-hidden sticky top-8">
                <div className="relative aspect-[2/3]">
                  <img
                    src={getPosterUrl(anime.poster_path)}
                    alt={anime.title}
                    className="w-full h-full object-cover"
                  />
                  {anime.monitored && (
                    <div className="absolute top-4 right-4 bg-primary text-primary-foreground p-2 rounded-lg shadow-lg">
                      <Eye className="w-5 h-5" />
                    </div>
                  )}
                  {anime.is_adult && (
                    <div className="absolute top-4 left-4 bg-red-600 text-white px-2 py-1 rounded-lg text-xs font-bold shadow-lg">
                      18+
                    </div>
                  )}
                </div>
                <div className="p-6 space-y-4">
                  <div>
                    <h2 className="text-2xl font-bold mb-1">{anime.title}</h2>
                    {anime.original_title && anime.original_title !== anime.title && (
                      <p className="text-sm text-muted-foreground italic mb-2">{anime.original_title}</p>
                    )}
                  </div>

                  {/* Format & Genres */}
                  <div className="flex flex-wrap gap-2">
                    {getFormatBadge(anime.format)}
                    {genres.slice(0, 3).map((genre, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-1 text-xs rounded bg-accent text-accent-foreground font-medium"
                      >
                        {genre}
                      </span>
                    ))}
                  </div>

                  {/* Studios */}
                  {studios.length > 0 && (
                    <p className="text-sm text-muted-foreground">
                      Studio: <span className="text-foreground font-medium">{studios.join(', ')}</span>
                    </p>
                  )}

                  {/* Anime Details */}
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <Calendar className="w-4 h-4" />
                        Season
                      </span>
                      <span className="font-medium">
                        {anime.season_period || ''} {anime.season_year || 'Unknown'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <Tv className="w-4 h-4" />
                        Episodes
                      </span>
                      <span className="font-medium">
                        {downloadedCount} / {anime.episodes || '?'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <Clock className="w-4 h-4" />
                        Duration
                      </span>
                      <span className="font-medium">{formatDuration(anime.duration)}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <Star className="w-4 h-4" />
                        Rating
                      </span>
                      <span className="font-medium">
                        {anime.rating ? `${anime.rating.toFixed(1)} / 10` : 'N/A'}
                      </span>
                    </div>
                    {anime.source && (
                      <div className="flex justify-between items-center">
                        <span className="flex items-center gap-2 text-muted-foreground">
                          <Film className="w-4 h-4" />
                          Source
                        </span>
                        <span className="font-medium capitalize">{anime.source.toLowerCase().replace('_', ' ')}</span>
                      </div>
                    )}
                    <div className="flex justify-between items-center pt-2 border-t border-border">
                      <span className="text-muted-foreground">Status</span>
                      {getStatusBadge(anime.status, anime.has_file)}
                    </div>
                  </div>

                  {/* Monitoring Options */}
                  <div className="pt-4 border-t border-border">
                    <MonitoringOptionsDropdown
                      mediaType="anime"
                      mediaId={anime.id}
                      currentState={{
                        monitored: anime.monitored,
                        upgradeAllowed: anime.upgrade_allowed,
                      }}
                      onUpdate={handleMonitoringUpdate}
                    />
                  </div>

                  {/* Action Buttons */}
                  <div className="space-y-2">
                    <button
                      onClick={() => setShowInteractiveSearch(true)}
                      className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium cursor-pointer"
                    >
                      <Search className="w-5 h-5" />
                      Interactive Search
                    </button>

                    <button
                      onClick={() => searchDownloadMutation.mutate()}
                      disabled={searchDownloadMutation.isPending || anime.status === 'downloading'}
                      className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed transition font-medium"
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
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-card text-foreground border-2 border-border rounded-lg hover:bg-accent transition font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Refresh metadata from AniList"
                      >
                        <RefreshCw className={`w-5 h-5 ${refreshMetadataMutation.isPending ? 'animate-spin' : ''}`} />
                        Refresh
                      </button>
                      <button
                        onClick={() => rescanFilesMutation.mutate()}
                        disabled={rescanFilesMutation.isPending}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-card text-foreground border-2 border-border rounded-lg hover:bg-accent transition font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Rescan files on disk"
                      >
                        <ScanLine className={`w-5 h-5 ${rescanFilesMutation.isPending ? 'animate-spin' : ''}`} />
                        Rescan
                      </button>
                    </div>

                    <button
                      onClick={() => setShowDeleteModal(true)}
                      className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-destructive text-destructive-foreground rounded-lg hover:opacity-90 transition font-medium cursor-pointer"
                    >
                      <Trash2 className="w-5 h-5" />
                      Delete Anime
                    </button>
                  </div>

                  {/* External Links */}
                  <div className="pt-4 border-t border-border">
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">External Links</h4>
                    <div className="space-y-2">
                      {anime.anilist_id && (
                        <a
                          href={`https://anilist.co/anime/${anime.anilist_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 px-3 py-2 bg-muted hover:bg-muted/80 rounded-lg transition text-sm cursor-pointer"
                        >
                          <img src="https://anilist.co/img/icons/icon.svg" alt="AniList" className="w-4 h-4" />
                          View on AniList
                          <ExternalLink className="w-3 h-3 text-muted-foreground ml-auto" />
                        </a>
                      )}
                      {anime.mal_id && (
                        <a
                          href={`https://myanimelist.net/anime/${anime.mal_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 px-3 py-2 bg-muted hover:bg-muted/80 rounded-lg transition text-sm cursor-pointer"
                        >
                          <img src="https://myanimelist.net/img/common/pwa/launcher-icon-0-75x.png" alt="MAL" className="w-4 h-4" />
                          View on MyAnimeList
                          <ExternalLink className="w-3 h-3 text-muted-foreground ml-auto" />
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Column - Details */}
            <div className="lg:col-span-2 space-y-6">
              {/* Overview */}
              {anime.overview && (
                <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6">
                  <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
                    <Film className="w-5 h-5" />
                    Synopsis
                  </h3>
                  <p className="text-muted-foreground leading-relaxed">{anime.overview}</p>
                </div>
              )}

              {/* File Quality Info */}
              {anime.has_file && (
                <FileQualityInfo
                  mediaType="anime"
                  mediaId={anime.id}
                  files={files || []}
                />
              )}

              {/* Episode List */}
              {episodeList.length > 0 && (
                <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border overflow-hidden">
                  <button
                    onClick={() => setExpandedEpisodes(!expandedEpisodes)}
                    className="w-full p-6 flex items-center justify-between hover:bg-accent/50 transition cursor-pointer"
                  >
                    <h3 className="text-lg font-bold flex items-center gap-2">
                      <Play className="w-5 h-5" />
                      Episodes ({downloadedCount}/{episodeList.length})
                    </h3>
                    <span className={`transition-transform ${expandedEpisodes ? 'rotate-180' : ''}`}>
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </span>
                  </button>

                  {expandedEpisodes && (
                    <div className="border-t border-border">
                      <div className="max-h-96 overflow-y-auto">
                        <table className="w-full">
                          <thead className="bg-accent/50 sticky top-0">
                            <tr>
                              <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase">#</th>
                              <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase">Title</th>
                              <th className="px-4 py-2 text-center text-xs font-medium text-muted-foreground uppercase">Status</th>
                              <th className="px-4 py-2 text-center text-xs font-medium text-muted-foreground uppercase">Monitor</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border">
                            {episodeList.map((episode) => (
                              <tr key={episode.episode_number} className="hover:bg-accent/30 transition">
                                <td className="px-4 py-3 text-sm font-mono">{episode.episode_number}</td>
                                <td className="px-4 py-3 text-sm">
                                  {episode.title || `Episode ${episode.episode_number}`}
                                </td>
                                <td className="px-4 py-3 text-center">
                                  {episode.has_file ? (
                                    <span className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded bg-green-500/20 text-green-400 border border-green-500/50">
                                      <Check className="w-3 h-3" />
                                      Downloaded
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded bg-yellow-500/20 text-yellow-400 border border-yellow-500/50">
                                      Missing
                                    </span>
                                  )}
                                </td>
                                <td className="px-4 py-3 text-center">
                                  <button
                                    onClick={() => toggleEpisodeMonitorMutation.mutate({
                                      episodeNumber: episode.episode_number,
                                      monitored: !episode.monitored,
                                    })}
                                    disabled={toggleEpisodeMonitorMutation.isPending}
                                    className={`p-1.5 rounded transition cursor-pointer disabled:cursor-not-allowed ${
                                      episode.monitored
                                        ? 'bg-primary/20 text-primary hover:bg-primary/30'
                                        : 'bg-muted text-muted-foreground hover:bg-muted/80'
                                    }`}
                                    title={episode.monitored ? 'Click to unmonitor' : 'Click to monitor'}
                                  >
                                    {episode.monitored ? (
                                      <Eye className="w-4 h-4" />
                                    ) : (
                                      <X className="w-4 h-4" />
                                    )}
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Cast & Crew */}
              {credits && (credits.characters?.length > 0 || credits.staff?.length > 0) && (
                <CastCrewSection
                  mediaType="anime"
                  cast={credits.characters?.map(c => ({
                    id: c.id,
                    name: c.name,
                    character: '',
                    profile_path: c.image,
                    order: 0,
                  })) || []}
                  crew={credits.staff?.map(s => ({
                    id: s.id,
                    name: s.name,
                    job: s.role,
                    department: 'Staff',
                    profile_path: null,
                  })) || []}
                />
              )}

              {/* Tags */}
              <TagsEditor
                mediaType="anime"
                mediaId={anime.id}
              />

              {/* Download History */}
              <DownloadHistoryPanel
                mediaType="anime"
                mediaId={anime.id}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Modals */}
      <DeleteConfirmModal
        isOpen={showDeleteModal}
        onCancel={() => setShowDeleteModal(false)}
        onConfirm={handleDeleteConfirm}
        title={anime.title}
        itemName="anime"
        hasFiles={anime.has_file}
      />

      <InteractiveSearchModal
        isOpen={showInteractiveSearch}
        onClose={() => setShowInteractiveSearch(false)}
        mediaType="anime"
        mediaId={anime.id}
        mediaTitle={anime.title}
        searchQuery={anime.title}
      />

      <ManualImportModal
        isOpen={showManualImport}
        onClose={() => setShowManualImport(false)}
        mediaType="anime"
        mediaId={anime.id}
        mediaTitle={anime.title}
        onImportComplete={() => {
          queryClient.invalidateQueries({ queryKey: ['anime', animeId] });
          queryClient.invalidateQueries({ queryKey: ['files', 'anime', animeId] });
          queryClient.invalidateQueries({ queryKey: ['anime-episodes', animeId] });
        }}
      />
    </div>
  );
}
