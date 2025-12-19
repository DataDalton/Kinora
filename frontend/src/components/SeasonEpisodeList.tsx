'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  ChevronDown,
  ChevronRight,
  Eye,
  EyeOff,
  Search,
  Download,
  CheckCircle,
  XCircle,
  Clock,
  Calendar,
  HardDrive,
  Film,
  Play,
} from 'lucide-react';

interface Episode {
  id: number;
  season_number: number;
  episode_number: number;
  title: string | null;
  overview: string | null;
  still_path: string | null;
  air_date: string | null;
  runtime: number | null;
  monitored: boolean;
  has_file: boolean;
  file_path: string | null;
  file_size: number | null;
  quality_detected: string | null;
}

interface Season {
  id: number;
  season_number: number;
  title: string | null;
  overview: string | null;
  poster_path: string | null;
  air_date: string | null;
  episode_count: number;
  monitored: boolean;
}

interface SeasonEpisodeListProps {
  showId: number;
  seasons?: Season[];
  tmdbImageBaseUrl?: string;
  onSearchSeason?: (seasonNumber: number) => void;
  onSearchEpisode?: (seasonNumber: number, episodeNumber: number) => void;
}

const TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p';

const formatSize = (bytes: number | null): string => {
  if (!bytes) return '';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const formatDate = (dateStr: string | null): string => {
  if (!dateStr) return 'TBA';
  const date = new Date(dateStr);
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

const isAired = (dateStr: string | null): boolean => {
  if (!dateStr) return false;
  return new Date(dateStr) <= new Date();
};

export default function SeasonEpisodeList({
  showId,
  seasons: initialSeasons,
  tmdbImageBaseUrl = TMDB_IMAGE_BASE,
  onSearchSeason,
  onSearchEpisode,
}: SeasonEpisodeListProps) {
  const [expandedSeasons, setExpandedSeasons] = useState<Set<number>>(new Set());
  const queryClient = useQueryClient();

  const { data: seasons } = useQuery({
    queryKey: ['seasons', showId],
    queryFn: async () => {
      const response = await api.get(`/shows/${showId}/seasons`);
      return response.data as Season[];
    },
    initialData: initialSeasons,
  });

  const toggleSeasonMutation = useMutation({
    mutationFn: async ({ seasonNumber, monitored }: { seasonNumber: number; monitored: boolean }) => {
      await api.put(`/shows/${showId}/seasons/${seasonNumber}`, { monitored });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['seasons', showId] });
      queryClient.invalidateQueries({ queryKey: ['episodes', showId] });
    },
  });

  const toggleEpisodeMutation = useMutation({
    mutationFn: async ({ episodeId, monitored }: { episodeId: number; monitored: boolean }) => {
      await api.put(`/shows/${showId}/episodes/${episodeId}`, { monitored });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['episodes', showId] });
    },
  });

  const toggleSeason = (seasonNumber: number) => {
    const newExpanded = new Set(expandedSeasons);
    if (newExpanded.has(seasonNumber)) {
      newExpanded.delete(seasonNumber);
    } else {
      newExpanded.add(seasonNumber);
    }
    setExpandedSeasons(newExpanded);
  };

  const SeasonCard = ({ season }: { season: Season }) => {
    const isExpanded = expandedSeasons.has(season.season_number);

    const { data: episodes, isLoading: episodesLoading } = useQuery({
      queryKey: ['episodes', showId, season.season_number],
      queryFn: async () => {
        const response = await api.get(`/shows/${showId}/seasons/${season.season_number}/episodes`);
        return response.data as Episode[];
      },
      enabled: isExpanded,
    });

    const downloadedCount = episodes?.filter(e => e.has_file).length || 0;
    const monitoredCount = episodes?.filter(e => e.monitored).length || 0;
    const totalEpisodes = episodes?.length || season.episode_count;

    return (
      <div className="bg-background rounded-lg border border-border overflow-hidden">
        <div
          className="flex items-center gap-4 p-4 cursor-pointer hover:bg-muted/50 transition"
          onClick={() => toggleSeason(season.season_number)}
        >
          <div className="flex-shrink-0">
            {isExpanded ? (
              <ChevronDown className="w-5 h-5 text-muted-foreground" />
            ) : (
              <ChevronRight className="w-5 h-5 text-muted-foreground" />
            )}
          </div>

          {season.poster_path ? (
            <img
              src={`${tmdbImageBaseUrl}/w92${season.poster_path}`}
              alt={`Season ${season.season_number}`}
              className="w-12 h-18 rounded object-cover flex-shrink-0"
            />
          ) : (
            <div className="w-12 h-18 bg-muted rounded flex items-center justify-center flex-shrink-0">
              <Film className="w-6 h-6 text-muted-foreground" />
            </div>
          )}

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-medium">
                {season.season_number === 0 ? 'Specials' : `Season ${season.season_number}`}
              </h3>
              {season.title && (
                <span className="text-sm text-muted-foreground truncate">
                  - {season.title}
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <Play className="w-3 h-3" />
                {totalEpisodes} episodes
              </span>
              {season.air_date && (
                <span className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  {formatDate(season.air_date)}
                </span>
              )}
              <span className={`flex items-center gap-1 ${downloadedCount === totalEpisodes ? 'text-green-500' : ''}`}>
                <HardDrive className="w-3 h-3" />
                {downloadedCount}/{totalEpisodes}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => toggleSeasonMutation.mutate({
                seasonNumber: season.season_number,
                monitored: !season.monitored,
              })}
              disabled={toggleSeasonMutation.isPending}
              className={`p-2 rounded-lg transition ${
                season.monitored
                  ? 'bg-primary/20 text-primary hover:bg-primary/30'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }`}
              title={season.monitored ? 'Unmonitor season' : 'Monitor season'}
            >
              {season.monitored ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
            </button>

            {onSearchSeason && (
              <button
                onClick={() => onSearchSeason(season.season_number)}
                className="p-2 bg-muted hover:bg-muted/80 rounded-lg transition"
                title="Search season pack"
              >
                <Search className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {isExpanded && (
          <div className="border-t border-border">
            {episodesLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              </div>
            ) : episodes && episodes.length > 0 ? (
              <div className="divide-y divide-border">
                {episodes.map((episode) => (
                  <EpisodeRow
                    key={episode.id}
                    episode={episode}
                    onToggleMonitor={(monitored) =>
                      toggleEpisodeMutation.mutate({ episodeId: episode.id, monitored })
                    }
                    onSearch={
                      onSearchEpisode
                        ? () => onSearchEpisode(episode.season_number, episode.episode_number)
                        : undefined
                    }
                    tmdbImageBaseUrl={tmdbImageBaseUrl}
                  />
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center py-8 text-muted-foreground">
                <p className="text-sm">No episodes found</p>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  const EpisodeRow = ({
    episode,
    onToggleMonitor,
    onSearch,
    tmdbImageBaseUrl,
  }: {
    episode: Episode;
    onToggleMonitor: (monitored: boolean) => void;
    onSearch?: () => void;
    tmdbImageBaseUrl: string;
  }) => {
    const aired = isAired(episode.air_date);

    return (
      <div className="flex items-center gap-4 p-3 hover:bg-muted/30 transition">
        <div className="w-8 text-center">
          <span className="text-sm font-medium text-muted-foreground">
            {episode.episode_number}
          </span>
        </div>

        {episode.still_path ? (
          <img
            src={`${tmdbImageBaseUrl}/w185${episode.still_path}`}
            alt={episode.title || `Episode ${episode.episode_number}`}
            className="w-24 h-14 rounded object-cover flex-shrink-0"
          />
        ) : (
          <div className="w-24 h-14 bg-muted rounded flex items-center justify-center flex-shrink-0">
            <Film className="w-6 h-6 text-muted-foreground" />
          </div>
        )}

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-medium text-sm truncate">
              {episode.title || `Episode ${episode.episode_number}`}
            </p>
            {episode.has_file ? (
              <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
            ) : aired ? (
              <XCircle className="w-4 h-4 text-destructive flex-shrink-0" />
            ) : (
              <Clock className="w-4 h-4 text-yellow-500 flex-shrink-0" />
            )}
          </div>
          <div className="flex items-center gap-3 mt-0.5 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              {formatDate(episode.air_date)}
            </span>
            {episode.runtime && (
              <span>{episode.runtime} min</span>
            )}
            {episode.has_file && episode.quality_detected && (
              <span className="px-1.5 py-0.5 bg-primary/20 text-primary rounded text-xs">
                {episode.quality_detected}
              </span>
            )}
            {episode.has_file && episode.file_size && (
              <span className="flex items-center gap-1">
                <HardDrive className="w-3 h-3" />
                {formatSize(episode.file_size)}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={() => onToggleMonitor(!episode.monitored)}
            className={`p-1.5 rounded transition ${
              episode.monitored
                ? 'text-primary hover:bg-primary/20'
                : 'text-muted-foreground hover:bg-muted'
            }`}
            title={episode.monitored ? 'Unmonitor' : 'Monitor'}
          >
            {episode.monitored ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
          </button>

          {onSearch && aired && !episode.has_file && (
            <button
              onClick={onSearch}
              className="p-1.5 hover:bg-muted rounded transition"
              title="Search episode"
            >
              <Search className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    );
  };

  if (!seasons || seasons.length === 0) {
    return (
      <div className="bg-muted/30 rounded-lg border border-border p-8">
        <div className="flex flex-col items-center justify-center text-muted-foreground">
          <Film className="w-10 h-10 mb-2 opacity-50" />
          <p className="text-sm">No seasons found</p>
        </div>
      </div>
    );
  }

  const sortedSeasons = [...seasons].sort((a, b) => {
    if (a.season_number === 0) return 1;
    if (b.season_number === 0) return -1;
    return a.season_number - b.season_number;
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Film className="w-5 h-5" />
          Seasons & Episodes
        </h2>
        <span className="text-sm text-muted-foreground">
          {seasons.length} season{seasons.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="space-y-2">
        {sortedSeasons.map((season) => (
          <SeasonCard key={season.id} season={season} />
        ))}
      </div>
    </div>
  );
}
