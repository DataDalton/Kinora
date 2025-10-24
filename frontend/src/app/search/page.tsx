'use client';

import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

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
  const queryClient = useQueryClient();
  const [query, setQuery] = useState(searchParams.get('query') || '');
  const debouncedQuery = useDebounce(query, 500);
  const [mediaType, setMediaType] = useState(searchParams.get('type') || 'movie');
  const [selectedMedia, setSelectedMedia] = useState<SearchResult | null>(null);
  const [showTorrents, setShowTorrents] = useState(false);
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [autoSearch, setAutoSearch] = useState(true);
  const [addCollection, setAddCollection] = useState(false);
  const [sortBy, setSortBy] = useState('popularity');

  // Fetch all media profiles
  const { data: profiles } = useQuery({
    queryKey: ['media-profiles'],
    queryFn: async () => {
      const response = await api.get('/media-profiles');
      return response.data;
    },
  });

  // Load last used profile for this media type from localStorage
  useEffect(() => {
    const savedProfileId = localStorage.getItem(`lastProfile_${mediaType}`);
    if (savedProfileId && profiles) {
      const profileExists = profiles.find((p: any) => p.id === parseInt(savedProfileId));
      if (profileExists) {
        setSelectedProfileId(parseInt(savedProfileId));
      } else if (profiles.length > 0) {
        setSelectedProfileId(profiles[0].id);
      }
    } else if (profiles && profiles.length > 0) {
      setSelectedProfileId(profiles[0].id);
    }
  }, [mediaType, profiles]);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showDetails) {
        setShowDetails(false);
        setSelectedMedia(null);
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [showDetails]);

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

  const { data: mediaDetails, isLoading: detailsLoading } = useQuery({
    queryKey: ['media-details', selectedMedia?.id, selectedMedia?.media_type || mediaType],
    queryFn: async () => {
      if (!selectedMedia) return null;
      const type = selectedMedia.media_type || mediaType;
      const response = await api.get(`/search/details/${type}/${selectedMedia.id}`);
      return response.data;
    },
    enabled: showDetails && !!selectedMedia,
  });

  const { data: collectionDetails, isLoading: collectionLoading } = useQuery({
    queryKey: ['collection-details', mediaDetails?.collection_id],
    queryFn: async () => {
      if (!mediaDetails?.collection_id) return null;
      const response = await api.get(`/search/collection/${mediaDetails.collection_id}`);
      return response.data;
    },
    enabled: showAddModal && !!mediaDetails?.collection_id && addCollection,
  });

  const { data: torrentResults, isLoading: torrentLoading } = useQuery({
    queryKey: ['torrents', selectedMedia?.title, mediaType],
    queryFn: async () => {
      if (!selectedMedia) return { results: [], indexers_searched: [] };
      const title = selectedMedia.title || selectedMedia.name;
      const year = selectedMedia.release_date
        ? new Date(selectedMedia.release_date).getFullYear()
        : selectedMedia.first_air_date
        ? new Date(selectedMedia.first_air_date).getFullYear()
        : undefined;

      const response = await api.get('/search/torrents', {
        params: { query: title, year, category: mediaType },
      });
      return response.data;
    },
    enabled: showTorrents && !!selectedMedia,
  });

  const addMediaMutation = useMutation({
    mutationFn: async (data: { tmdb_id: number; monitored: boolean; media_profile_id?: number }) => {
      const type = selectedMedia?.media_type || mediaType;
      const endpoint = type === 'movie' ? '/movies' : type === 'show' ? '/shows' : '/anime';
      const response = await api.post(endpoint, data);
      return response.data;
    },
    onSuccess: () => {
      const type = selectedMedia?.media_type || mediaType;
      if (selectedProfileId) {
        localStorage.setItem(`lastProfile_${type}`, selectedProfileId.toString());
      }
      queryClient.invalidateQueries({ queryKey: [type === 'movie' ? 'movies' : type === 'show' ? 'shows' : 'anime'] });
      alert('Added to library successfully!');
      setSelectedMedia(null);
      setShowDetails(false);
      setShowAddModal(false);
      setShowTorrents(false);
    },
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSelectedMedia(null);
    setShowTorrents(false);
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

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const formatRuntime = (minutes: number) => {
    if (!minutes) return '';
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };

  return (
    <div className="min-h-screen">
      <div className="bg-gradient-to-r from-emerald-600/10 via-green-600/10 to-teal-600/10 border-b-2 border-border">
        <div className="container mx-auto px-6 py-8">
          <h1 className="text-4xl font-bold">Search</h1>
          <p className="text-muted-foreground mt-2">Search and add new media to your library</p>
        </div>
      </div>

      <div className="container mx-auto px-6 py-8">
        <form onSubmit={handleSearch} className="mb-8">
        <div className="flex gap-4">
          <select
            value={mediaType}
            onChange={(e) => setMediaType(e.target.value)}
            className="px-4 py-2 border-input bg-background text-foreground border rounded"
          >
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
            className="px-6 py-2 bg-primary text-primary-foreground rounded hover:opacity-90"
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
                setShowDetails(true);
                setShowTorrents(false);
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

      {showDetails && mediaDetails && (
        <div
          className="fixed inset-0 backdrop-blur-sm bg-background/20 z-50 overflow-y-auto"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setShowDetails(false);
              setSelectedMedia(null);
            }
          }}
        >
          <div
            className="min-h-screen p-4"
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                setShowDetails(false);
                setSelectedMedia(null);
              }
            }}
          >
            <div className="relative bg-background/95 backdrop-blur-sm rounded-lg max-w-6xl mx-auto mt-8 mb-8 overflow-hidden border border-border shadow-2xl">
              <button
                onClick={() => {
                  setShowDetails(false);
                  setSelectedMedia(null);
                }}
                className="absolute top-4 left-4 z-20 px-4 py-2 bg-background/90 hover:bg-background text-foreground rounded-lg border border-border shadow-lg cursor-pointer transition-all hover:scale-105"
              >
                ← Back to Results
              </button>

              {mediaDetails.backdrop_path ? (
                <div className="relative h-96">
                  <img
                    src={getImageUrl(mediaDetails.backdrop_path, 'original') || ''}
                    alt={mediaDetails.title || mediaDetails.name}
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-background via-background/60 to-transparent" />
                </div>
              ) : (
                <div className="relative h-96 bg-gradient-to-br from-muted/50 to-muted flex items-center justify-center">
                  <div className="text-center text-muted-foreground">
                    <svg className="w-16 h-16 mx-auto mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <p className="text-sm">No backdrop image available</p>
                  </div>
                </div>
              )}

              <div className="p-8 relative z-10">
                <div className="flex gap-6">
                  <img
                    src={getPosterUrl(mediaDetails.poster_path)}
                    alt={mediaDetails.title || mediaDetails.name}
                    className="w-64 h-96 object-cover rounded-lg shadow-2xl"
                  />

                  <div className="flex-1">
                    <h1 className="text-4xl font-bold mb-2">{mediaDetails.title || mediaDetails.name}</h1>
                    {mediaDetails.tagline && (
                      <p className="text-muted-foreground italic mb-4">{mediaDetails.tagline}</p>
                    )}

                    <div className="flex items-center gap-4 mb-4">
                      <div className="flex items-center">
                        <svg className="w-5 h-5 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        {mediaDetails.vote_average > 0 ? (
                          <>
                            <span className="font-semibold">{mediaDetails.vote_average.toFixed(1)}</span>
                            {mediaDetails.vote_count && <span className="text-muted-foreground ml-1">({mediaDetails.vote_count} votes)</span>}
                          </>
                        ) : (
                          <span className="text-muted-foreground">No rating</span>
                        )}
                      </div>
                      {mediaDetails.runtime && <span>{formatRuntime(mediaDetails.runtime)}</span>}
                      <span>
                        {mediaDetails.release_date ? (
                          new Date(mediaDetails.release_date).getFullYear()
                        ) : (
                          <span className="text-muted-foreground">Release date unknown</span>
                        )}
                      </span>
                    </div>

                    {mediaDetails.genres && mediaDetails.genres.length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-4">
                        {mediaDetails.genres.map((genre: any, index: number) => (
                          <span key={genre.id || `${genre.name || genre}-${index}`} className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm">
                            {genre.name || genre}
                          </span>
                        ))}
                      </div>
                    )}

                    <p className="text-foreground/90 mb-6">{mediaDetails.overview}</p>

                    <div className="flex gap-4">
                      <button
                        onClick={() => {
                          setShowAddModal(true);
                        }}
                        className="px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 cursor-pointer transition-all hover:scale-105"
                      >
                        Add to Library
                      </button>
                    </div>
                  </div>
                </div>

                {mediaDetails.media_type !== 'anime' && (
                  <>
                    {mediaDetails.cast && mediaDetails.cast.length > 0 ? (
                      <div className="mt-8">
                        <h2 className="text-2xl font-bold mb-4">Cast</h2>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                          {mediaDetails.cast.map((person: any) => (
                            <div key={person.id || person.name?.full} className="text-center">
                              {person.profile_path || person.image?.large ? (
                                <img
                                  src={person.profile_path ? getImageUrl(person.profile_path, 'w185') || '' : person.image?.large}
                                  alt={person.name || person.name?.full}
                                  className="w-full aspect-[2/3] object-cover rounded-lg mb-2"
                                />
                              ) : (
                                <div className="w-full aspect-[2/3] bg-muted rounded-lg mb-2 flex items-center justify-center">
                                  <span className="text-muted-foreground text-4xl">👤</span>
                                </div>
                              )}
                              <p className="font-semibold text-sm">{person.name || person.name?.full}</p>
                              {person.character && <p className="text-xs text-muted-foreground">{person.character}</p>}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="mt-8 p-6 bg-muted/30 rounded-lg text-center">
                        <p className="text-muted-foreground">No cast information available</p>
                      </div>
                    )}
                  </>
                )}

                {mediaDetails.media_type === 'anime' && (
                  <>
                    {mediaDetails.characters && mediaDetails.characters.length > 0 ? (
                      <div className="mt-8">
                        <h2 className="text-2xl font-bold mb-4">Characters</h2>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                          {mediaDetails.characters.map((character: any) => (
                            <div key={character.id} className="text-center">
                              {character.image?.large ? (
                                <img
                                  src={character.image.large}
                                  alt={character.name?.full}
                                  className="w-full aspect-[2/3] object-cover rounded-lg mb-2"
                                />
                              ) : (
                                <div className="w-full aspect-[2/3] bg-muted rounded-lg mb-2 flex items-center justify-center">
                                  <span className="text-muted-foreground text-4xl">👤</span>
                                </div>
                              )}
                              <p className="font-semibold text-sm">{character.name?.full}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="mt-8 p-6 bg-muted/30 rounded-lg text-center">
                        <p className="text-muted-foreground">No character information available</p>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {showAddModal && mediaDetails && (
        <div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-[60] flex items-center justify-center p-4">
          <div className="bg-background rounded-lg max-w-2xl w-full border border-border shadow-2xl p-6">
            <h2 className="text-2xl font-bold mb-4">Add to Library</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold mb-2">Media Profile</label>
                <select
                  value={selectedProfileId || ''}
                  onChange={(e) => setSelectedProfileId(parseInt(e.target.value))}
                  className="w-full px-4 py-3 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
                >
                  {!profiles || profiles.length === 0 ? (
                    <option value="">No profiles available</option>
                  ) : (
                    <>
                      <option value="">Select a profile...</option>
                      {profiles.map((profile: any) => (
                        <option key={profile.id} value={profile.id}>
                          {profile.name}
                        </option>
                      ))}
                    </>
                  )}
                </select>
                <p className="text-xs text-muted-foreground mt-1">
                  Quality profile for downloads
                </p>
              </div>

              <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                <input
                  type="checkbox"
                  id="autoSearch"
                  checked={autoSearch}
                  onChange={(e) => setAutoSearch(e.target.checked)}
                  className="w-4 h-4 cursor-pointer"
                />
                <label htmlFor="autoSearch" className="flex-1 cursor-pointer">
                  <div className="font-semibold">Start search automatically</div>
                  <div className="text-xs text-muted-foreground">Search for torrents and send to download client immediately</div>
                </label>
              </div>

              {mediaDetails.collection_id && (mediaDetails.media_type === 'movie' || mediaType === 'movie') && (
                <div className="space-y-3">
                  <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                    <input
                      type="checkbox"
                      id="addCollection"
                      checked={addCollection}
                      onChange={(e) => setAddCollection(e.target.checked)}
                      className="w-4 h-4 cursor-pointer"
                    />
                    <label htmlFor="addCollection" className="flex-1 cursor-pointer">
                      <div className="font-semibold">Add entire collection</div>
                      <div className="text-xs text-muted-foreground">
                        {mediaDetails.collection_name ? `Add all movies from "${mediaDetails.collection_name}"` : 'Add all movies from this collection'}
                      </div>
                    </label>
                  </div>

                  {addCollection && collectionDetails && (
                    <div className="p-4 bg-muted/30 rounded-lg border border-border">
                      <h3 className="font-semibold mb-3 text-sm">Collection Preview ({collectionDetails.parts?.length || 0} movies):</h3>
                      <div className="max-h-48 overflow-y-auto space-y-2">
                        {collectionDetails.parts?.map((movie: any) => (
                          <div key={movie.id} className="flex items-center gap-3 p-2 bg-background/50 rounded">
                            {movie.poster_path && (
                              <img
                                src={getImageUrl(movie.poster_path, 'w92') || ''}
                                alt={movie.title}
                                className="w-8 h-12 object-cover rounded"
                              />
                            )}
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-sm truncate">{movie.title}</p>
                              <p className="text-xs text-muted-foreground">
                                {movie.release_date ? new Date(movie.release_date).getFullYear() : 'TBA'}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {addCollection && collectionLoading && (
                    <div className="p-4 bg-muted/30 rounded-lg text-center text-sm text-muted-foreground">
                      Loading collection details...
                    </div>
                  )}
                </div>
              )}

              <div className="flex gap-3 pt-4">
                <button
                  onClick={() => {
                    if (!selectedProfileId) {
                      alert('Please select a media profile');
                      return;
                    }
                    addMediaMutation.mutate({
                      tmdb_id: mediaDetails.id,
                      monitored: true,
                      media_profile_id: selectedProfileId
                    });
                  }}
                  disabled={addMediaMutation.isPending || !selectedProfileId}
                  className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer transition-all hover:scale-105"
                >
                  {addMediaMutation.isPending ? 'Adding...' : 'Add to Library'}
                </button>
                <button
                  onClick={() => {
                    setShowAddModal(false);
                    setAutoSearch(true);
                    setAddCollection(false);
                  }}
                  className="px-6 py-3 bg-muted text-foreground rounded-lg hover:opacity-90 cursor-pointer transition-all hover:scale-105"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {selectedMedia && showTorrents && (
        <div className="mt-8">
          <div className="bg-card text-card-foreground rounded-lg shadow p-6 mb-6">
            <div className="flex gap-6">
              <img
                src={getPosterUrl(selectedMedia.poster_path)}
                alt={selectedMedia.title || selectedMedia.name}
                className="w-32 h-48 object-cover rounded"
              />
              <div className="flex-1">
                <h2 className="text-2xl font-bold mb-2">
                  {selectedMedia.title || selectedMedia.name}
                </h2>
                <p className="text-muted-foreground mb-4">{selectedMedia.overview}</p>

                <div className="flex gap-4 items-center">
                  <div className="flex-1">
                    <label className="block text-sm font-semibold mb-2">Media Profile</label>
                    <select
                      value={selectedProfileId || ''}
                      onChange={(e) => setSelectedProfileId(parseInt(e.target.value))}
                      className="w-full px-4 py-2 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
                    >
                      {!profiles || profiles.length === 0 ? (
                        <option value="">No profiles available</option>
                      ) : (
                        profiles.map((profile: any) => (
                          <option key={profile.id} value={profile.id}>
                            {profile.name}
                          </option>
                        ))
                      )}
                    </select>
                    <p className="text-xs text-muted-foreground mt-1">
                      Last used profile for {mediaType === 'movie' ? 'movies' : mediaType === 'show' ? 'TV shows' : 'anime'}
                    </p>
                  </div>

                  <div className="pt-6">
                    <button
                      onClick={() => addMediaMutation.mutate({
                        tmdb_id: selectedMedia.id,
                        monitored: true,
                        media_profile_id: selectedProfileId || undefined
                      })}
                      disabled={addMediaMutation.isPending || !selectedProfileId}
                      className="px-6 py-2 bg-primary text-primary-foreground rounded hover:opacity-90 disabled:opacity-50 whitespace-nowrap"
                    >
                      {addMediaMutation.isPending ? 'Adding...' : 'Add to Library'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <h3 className="text-xl font-bold mb-4">Available Torrents</h3>

          {torrentLoading && <div className="text-center py-12">Finding torrents...</div>}

          {torrentResults && torrentResults.results && torrentResults.results.length > 0 ? (
            <div className="space-y-2">
              {torrentResults.results.map((torrent: TorrentResult, index: number) => (
                <div key={index} className="bg-card text-card-foreground rounded-lg shadow p-4 hover:shadow-md transition">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h4 className="font-semibold text-sm mb-2">{torrent.title}</h4>
                      <div className="flex gap-4 text-xs text-muted-foreground">
                        <span className="px-2 py-1 bg-primary/10 text-primary rounded">
                          {torrent.quality}
                        </span>
                        <span>{torrent.codec}</span>
                        <span>{torrent.source}</span>
                        <span>{torrent.audio}</span>
                        <span>{formatBytes(torrent.size)}</span>
                        <span className="text-green-600">↑ {torrent.seeders}</span>
                        <span className="text-red-600">↓ {torrent.leechers}</span>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <span className="text-xs px-2 py-1 bg-muted text-muted-foreground rounded">{torrent.indexer}</span>
                      <button
                        onClick={() => window.open(torrent.magnet, '_blank')}
                        className="px-4 py-2 bg-primary text-primary-foreground text-sm rounded hover:opacity-90"
                      >
                        Download
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            !torrentLoading && <div className="text-center py-12 text-muted-foreground">No torrents found</div>
          )}
        </div>
      )}
      </div>
    </div>
  );
}
