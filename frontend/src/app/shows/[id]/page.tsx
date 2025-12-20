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
import TagsEditor from '@/components/TagsEditor';
import CastCrewSection from '@/components/CastCrewSection';
import SeasonEpisodeList from '@/components/SeasonEpisodeList';
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
  Tv,
  Play,
  ScanLine,
  Building2,
} from 'lucide-react';
import Link from 'next/link';

interface Show {
  id: number;
  title: string;
  original_title: string;
  overview: string;
  poster_path: string | null;
  backdrop_path: string | null;
  release_date: string;
  genres: { id: number; name: string }[] | string[];
  rating: number;
  vote_count: number | null;
  popularity: number;
  status: string;
  monitored: boolean;
  upgrade_allowed: boolean | null;
  season_monitoring: string;
  number_of_seasons: number | null;
  number_of_episodes: number | null;
  episode_run_time: number[] | string | null;
  networks: { id: number; name: string; logo_path: string | null }[] | string | null;
  production_companies: { id: number; name: string; logo_path: string | null }[] | string | null;
  first_air_date: string | null;
  last_air_date: string | null;
  in_production: boolean;
  tmdb_id: number | null;
  imdb_id: string | null;
  tvdb_id: number | null;
  root_folder_path: string | null;
}

interface CastMember {
  id: number;
  name: string;
  character: string;
  profile_path: string | null;
  order: number;
}

interface CrewMember {
  id: number;
  name: string;
  job: string;
  department: string;
  profile_path: string | null;
}

interface Season {
  id: number;
  show_id: number;
  season_number: number;
  title: string | null;
  overview: string | null;
  poster_path: string | null;
  air_date: string | null;
  episode_count: number | null;
  monitored: boolean;
}

