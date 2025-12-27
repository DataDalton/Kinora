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
  Folder,
  ScanLine,
} from 'lucide-react';
import Link from 'next/link';

interface Movie {
  id: number;
  title: string;
  original_title: string;
  overview: string;
  poster_path: string | null;
  backdrop_path: string | null;
  release_date: string;
  genres: { id: number; name: string }[] | string[];
  rating: number;
  vote_count: number;
  popularity: number;
  status: string;
  monitored: boolean;
  upgrade_allowed: boolean | null;
  has_file: boolean;
  file_path: string | null;
  file_size: number | null;
  quality_detected: string | null;
  codec: string | null;
  resolution: string | null;
  runtime: number | null;
  tagline: string | null;
  tmdb_id: number | null;
  imdb_id: string | null;
  collection_id: number | null;
  collection_name: string | null;
  production_companies: { id: number; name: string; logo_path: string | null }[] | null;
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

export default function MovieDetailPage() {
  const params = useParams();
  const router = useRouter();
  const movieId = parseInt(params.id as string);
  const queryClient = useQueryClient();

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showInteractiveSearch, setShowInteractiveSearch] = useState(false);
  const [showManualImport, setShowManualImport] = useState(false);

  const { data: movie, isLoading: movieLoading } = useQuery({
    queryKey: ['movie', movieId],
    queryFn: async () => {
      const response = await api.get(`/movies/${movieId}`);
      return response.data as Movie;
    },
  });

  const { data: credits } = useQuery({
    queryKey: ['movie-credits', movieId],
    queryFn: async () => {
      const response = await api.get(`/movies/${movieId}/credits`);
      return response.data as { cast: CastMember[]; crew: CrewMember[] };
    },
    enabled: !!movie?.tmdb_id,
  });

  const { data: files } = useQuery({
    queryKey: ['files', 'movie', movieId],
    queryFn: async () => {
      const response = await api.get(`/files/movie/${movieId}`);
      return response.data.files as FileInfo[];
    },
    enabled: !!movie?.has_file,
  });

