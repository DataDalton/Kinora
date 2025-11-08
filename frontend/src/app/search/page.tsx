'use client';

import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import MediaDetailModal from '@/components/MediaDetailModal';
import PageHeader from '@/components/PageHeader';

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

interface SearchResult {
  id: number;
  title: string;
  name?: string;
  overview: string;
  poster_path: string | null;
  release_date?: string;
  first_air_date?: string;
  vote_average: number;
  media_type?: string;
}

interface TorrentResult {
  title: string;
  magnet: string;
  info_hash: string;
  size: number;
  seeders: number;
  leechers: number;
  quality: string;
  codec: string;
  source: string;
  audio: string;
  indexer: string;
}

export default function SearchPage() {
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get('query') || searchParams.get('q') || '');
  const debouncedQuery = useDebounce(query, 500);
  const [mediaType, setMediaType] = useState(searchParams.get('type') || 'all');
  const [selectedMedia, setSelectedMedia] = useState<SearchResult | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [sortBy, setSortBy] = useState('popularity');

  const { data: searchResults, isLoading: searchLoading } = useQuery({
    queryKey: ['search', debouncedQuery, mediaType],
    queryFn: async () => {
      if (!debouncedQuery) return [];
      const response = await api.get('/search', {
        params: { query: debouncedQuery, media_type: mediaType },
      });
      return response.data;
    },
    enabled: debouncedQuery.length > 0,
  });

  const sortedResults = useMemo(() => {
    if (!searchResults) return [];

    const results = [...searchResults];

    switch (sortBy) {
      case 'rating-desc':
        return results.sort((a, b) => (b.vote_average || 0) - (a.vote_average || 0));
      case 'rating-asc':
        return results.sort((a, b) => (a.vote_average || 0) - (b.vote_average || 0));
      case 'release-desc':
        return results.sort((a, b) => {
          const dateA = a.release_date || a.first_air_date || '';
          const dateB = b.release_date || b.first_air_date || '';
          return dateB.localeCompare(dateA);
        });
      case 'release-asc':
        return results.sort((a, b) => {
          const dateA = a.release_date || a.first_air_date || '';
          const dateB = b.release_date || b.first_air_date || '';
          return dateA.localeCompare(dateB);
        });
      case 'title':
        return results.sort((a, b) => {
          const titleA = (a.title || a.name || '').toLowerCase();
          const titleB = (b.title || b.name || '').toLowerCase();
          return titleA.localeCompare(titleB);
        });
      case 'popularity':
      default:
        return results.sort((a, b) => (b.popularity || 0) - (a.popularity || 0));
    }
  }, [searchResults, sortBy]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
  };

  const getPosterUrl = (path: string | null) => {
    if (!path) {
      return 'data:image/svg+xml;base64,' + btoa(`
        <svg xmlns="http://www.w3.org/2000/svg" width="500" height="750" viewBox="0 0 500 750">
          <rect width="500" height="750" fill="#18181b"/>
          <g transform="translate(250, 325)">
            <rect x="-75" y="-100" width="150" height="200" rx="8" fill="none" stroke="#52525b" stroke-width="6"/>
            <rect x="-65" y="-20" width="130" height="3" fill="#52525b"/>
            <rect x="-65" y="0" width="130" height="3" fill="#52525b"/>
            <rect x="-65" y="20" width="130" height="3" fill="#52525b"/>
            <circle cx="-90" cy="-85" r="10" fill="#52525b"/>
            <circle cx="-90" cy="-55" r="10" fill="#52525b"/>
            <circle cx="-90" cy="-25" r="10" fill="#52525b"/>
            <circle cx="-90" cy="5" r="10" fill="#52525b"/>
            <circle cx="-90" cy="35" r="10" fill="#52525b"/>
            <circle cx="-90" cy="65" r="10" fill="#52525b"/>
            <circle cx="90" cy="-85" r="10" fill="#52525b"/>
            <circle cx="90" cy="-55" r="10" fill="#52525b"/>
            <circle cx="90" cy="-25" r="10" fill="#52525b"/>
            <circle cx="90" cy="5" r="10" fill="#52525b"/>
            <circle cx="90" cy="35" r="10" fill="#52525b"/>
            <circle cx="90" cy="65" r="10" fill="#52525b"/>
          </g>
          <text x="250" y="520" font-family="system-ui, sans-serif" font-size="24" fill="#71717a" text-anchor="middle" font-weight="500">No Poster</text>
        </svg>
      `);
    }
    if (path.startsWith('http://') || path.startsWith('https://')) {
      return path;
    }
    return `https://image.tmdb.org/t/p/w500${path}`;
  };

  const getImageUrl = (path: string | null, size: string = 'original') => {
    if (!path) return null;
    if (path.startsWith('http://') || path.startsWith('https://')) {
      return path;
    }
    return `https://image.tmdb.org/t/p/${size}${path}`;
  };


  return (
    <div className="min-h-screen">
      <PageHeader
        title="Search"
        description="Search and add new media to your library"
        gradientFrom="emerald-600/10"
        gradientVia="green-600/10"
        gradientTo="teal-600/10"
      />

      <div className="container mx-auto px-6 py-8">
        <form onSubmit={handleSearch} className="mb-8">
        <div className="flex gap-4">
          <select
            value={mediaType}
            onChange={(e) => setMediaType(e.target.value)}
            className="px-4 py-2 border-input bg-background text-foreground border rounded"
          >
            <option value="all">All</option>
            <option value="movie">Movies</option>
            <option value="show">TV Shows</option>
            <option value="anime">Anime</option>
          </select>

          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search for movies, shows, or anime..."
            className="flex-1 px-4 py-2 border-input bg-background text-foreground border rounded"
          />

          <button
            type="submit"
            className="px-6 py-2 bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
          >
            Search
          </button>
        </div>
      </form>

      {searchLoading && <div className="text-center py-12">Searching...</div>}

      {sortedResults && sortedResults.length > 0 && (
        <>
          <div className="flex justify-between items-center mb-4">
            <p className="text-sm text-muted-foreground">
              {sortedResults.length} result{sortedResults.length !== 1 ? 's' : ''} found
            </p>
            <div className="flex items-center gap-2">
              <label htmlFor="sortBy" className="text-sm text-muted-foreground">Sort by:</label>
              <select
                id="sortBy"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-3 py-1.5 border-input bg-background text-foreground border rounded text-sm"
              >
                <option value="popularity">Popularity</option>
                <option value="rating-desc">Rating (High to Low)</option>
                <option value="rating-asc">Rating (Low to High)</option>
                <option value="release-desc">Release Date (Newest)</option>
                <option value="release-asc">Release Date (Oldest)</option>
                <option value="title">Title (A-Z)</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {sortedResults.map((result: SearchResult) => (
            <div
              key={result.id}
              onClick={() => {
                setSelectedMedia(result);
                setShowModal(true);
              }}
              className="bg-card text-card-foreground rounded-lg shadow overflow-hidden hover:shadow-lg transition cursor-pointer"
            >
              <div className="relative aspect-[2/3]">
                <img
                  src={getPosterUrl(result.poster_path)}
                  alt={result.title || result.name}
                  className="w-full h-full object-cover"
                />
              </div>
              <div className="p-3">
                <h3 className="font-semibold text-sm truncate">
                  {result.title || result.name}
                </h3>
                <div className="flex justify-between items-center mt-2">
                  <span className="text-xs text-muted-foreground">
                    {result.release_date
                      ? new Date(result.release_date).getFullYear()
                      : result.first_air_date
                      ? new Date(result.first_air_date).getFullYear()
                      : 'Unknown'}
                  </span>
                  <div className="flex items-center text-xs">
                    <svg
                      className="w-4 h-4 text-yellow-400 mr-1"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                    </svg>
                    {result.vote_average > 0 ? (
                      <span>{result.vote_average.toFixed(1)}</span>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
          </div>
        </>
      )}

      <MediaDetailModal
        media={selectedMedia}
        isOpen={showModal}
        onClose={() => {
          setShowModal(false);
          setSelectedMedia(null);
        }}
        defaultMediaType={mediaType}
      />
      </div>
    </div>
  );
}