export default function ShowDetailPage() {
  const params = useParams();
  const router = useRouter();
  const showId = parseInt(params.id as string);
  const queryClient = useQueryClient();

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showInteractiveSearch, setShowInteractiveSearch] = useState(false);
  const [showManualImport, setShowManualImport] = useState(false);

  const { data: show, isLoading: showLoading } = useQuery({
    queryKey: ['show', showId],
    queryFn: async () => {
      const response = await api.get(`/shows/${showId}`);
      return response.data as Show;
    },
  });

  const { data: credits } = useQuery({
    queryKey: ['show-credits', showId],
    queryFn: async () => {
      const response = await api.get(`/shows/${showId}/credits`);
      return response.data as { cast: CastMember[]; crew: CrewMember[] };
    },
    enabled: !!show?.tmdb_id,
  });

  const { data: seasonsData } = useQuery({
    queryKey: ['show-seasons', showId],
    queryFn: async () => {
      const response = await api.get(`/shows/${showId}/seasons`);
      return response.data as { seasons: Season[]; total_seasons: number };
    },
  });

  const searchDownloadMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/search/search-download`, {
        media_type: 'show',
        media_id: showId,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['show', showId] });
    },
  });

  const refreshMetadataMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/shows/${showId}/refresh-metadata`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['show', showId] });
      queryClient.invalidateQueries({ queryKey: ['show-credits', showId] });
      queryClient.invalidateQueries({ queryKey: ['show-seasons', showId] });
    },
  });

  const rescanFilesMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/shows/${showId}/rescan`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['show', showId] });
      queryClient.invalidateQueries({ queryKey: ['show-seasons', showId] });
    },
  });

  const deleteShowMutation = useMutation({
    mutationFn: async (deleteFiles: boolean) => {
      const response = await api.delete(`/shows/${showId}/delete?delete_files=${deleteFiles}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shows'] });
      router.push('/shows');
    },
  });

  const getPosterUrl = (path: string | null, size: string = 'w500') => {
    if (!path) return '/placeholder-poster.jpg';
    return `https://image.tmdb.org/t/p/${size}${path}`;
  };

  const formatRuntime = (runtime: Show['episode_run_time']) => {
    if (!runtime) return 'Unknown';
    if (typeof runtime === 'string') {
      try {
        const parsed = JSON.parse(runtime);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return `${parsed[0]} min/ep`;
        }
      } catch {
        return 'Unknown';
      }
    }
    if (Array.isArray(runtime) && runtime.length > 0) {
      return `${runtime[0]} min/ep`;
    }
    return 'Unknown';
  };

  const getStatusBadge = (status: string, inProduction: boolean) => {
    if (inProduction) {
      return <span className="px-3 py-1 text-sm rounded bg-green-500/20 text-green-400 border border-green-500/50 font-medium">Continuing</span>;
    }
    if (status === 'downloading') {
      return <span className="px-3 py-1 text-sm rounded bg-blue-500/20 text-blue-400 border border-blue-500/50 font-medium">Downloading</span>;
    }
    if (status === 'wanted') {
      return <span className="px-3 py-1 text-sm rounded bg-yellow-500/20 text-yellow-400 border border-yellow-500/50 font-medium">Wanted</span>;
    }
    return <span className="px-3 py-1 text-sm rounded bg-gray-500/20 text-gray-400 border border-gray-500/50 font-medium">Ended</span>;
  };

  const parseGenres = (genres: Show['genres']): string[] => {
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

  const parseNetworks = (networks: Show['networks']): { name: string; logo_path: string | null }[] => {
    if (!networks) return [];
    if (Array.isArray(networks)) {
      return networks;
    }
    if (typeof networks === 'string') {
      try {
        const parsed = JSON.parse(networks);
        return Array.isArray(parsed) ? parsed : [];
      } catch {
        return [];
      }
    }
    return [];
  };

  const handleDeleteConfirm = (deleteFiles: boolean) => {
    setShowDeleteModal(false);
    deleteShowMutation.mutate(deleteFiles);
  };

  const handleMonitoringUpdate = () => {
    queryClient.invalidateQueries({ queryKey: ['show', showId] });
  };

  if (showLoading) {
    return (
      <div className="min-h-screen">
        <PageHeader
          title="Loading..."
          description="Loading show details"
          gradientFrom="green-600/10"
          gradientVia="teal-600/10"
          gradientTo="cyan-600/10"
        />
        <div className="container mx-auto px-6 py-8">
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        </div>
      </div>
    );
  }

  if (!show) {
    return (
      <div className="min-h-screen">
        <PageHeader
          title="Not Found"
          description="Show not found"
          gradientFrom="green-600/10"
          gradientVia="teal-600/10"
          gradientTo="cyan-600/10"
        />
        <div className="container mx-auto px-6 py-8">
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">Show not found</p>
            <Link
              href="/shows"
              className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium"
            >
              <ArrowLeft className="w-5 h-5" />
              Back to Shows
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const genres = parseGenres(show.genres);
  const networks = parseNetworks(show.networks);
  const creator = credits?.crew?.find(c => c.job === 'Creator');

  return (
    <div className="min-h-screen">
      {/* Backdrop */}
      {show.backdrop_path && (
        <div className="fixed inset-0 z-0">
          <img
            src={getPosterUrl(show.backdrop_path, 'original')}
            alt=""
            className="w-full h-full object-cover opacity-10"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-background/50 via-background to-background" />
        </div>
      )}

      <div className="relative z-10">
        <PageHeader
          title={show.title}
          description={`${show.first_air_date ? new Date(show.first_air_date).getFullYear() : 'Unknown'} • ${show.number_of_seasons || '?'} Seasons • ${show.number_of_episodes || '?'} Episodes`}
          gradientFrom="green-600/10"
          gradientVia="teal-600/10"
          gradientTo="cyan-600/10"
        >
          <Link
            href="/shows"
            className="flex items-center gap-2 px-4 py-2 bg-card text-foreground border-2 border-border rounded-lg hover:bg-accent transition font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Shows
          </Link>
        </PageHeader>

        <div className="container mx-auto px-6 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left Column - Poster & Actions */}
            <div className="lg:col-span-1 space-y-6">
              <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border overflow-hidden sticky top-8">
                <div className="relative aspect-[2/3]">
                  <img
                    src={getPosterUrl(show.poster_path)}
                    alt={show.title}
                    className="w-full h-full object-cover"
                  />
                  {show.monitored && (
                    <div className="absolute top-4 right-4 bg-primary text-primary-foreground p-2 rounded-lg shadow-lg">
                      <Eye className="w-5 h-5" />
                    </div>
                  )}
                </div>
                <div className="p-6 space-y-4">
                  <div>
                    <h2 className="text-2xl font-bold mb-1">{show.title}</h2>
                    {show.original_title && show.original_title !== show.title && (
                      <p className="text-sm text-muted-foreground italic mb-2">{show.original_title}</p>
                    )}
                    {creator && (
                      <p className="text-sm text-muted-foreground">
                        Created by <span className="text-foreground font-medium">{creator.name}</span>
                      </p>
                    )}
                  </div>

                  {/* Genres */}
                  {genres.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {genres.map((genre, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-1 text-xs rounded bg-accent text-accent-foreground font-medium"
                        >
                          {genre}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Networks */}
                  {networks.length > 0 && (
                    <div className="flex items-center gap-2">
                      <Building2 className="w-4 h-4 text-muted-foreground" />
                      <span className="text-sm text-muted-foreground">
                        {networks.map(n => n.name).join(', ')}
                      </span>
                    </div>
                  )}

                  {/* Show Details */}
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <Calendar className="w-4 h-4" />
                        First Aired
                      </span>
                      <span className="font-medium">
                        {show.first_air_date ? new Date(show.first_air_date).toLocaleDateString() : 'Unknown'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <Tv className="w-4 h-4" />
                        Seasons
                      </span>
                      <span className="font-medium">{show.number_of_seasons || '?'}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <Play className="w-4 h-4" />
                        Episodes
                      </span>
                      <span className="font-medium">{show.number_of_episodes || '?'}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <Clock className="w-4 h-4" />
                        Runtime
                      </span>
                      <span className="font-medium">{formatRuntime(show.episode_run_time)}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <Star className="w-4 h-4" />
                        Rating
                      </span>
                      <span className="font-medium">
                        {show.rating ? `${show.rating.toFixed(1)} / 10` : 'N/A'}
                        {show.vote_count && (
                          <span className="text-xs text-muted-foreground ml-1">
                            ({show.vote_count.toLocaleString()} votes)
                          </span>
                        )}
                      </span>
                    </div>
                    <div className="flex justify-between items-center pt-2 border-t border-border">
                      <span className="text-muted-foreground">Status</span>
                      {getStatusBadge(show.status, show.in_production)}
                    </div>
                  </div>

                  {/* Monitoring Options */}
                  <div className="pt-4 border-t border-border">
                    <MonitoringOptionsDropdown
                      mediaType="show"
                      mediaId={show.id}
                      currentState={{
                        monitored: show.monitored,
                        upgradeAllowed: show.upgrade_allowed,
                        seasonMonitoring: show.season_monitoring as any,
                      }}
                      showSeasonOptions={true}
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
                      disabled={searchDownloadMutation.isPending || show.status === 'downloading'}
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
                        title="Refresh metadata from TMDB"
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
                      Delete Show
                    </button>
                  </div>

                  {/* External Links */}
                  <div className="pt-4 border-t border-border">
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">External Links</h4>
                    <div className="space-y-2">
                      {show.tmdb_id && (
                        <a
                          href={`https://www.themoviedb.org/tv/${show.tmdb_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 px-3 py-2 bg-muted hover:bg-muted/80 rounded-lg transition text-sm cursor-pointer"
                        >
                          <img src="https://www.themoviedb.org/favicon.ico" alt="TMDB" className="w-4 h-4" />
                          View on TMDB
                          <ExternalLink className="w-3 h-3 text-muted-foreground ml-auto" />
                        </a>
                      )}
                      {show.imdb_id && (
                        <a
                          href={`https://www.imdb.com/title/${show.imdb_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 px-3 py-2 bg-muted hover:bg-muted/80 rounded-lg transition text-sm cursor-pointer"
                        >
                          <img src="https://www.imdb.com/favicon.ico" alt="IMDb" className="w-4 h-4" />
                          View on IMDb
                          <ExternalLink className="w-3 h-3 text-muted-foreground ml-auto" />
                        </a>
                      )}
                      {show.tvdb_id && (
                        <a
                          href={`https://thetvdb.com/series/${show.tvdb_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 px-3 py-2 bg-muted hover:bg-muted/80 rounded-lg transition text-sm cursor-pointer"
                        >
                          <img src="https://thetvdb.com/images/icon.png" alt="TVDB" className="w-4 h-4" />
                          View on TVDB
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
              {show.overview && (
                <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6">
                  <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
                    <Tv className="w-5 h-5" />
                    Overview
                  </h3>
                  <p className="text-muted-foreground leading-relaxed">{show.overview}</p>
                </div>
              )}

              {/* Seasons & Episodes */}
              {seasonsData && seasonsData.seasons.length > 0 && (
                <SeasonEpisodeList
                  showId={show.id}
                  seasons={seasonsData.seasons}
                />
              )}

              {/* Cast & Crew */}
              {credits && (credits.cast?.length > 0 || credits.crew?.length > 0) && (
                <CastCrewSection
                  mediaType="show"
                  cast={credits.cast || []}
                  crew={credits.crew || []}
                />
              )}

              {/* Tags */}
              <TagsEditor
                mediaType="show"
                mediaId={show.id}
              />

              {/* Download History */}
              <DownloadHistoryPanel
                mediaType="show"
                mediaId={show.id}
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
        title={show.title}
        itemName="show"
        hasFiles={!!show.root_folder_path}
      />

      <InteractiveSearchModal
        isOpen={showInteractiveSearch}
        onClose={() => setShowInteractiveSearch(false)}
        mediaType="show"
        mediaId={show.id}
        mediaTitle={show.title}
        searchQuery={show.title}
      />

      <ManualImportModal
        isOpen={showManualImport}
        onClose={() => setShowManualImport(false)}
        mediaType="show"
        mediaId={show.id}
        mediaTitle={show.title}
        onImportComplete={() => {
          queryClient.invalidateQueries({ queryKey: ['show', showId] });
          queryClient.invalidateQueries({ queryKey: ['show-seasons', showId] });
        }}
      />
    </div>
  );
}