  const searchDownloadMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/search/search-download`, {
        media_type: 'movie',
        media_id: movieId,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['movie', movieId] });
    },
  });

  const refreshMetadataMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/movies/${movieId}/refresh-metadata`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['movie', movieId] });
      queryClient.invalidateQueries({ queryKey: ['movie-credits', movieId] });
    },
  });

  const rescanFilesMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/movies/${movieId}/rescan`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['movie', movieId] });
      queryClient.invalidateQueries({ queryKey: ['files', 'movie', movieId] });
    },
  });

  const deleteMovieMutation = useMutation({
    mutationFn: async (deleteFiles: boolean) => {
      const response = await api.delete(`/movies/${movieId}/delete?delete_files=${deleteFiles}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['movies'] });
      router.push('/movies');
    },
  });

  const getPosterUrl = (path: string | null, size: string = 'w500') => {
    if (!path) return '/placeholder-poster.svg';
    return `https://image.tmdb.org/t/p/${size}${path}`;
  };

  const formatRuntime = (minutes: number | null) => {
    if (!minutes) return 'Unknown';
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (hours > 0) {
      return `${hours}h ${mins}m`;
    }
    return `${mins}m`;
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

  const parseGenres = (genres: Movie['genres']): string[] => {
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

  const handleDeleteConfirm = (deleteFiles: boolean) => {
    setShowDeleteModal(false);
    deleteMovieMutation.mutate(deleteFiles);
  };

  const handleMonitoringUpdate = () => {
    queryClient.invalidateQueries({ queryKey: ['movie', movieId] });
  };

  if (movieLoading) {
    return (
      <div className="min-h-screen">
        <PageHeader
          title="Loading..."
          description="Loading movie details"
          gradientFrom="blue-600/10"
          gradientVia="purple-600/10"
          gradientTo="pink-600/10"
        />
        <div className="container mx-auto px-6 py-8">
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        </div>
      </div>
    );
  }

  if (!movie) {
    return (
      <div className="min-h-screen">
        <PageHeader
          title="Not Found"
          description="Movie not found"
          gradientFrom="blue-600/10"
          gradientVia="purple-600/10"
          gradientTo="pink-600/10"
        />
        <div className="container mx-auto px-6 py-8">
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">Movie not found</p>
            <Link
              href="/movies"
              className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium"
            >
              <ArrowLeft className="w-5 h-5" />
              Back to Movies
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const genres = parseGenres(movie.genres);
  const director = credits?.crew?.find(c => c.job === 'Director');

  return (
    <div className="min-h-screen">
      {/* Backdrop */}
      {movie.backdrop_path && (
        <div className="fixed inset-0 z-0">
          <img
            src={getPosterUrl(movie.backdrop_path, 'original')}
            alt=""
            className="w-full h-full object-cover opacity-10"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-background/50 via-background to-background" />
        </div>
      )}

      <div className="relative z-10">
        <PageHeader
          title={movie.title}
          description={movie.tagline || `${movie.release_date ? new Date(movie.release_date).getFullYear() : 'Unknown'} • ${formatRuntime(movie.runtime)}`}
          gradientFrom="blue-600/10"
          gradientVia="purple-600/10"
          gradientTo="pink-600/10"
        >
          <Link
            href="/movies"
            className="flex items-center gap-2 px-4 py-2 bg-card text-foreground border-2 border-border rounded-lg hover:bg-accent transition font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Movies
          </Link>
        </PageHeader>

        <div className="container mx-auto px-6 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left Column - Poster & Actions */}
            <div className="lg:col-span-1 space-y-6">
              <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border overflow-hidden sticky top-8">
                <div className="relative aspect-[2/3]">
                  <img
                    src={getPosterUrl(movie.poster_path)}
                    alt={movie.title}
                    className="w-full h-full object-cover"
                  />
                  {movie.monitored && (
                    <div className="absolute top-4 right-4 bg-primary text-primary-foreground p-2 rounded-lg shadow-lg">
                      <Eye className="w-5 h-5" />
                    </div>
                  )}
                </div>
                <div className="p-6 space-y-4">
                  <div>
                    <h2 className="text-2xl font-bold mb-1">{movie.title}</h2>
                    {movie.original_title && movie.original_title !== movie.title && (
                      <p className="text-sm text-muted-foreground italic mb-2">{movie.original_title}</p>
                    )}
                    {director && (
                      <p className="text-sm text-muted-foreground">
                        Directed by <span className="text-foreground font-medium">{director.name}</span>
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

                  {/* Movie Details */}
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <Calendar className="w-4 h-4" />
                        Release Date
                      </span>
                      <span className="font-medium">
                        {movie.release_date ? new Date(movie.release_date).toLocaleDateString() : 'Unknown'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <Clock className="w-4 h-4" />
                        Runtime
                      </span>
                      <span className="font-medium">{formatRuntime(movie.runtime)}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <Star className="w-4 h-4" />
                        Rating
                      </span>
                      <span className="font-medium">
                        {movie.rating > 0 ? `${movie.rating.toFixed(1)} / 10` : 'N/A'}
                        {movie.vote_count > 0 && (
                          <span className="text-xs text-muted-foreground ml-1">
                            ({movie.vote_count.toLocaleString()} votes)
                          </span>
                        )}
                      </span>
                    </div>
                  </div>

                  {/* Status & Monitoring */}
                  <div className="py-3 border-y border-border space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Status</span>
                      {getStatusBadge(movie.status, movie.has_file)}
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Monitoring</span>
                      <MonitoringOptionsDropdown
                        mediaType="movie"
                        mediaId={movie.id}
                        currentState={{
                          monitored: movie.monitored,
                          upgradeAllowed: movie.upgrade_allowed,
                        }}
                        onUpdate={handleMonitoringUpdate}
                      />
                    </div>
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
                      disabled={searchDownloadMutation.isPending || movie.status === 'downloading'}
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
                      Delete Movie
                    </button>
                  </div>

                  {/* Collection */}
                  {movie.collection_name && (
                    <div className="pt-4 border-t border-border">
                      <h4 className="text-sm font-medium text-muted-foreground mb-2">Collection</h4>
                      <div className="flex items-center gap-2 px-3 py-2 bg-muted rounded-lg">
                        <Folder className="w-4 h-4 text-primary" />
                        <span className="text-sm font-medium">{movie.collection_name}</span>
                      </div>
                    </div>
                  )}

                  {/* External Links */}
                  <div className="pt-4 border-t border-border">
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">External Links</h4>
                    <div className="space-y-2">
                      {movie.tmdb_id && (
                        <a
                          href={`https://www.themoviedb.org/movie/${movie.tmdb_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 px-3 py-2 bg-muted hover:bg-muted/80 rounded-lg transition text-sm cursor-pointer"
                        >
                          <img src="https://www.themoviedb.org/favicon.ico" alt="TMDB" className="w-4 h-4" />
                          View on TMDB
                          <ExternalLink className="w-3 h-3 text-muted-foreground ml-auto" />
                        </a>
                      )}
                      {movie.imdb_id && (
                        <a
                          href={`https://www.imdb.com/title/${movie.imdb_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 px-3 py-2 bg-muted hover:bg-muted/80 rounded-lg transition text-sm cursor-pointer"
                        >
                          <img src="https://www.imdb.com/favicon.ico" alt="IMDb" className="w-4 h-4" />
                          View on IMDb
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
              {movie.overview && (
                <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6">
                  <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
                    <Film className="w-5 h-5" />
                    Overview
                  </h3>
                  <p className="text-muted-foreground leading-relaxed">{movie.overview}</p>
                </div>
              )}

              {/* File Quality Info */}
              {movie.has_file && (
                <FileQualityInfo
                  mediaType="movie"
                  mediaId={movie.id}
                  files={files || []}
                />
              )}

              {/* Cast & Crew */}
              {credits && (credits.cast?.length > 0 || credits.crew?.length > 0) && (
                <CastCrewSection
                  mediaType="movie"
                  cast={credits.cast || []}
                  crew={credits.crew || []}
                />
              )}

              {/* Tags */}
              <TagsEditor
                mediaType="movie"
                mediaId={movie.id}
              />

              {/* Download History */}
              <DownloadHistoryPanel
                mediaType="movie"
                mediaId={movie.id}
              />

              {/* Production Companies */}
              {movie.production_companies && Array.isArray(movie.production_companies) && movie.production_companies.length > 0 && (
                <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6">
                  <h3 className="text-lg font-bold mb-4">Production Companies</h3>
                  <div className="flex flex-wrap gap-4">
                    {movie.production_companies.map((company: any) => (
                      <div
                        key={company.id || company.name}
                        className="flex items-center gap-2 px-3 py-2 bg-muted rounded-lg"
                      >
                        {company.logo_path ? (
                          <img
                            src={getPosterUrl(company.logo_path, 'w92')}
                            alt={company.name}
                            className="h-6 w-auto object-contain"
                          />
                        ) : null}
                        <span className="text-sm font-medium">{company.name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Modals */}
      <DeleteConfirmModal
        isOpen={showDeleteModal}
        onCancel={() => setShowDeleteModal(false)}
        onConfirm={handleDeleteConfirm}
        title={movie.title}
        itemName="movie"
        hasFiles={movie.has_file}
      />

      <InteractiveSearchModal
        isOpen={showInteractiveSearch}
        onClose={() => setShowInteractiveSearch(false)}
        mediaType="movie"
        mediaId={movie.id}
        mediaTitle={movie.title}
        searchQuery={`${movie.title} ${movie.release_date ? new Date(movie.release_date).getFullYear() : ''}`}
      />

      <ManualImportModal
        isOpen={showManualImport}
        onClose={() => setShowManualImport(false)}
        mediaType="movie"
        mediaId={movie.id}
        mediaTitle={movie.title}
        onImportComplete={() => {
          queryClient.invalidateQueries({ queryKey: ['movie', movieId] });
          queryClient.invalidateQueries({ queryKey: ['files', 'movie', movieId] });
        }}
      />
    </div>
  );
}
