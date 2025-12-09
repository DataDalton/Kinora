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
  Tv,
  Calendar,
  Star,
  Clock,
  Film
} from 'lucide-react';
import Link from 'next/link';
import PageHeader from '@/components/PageHeader';

interface Show {
  id: number;
  title: string;
  original_title: string;
  overview: string;
  poster_path: string | null;
  backdrop_path: string | null;
  release_date: string;
  first_air_date: string;
  last_air_date: string;
  rating: number;
  vote_count: number;
  popularity: number;
  status: string;
  monitored: boolean;
  tmdb_id: number;
  imdb_id: string;
  tvdb_id: number;
  number_of_seasons: number;
  number_of_episodes: number;
  episode_run_time: string;
  networks: string;
  genres: string;
  in_production: boolean;
  has_file: boolean;
  created_at: string;
  updated_at: string;
}

export default function ShowDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const showId = params?.id as string;

  const { data: show, isLoading } = useQuery({
    queryKey: ['show', showId],
    queryFn: async () => {
      const response = await api.get(`/shows/${showId}`);
      return response.data as Show;
    },
    enabled: !!showId,
  });

  const toggleMonitoredMutation = useMutation({
    mutationFn: async (monitored: boolean) => {
      const response = await api.put(`/shows/${showId}`, { monitored });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['show', showId] });
      queryClient.invalidateQueries({ queryKey: ['shows'] });
    },
  });

  const searchDownloadMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/shows/${showId}/search-download`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['show', showId] });
    },
  });

  const getPosterUrl = (path: string | null) => {
    if (!path) return '/placeholder-poster.jpg';
    return `https://image.tmdb.org/t/p/w500${path}`;
  };

  const getBackdropUrl = (path: string | null) => {
    if (!path) return null;
    return `https://image.tmdb.org/t/p/original${path}`;
  };

  const getStatusBadge = (status: string, hasFile?: boolean) => {
    if (hasFile) {
      return <span className="px-3 py-1.5 text-sm rounded bg-green-500/20 text-green-400 border border-green-500/50 font-medium">Downloaded</span>;
    }
    if (status === 'downloading') {
      return <span className="px-3 py-1.5 text-sm rounded bg-blue-500/20 text-blue-400 border border-blue-500/50 font-medium">Downloading</span>;
    }
    if (status === 'wanted') {
      return <span className="px-3 py-1.5 text-sm rounded bg-yellow-500/20 text-yellow-400 border border-yellow-500/50 font-medium">Wanted</span>;
    }
    return <span className="px-3 py-1.5 text-sm rounded bg-gray-500/20 text-gray-400 border border-gray-500/50 font-medium">{status}</span>;
  };

  const parseGenres = (genres: any): string[] => {
    if (!genres) return [];
    if (typeof genres === 'string') {
      try {
        genres = JSON.parse(genres);
      } catch {
        return [genres];
      }
    }
    if (!Array.isArray(genres)) return [];
    return genres.map((g: any) => (typeof g === 'object' ? g.name : g)).filter(Boolean);
  };

  const parseNetworks = (networks: any): string[] => {
    if (!networks) return [];
    if (typeof networks === 'string') {
      try {
        networks = JSON.parse(networks);
      } catch {
        return [networks];
      }
    }
    if (!Array.isArray(networks)) return [];
    return networks.map((n: any) => (typeof n === 'object' ? n.name : n)).filter(Boolean);
  };

  const handleToggleMonitored = () => {
    if (show) {
      toggleMonitoredMutation.mutate(!show.monitored);
    }
  };

  const handleSearchDownload = () => {
    searchDownloadMutation.mutate();
  };

  if (isLoading) {
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
          <div className="text-center py-12">Loading show...</div>
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

  return (
    <div className="min-h-screen">
      <PageHeader
        title={show.title}
        description={`${show.number_of_seasons || 0} ${show.number_of_seasons === 1 ? 'season' : 'seasons'} • ${show.number_of_episodes || 0} episodes`}
        gradientFrom="green-600/10"
        gradientVia="teal-600/10"
        gradientTo="cyan-600/10"
      >
        <Link
          href="/shows"
          className="flex items-center gap-2 px-4 py-2 bg-card text-foreground rounded-lg hover:bg-accent transition font-medium border-2 border-border"
        >
          <ArrowLeft className="w-5 h-5" />
          Back
        </Link>
      </PageHeader>

      <div className="container mx-auto px-6 py-8">
        {/* Show Info Section */}
        <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6 mb-8">
          <div className="flex flex-col md:flex-row gap-6">
            <div className="flex-shrink-0">
              <img
                src={getPosterUrl(show.poster_path)}
                alt={show.title}
                className="w-48 h-72 object-cover rounded-lg shadow-lg"
              />
            </div>
            <div className="flex-1">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-3xl font-bold mb-2">{show.title}</h2>
                  {show.original_title && show.original_title !== show.title && (
                    <p className="text-muted-foreground mb-2">{show.original_title}</p>
                  )}
                  <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                    {show.first_air_date && (
                      <div className="flex items-center gap-1">
                        <Calendar className="w-4 h-4" />
                        {new Date(show.first_air_date).getFullYear()}
                        {show.last_air_date && show.last_air_date !== show.first_air_date && (
                          <span> - {new Date(show.last_air_date).getFullYear()}</span>
                        )}
                      </div>
                    )}
                    {show.rating > 0 && (
                      <div className="flex items-center gap-1">
                        <Star className="w-4 h-4 text-yellow-400" />
                        {show.rating.toFixed(1)}
                      </div>
                    )}
                    <div className="flex items-center gap-1">
                      <Film className="w-4 h-4" />
                      {show.number_of_seasons} {show.number_of_seasons === 1 ? 'season' : 'seasons'}
                    </div>
                    <div className="flex items-center gap-1">
                      <Tv className="w-4 h-4" />
                      {show.number_of_episodes} episodes
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {show.monitored ? (
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
                  {getStatusBadge(show.status, show.has_file)}
                </div>
              </div>

              {/* Genres */}
              {genres.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-4">
                  {genres.map((genre, index) => (
                    <span key={`${genre}-${index}`} className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm">
                      {genre}
                    </span>
                  ))}
                </div>
              )}

              {/* Networks */}
              {networks.length > 0 && (
                <div className="text-sm text-muted-foreground mb-4">
                  Networks: {networks.join(', ')}
                </div>
              )}

              {/* Overview */}
              {show.overview && (
                <p className="text-foreground/90 mb-6 line-clamp-4">{show.overview}</p>
              )}

              {/* Action Buttons */}
              <div className="flex flex-wrap gap-3 mt-6">
                <button
                  onClick={handleToggleMonitored}
                  disabled={toggleMonitoredMutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-card text-foreground rounded-lg hover:bg-accent transition font-medium border-2 border-border disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  {show.monitored ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  {toggleMonitoredMutation.isPending
                    ? 'Updating...'
                    : show.monitored
                    ? 'Unmonitor'
                    : 'Monitor'}
                </button>
                {show.status === 'wanted' && !show.has_file && (
                  <button
                    onClick={handleSearchDownload}
                    disabled={searchDownloadMutation.isPending}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition font-medium disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                  >
                    <Download className="w-5 h-5" />
                    {searchDownloadMutation.isPending ? 'Searching...' : 'Search & Download'}
                  </button>
                )}
              </div>

              {/* Success/Error Messages */}
              {searchDownloadMutation.isSuccess && (
                <div className="mt-4 p-3 bg-green-500/20 text-green-400 border border-green-500/50 rounded-lg">
                  Search started. Check downloads for progress.
                </div>
              )}
              {searchDownloadMutation.isError && (
                <div className="mt-4 p-3 bg-red-500/20 text-red-400 border border-red-500/50 rounded-lg">
                  Failed to start search. Please try again.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* External Links */}
        <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6">
          <h3 className="text-xl font-bold mb-4">External Links</h3>
          <div className="flex flex-wrap gap-3">
            {show.tmdb_id && (
              <a
                href={`https://www.themoviedb.org/tv/${show.tmdb_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium"
              >
                TMDB
              </a>
            )}
            {show.imdb_id && (
              <a
                href={`https://www.imdb.com/title/${show.imdb_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition font-medium"
              >
                IMDb
              </a>
            )}
            {show.tvdb_id && (
              <a
                href={`https://thetvdb.com/series/${show.tvdb_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition font-medium"
              >
                TVDB
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
