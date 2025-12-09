'use client';

import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import MediaDetailModal from '@/components/MediaDetailModal';
import PageHeader from '@/components/PageHeader';
import { ArrowUpDown, ChevronDown, Check, Film, Tv, Sparkles, Music2, Layers } from 'lucide-react';

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
  nb_fan?: number;
  nb_album?: number;
  nb_tracks?: number;
  artist_name?: string;
  album_name?: string;
  duration?: number;
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
  const [musicFilter, setMusicFilter] = useState<'all' | 'artist' | 'album' | 'track'>('all');
  const [selectedMedia, setSelectedMedia] = useState<SearchResult | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [sortBy, setSortBy] = useState('popularity');
  const [sortDropdownOpen, setSortDropdownOpen] = useState(false);
  const [sortHighlightedIndex, setSortHighlightedIndex] = useState(-1);
  const [mediaTypeDropdownOpen, setMediaTypeDropdownOpen] = useState(false);
  const [mediaTypeHighlightedIndex, setMediaTypeHighlightedIndex] = useState(-1);

  const isMusic = mediaType === 'music';

  const mediaTypeOptions = [
    { value: 'all', label: 'All', icon: Layers },
    { value: 'movie', label: 'Movies', icon: Film },
    { value: 'show', label: 'TV Shows', icon: Tv },
    { value: 'anime', label: 'Anime', icon: Sparkles },
    { value: 'music', label: 'Music', icon: Music2 },
  ];

  const currentMediaTypeOption = mediaTypeOptions.find(opt => opt.value === mediaType) || mediaTypeOptions[0];

  const sortOptions = isMusic
    ? [
        { value: 'popularity', label: 'Popularity' },
        { value: 'fans-desc', label: 'Fans (High to Low)' },
        { value: 'fans-asc', label: 'Fans (Low to High)' },
        { value: 'albums-desc', label: 'Albums (Most)' },
        { value: 'tracks-desc', label: 'Tracks (Most)' },
        { value: 'release-desc', label: 'Release Date (Newest)' },
        { value: 'release-asc', label: 'Release Date (Oldest)' },
        { value: 'title', label: 'Name (A-Z)' },
      ]
    : [
        { value: 'popularity', label: 'Popularity' },
        { value: 'rating-desc', label: 'Rating (High to Low)' },
        { value: 'rating-asc', label: 'Rating (Low to High)' },
        { value: 'release-desc', label: 'Release Date (Newest)' },
        { value: 'release-asc', label: 'Release Date (Oldest)' },
        { value: 'title', label: 'Title (A-Z)' },
      ];

  const currentSortLabel = sortOptions.find(opt => opt.value === sortBy)?.label || 'Sort';

  const handleSortKeyDown = (e: React.KeyboardEvent) => {
    if (!sortDropdownOpen) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault();
        setSortDropdownOpen(true);
        setSortHighlightedIndex(sortOptions.findIndex(opt => opt.value === sortBy));
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSortHighlightedIndex(prev => (prev + 1) % sortOptions.length);
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSortHighlightedIndex(prev => (prev - 1 + sortOptions.length) % sortOptions.length);
        break;
      case 'Enter':
        e.preventDefault();
        if (sortHighlightedIndex >= 0) {
          setSortBy(sortOptions[sortHighlightedIndex].value);
          setSortDropdownOpen(false);
        }
        break;
      case 'Escape':
        e.preventDefault();
        setSortDropdownOpen(false);
        break;
    }
  };

  const handleMediaTypeKeyDown = (e: React.KeyboardEvent) => {
    if (!mediaTypeDropdownOpen) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault();
        setMediaTypeDropdownOpen(true);
        setMediaTypeHighlightedIndex(mediaTypeOptions.findIndex(opt => opt.value === mediaType));
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setMediaTypeHighlightedIndex(prev => (prev + 1) % mediaTypeOptions.length);
        break;
      case 'ArrowUp':
        e.preventDefault();
        setMediaTypeHighlightedIndex(prev => (prev - 1 + mediaTypeOptions.length) % mediaTypeOptions.length);
        break;
      case 'Enter':
        e.preventDefault();
        if (mediaTypeHighlightedIndex >= 0) {
          setMediaType(mediaTypeOptions[mediaTypeHighlightedIndex].value);
          setMediaTypeDropdownOpen(false);
        }
        break;
      case 'Escape':
        e.preventDefault();
        setMediaTypeDropdownOpen(false);
        break;
    }
  };

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

    let results = [...searchResults];

    // Filter by music sub-type if music is selected
    if (isMusic && musicFilter !== 'all') {
      results = results.filter((r) => r.media_type === musicFilter);
    }

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
      case 'fans-desc':
        return results.sort((a, b) => (b.nb_fan || 0) - (a.nb_fan || 0));
      case 'fans-asc':
        return results.sort((a, b) => (a.nb_fan || 0) - (b.nb_fan || 0));
      case 'albums-desc':
        return results.sort((a, b) => (b.nb_album || 0) - (a.nb_album || 0));
      case 'tracks-desc':
        return results.sort((a, b) => (b.nb_tracks || 0) - (a.nb_tracks || 0));
      case 'popularity':
      default:
        return results.sort((a, b) => (b.popularity || b.nb_fan || 0) - (a.popularity || a.nb_fan || 0));
    }
  }, [searchResults, sortBy, isMusic, musicFilter]);

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

  const formatDuration = (seconds: number) => {
    if (!seconds) return '';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const isMusicType = (type?: string) => type === 'artist' || type === 'album' || type === 'track';


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
          {/* Media type dropdown - custom styled */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setMediaTypeDropdownOpen(!mediaTypeDropdownOpen)}
              onKeyDown={handleMediaTypeKeyDown}
              onBlur={() => setTimeout(() => setMediaTypeDropdownOpen(false), 150)}
              className="flex items-center gap-2 px-4 py-3 bg-card border-2 border-border rounded-lg hover:border-primary/50 focus:outline-none focus:border-primary transition-colors font-medium cursor-pointer min-w-[140px]"
            >
              {(() => {
                const IconComponent = currentMediaTypeOption.icon;
                return <IconComponent className="w-4 h-4 text-muted-foreground" />;
              })()}
              <span className="flex-1 text-left">{currentMediaTypeOption.label}</span>
              <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${mediaTypeDropdownOpen ? 'rotate-180' : ''}`} />
            </button>
            {mediaTypeDropdownOpen && (
              <div className="absolute left-0 top-full mt-1 w-48 bg-card border-2 border-border rounded-lg shadow-lg z-50 py-1 overflow-hidden">
                {mediaTypeOptions.map((option, index) => {
                  const IconComponent = option.icon;
                  return (
                    <button
                      key={option.value}
                      onClick={() => {
                        setMediaType(option.value);
                        setMediaTypeDropdownOpen(false);
                      }}
                      className={`w-full px-3 py-2 text-left text-sm flex items-center gap-2 transition-colors cursor-pointer ${
                        mediaTypeHighlightedIndex === index ? 'bg-muted' : ''
                      } ${
                        mediaType === option.value ? 'text-primary font-medium' : 'text-foreground hover:bg-muted'
                      }`}
                    >
                      <IconComponent className="w-4 h-4" />
                      <span className="flex-1">{option.label}</span>
                      {mediaType === option.value && <Check className="w-4 h-4" />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search for movies, shows, anime, or music..."
            className="flex-1 px-4 py-3 bg-card border-2 border-border rounded-lg focus:outline-none focus:border-primary transition-colors"
          />

          <button
            type="submit"
            className="px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium cursor-pointer"
          >
            Search
          </button>
        </div>
      </form>

      {searchLoading && <div className="text-center py-12">Searching...</div>}

      {sortedResults && sortedResults.length > 0 && (
        <>
          <div className="flex justify-between items-center mb-4 flex-wrap gap-4">
            <p className="text-sm text-muted-foreground">
              {sortedResults.length} result{sortedResults.length !== 1 ? 's' : ''} found
            </p>
            <div className="flex items-center gap-4 flex-wrap">
              {/* Music type filter - pill buttons */}
              {isMusic && (
                <div className="flex items-center gap-1 bg-card border-2 border-border rounded-lg p-1">
                  {(['all', 'artist', 'album', 'track'] as const).map((filter) => (
                    <button
                      key={filter}
                      onClick={() => setMusicFilter(filter)}
                      className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors cursor-pointer ${
                        musicFilter === filter
                          ? 'bg-primary text-primary-foreground'
                          : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                      }`}
                    >
                      {filter === 'all' ? 'All' : filter === 'artist' ? 'Artists' : filter === 'album' ? 'Albums' : 'Tracks'}
                    </button>
                  ))}
                </div>
              )}

              {/* Sort options - custom dropdown */}
              <div className="relative">
                <button
                  onClick={() => setSortDropdownOpen(!sortDropdownOpen)}
                  onKeyDown={handleSortKeyDown}
                  onBlur={() => setTimeout(() => setSortDropdownOpen(false), 150)}
                  className="flex items-center gap-2 pl-3 pr-3 py-2 bg-card border-2 border-border rounded-lg hover:border-primary/50 focus:outline-none focus:border-primary transition-colors text-sm font-medium cursor-pointer"
                >
                  <ArrowUpDown className="w-4 h-4 text-muted-foreground" />
                  <span>{currentSortLabel}</span>
                  <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${sortDropdownOpen ? 'rotate-180' : ''}`} />
                </button>
                {sortDropdownOpen && (
                  <div className="absolute right-0 top-full mt-1 w-56 bg-card border-2 border-border rounded-lg shadow-lg z-50 py-1 overflow-hidden">
                    {sortOptions.map((option, index) => (
                      <button
                        key={option.value}
                        onClick={() => {
                          setSortBy(option.value);
                          setSortDropdownOpen(false);
                        }}
                        className={`w-full px-3 py-2 text-left text-sm flex items-center justify-between transition-colors cursor-pointer ${
                          sortHighlightedIndex === index ? 'bg-muted' : ''
                        } ${
                          sortBy === option.value ? 'text-primary font-medium' : 'text-foreground hover:bg-muted'
                        }`}
                      >
                        {option.label}
                        {sortBy === option.value && <Check className="w-4 h-4" />}
                      </button>
                    ))}
                  </div>
                )}
              </div>
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
              className="bg-card text-card-foreground rounded-lg shadow border-2 border-border overflow-hidden hover:shadow-lg hover:border-primary/50 transition cursor-pointer"
            >
              <div className="relative aspect-2/3">
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
                {/* Secondary info line for music types */}
                {result.media_type === 'track' && result.artist_name && (
                  <p className="text-xs text-muted-foreground truncate">{result.artist_name}</p>
                )}
                {result.media_type === 'album' && result.artist_name && (
                  <p className="text-xs text-muted-foreground truncate">{result.artist_name}</p>
                )}
                <div className="flex justify-between items-center mt-2">
                  <span className="text-xs text-muted-foreground">
                    {result.media_type === 'artist' ? (
                      result.nb_album ? `${result.nb_album} albums` : 'Artist'
                    ) : result.media_type === 'track' ? (
                      result.duration ? formatDuration(result.duration) : 'Track'
                    ) : result.media_type === 'album' ? (
                      // Show both track count and year for albums
                      [
                        result.nb_tracks ? `${result.nb_tracks} tracks` : null,
                        result.release_date ? new Date(result.release_date).getFullYear() : null
                      ].filter(Boolean).join(' · ') || 'Album'
                    ) : result.release_date ? (
                      new Date(result.release_date).getFullYear()
                    ) : result.first_air_date ? (
                      new Date(result.first_air_date).getFullYear()
                    ) : (
                      ''
                    )}
                  </span>
                  {isMusicType(result.media_type) ? (
                    <span className="text-xs text-muted-foreground capitalize">{result.media_type}</span>
                  ) : (
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
                  )}
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
