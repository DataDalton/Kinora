'use client';

import { useParams } from 'next/navigation';
import { useInfiniteQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import MediaDetailModal from '@/components/MediaDetailModal';

interface Media {
  id: number;
  title: string;
  name?: string;
  poster_path: string | null;
  backdrop_path: string | null;
  vote_average: number;
  release_date?: string;
  first_air_date?: string;
  media_type?: string;
  anilist_id?: number;
}

const genreConfig: Record<string, { name: string; color: string; description: string }> = {
  action: {
    name: 'Action',
    color: 'from-red-500 to-orange-600',
    description: 'High-octane thrills and intense action sequences'
  },
  comedy: {
    name: 'Comedy',
    color: 'from-yellow-500 to-amber-600',
    description: 'Laugh out loud with the funniest shows and movies'
  },
  drama: {
    name: 'Drama',
    color: 'from-purple-500 to-pink-600',
    description: 'Compelling stories and emotional narratives'
  },
  scifi: {
    name: 'Sci-Fi & Fantasy',
    color: 'from-blue-500 to-cyan-600',
    description: 'Explore futuristic worlds and magical realms'
  },
  horror: {
    name: 'Horror & Thriller',
    color: 'from-gray-700 to-gray-900',
    description: 'Spine-chilling scares and suspenseful thrillers'
  },
  romance: {
    name: 'Romance',
    color: 'from-pink-400 to-rose-600',
    description: 'Heartwarming love stories and romantic dramas'
  }
};

export default function GenrePage() {
  const params = useParams();
  const genre = params.genre as string;
  const config = genreConfig[genre] || { name: 'Unknown', color: 'from-gray-500 to-gray-700', description: '' };

  const [sortBy, setSortBy] = useState('popularity');
  const [mediaTypeFilter, setMediaTypeFilter] = useState('all');
  const [selectedMedia, setSelectedMedia] = useState<Media | null>(null);
  const [showModal, setShowModal] = useState(false);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
  } = useInfiniteQuery({
    queryKey: ['discover', 'genre', genre, sortBy, mediaTypeFilter],
    queryFn: async ({ pageParam = 1 }) => {
      const response = await api.get(`/discover/genre`, {
        params: {
          genre,
          page: pageParam,
          sort_by: sortBy,
          media_type: mediaTypeFilter
        }
      });
      return response.data;
    },
    getNextPageParam: (lastPage, allPages) => {
      if (lastPage.results && lastPage.results.length === 20) {
        return allPages.length + 1;
      }
      return undefined;
    },
    initialPageParam: 1,
  });

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { threshold: 0.1 }
    );

    const currentRef = loadMoreRef.current;
    if (currentRef) {
      observer.observe(currentRef);
    }

    return () => {
      if (currentRef) {
        observer.unobserve(currentRef);
      }
    };
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const allResults = data?.pages.flatMap(page => page.results) || [];

  const getPosterUrl = (path: string | null, isAnime: boolean = false) => {
    if (!path) return '/placeholder-poster.jpg';
    if (isAnime) return path;
    return `https://image.tmdb.org/t/p/w500${path}`;
  };

  const getBackdropUrl = (path: string | null, isAnime: boolean = false) => {
    if (!path) return null;
    if (isAnime) return path;
    return `https://image.tmdb.org/t/p/original${path}`;
  };

  const headerBackdrops = allResults.slice(0, 4).map((item: Media) => {
    const isAnime = item.media_type === 'anime';
    return getBackdropUrl(item.backdrop_path || item.poster_path, isAnime);
  }).filter(Boolean);

  const getTitle = (item: Media) => {
    return item.title || item.name || 'Unknown';
  };

  const getYear = (item: Media) => {
    const date = item.release_date || item.first_air_date;
    return date ? new Date(date).getFullYear() : '';
  };

  return (
    <div className="min-h-screen">
      {/* Header Section */}
      <div className="relative border-b-2 border-border overflow-hidden">
        {/* Background Collage */}
        {headerBackdrops.length > 0 ? (
          <div className="absolute inset-0 grid grid-cols-2 grid-rows-2">
            {headerBackdrops.map((backdrop, idx) => (
              <div
                key={idx}
                className="bg-cover bg-center"
                style={{ backgroundImage: `url(${backdrop})` }}
              />
            ))}
          </div>
        ) : (
          <div className={`absolute inset-0 bg-gradient-to-r ${config.color}/10`} />
        )}

        {/* Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/80 to-black/70" />

        {/* Content */}
        <div className="relative container mx-auto px-6 py-16">
          <Link
            href="/discover"
            className="inline-flex items-center gap-2 text-white/80 hover:text-white transition mb-6"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Discover
          </Link>
          <h1 className="text-5xl font-bold mb-3 text-white">{config.name}</h1>
          <p className="text-white/80 text-lg">{config.description}</p>
        </div>
      </div>

      {/* Content Section */}
      <div className="container mx-auto px-6 py-8">
        {/* Filters Section */}
        <div className="bg-card border-2 border-border rounded-lg p-6 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium mb-2">Sort By</label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="w-full px-4 py-2 bg-background border-2 border-border rounded-lg focus:outline-none focus:border-primary"
              >
                <option value="popularity">Most Popular</option>
                <option value="rating">Highest Rated</option>
                <option value="release_date">Newest First</option>
                <option value="title">Title (A-Z)</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Media Type</label>
              <select
                value={mediaTypeFilter}
                onChange={(e) => setMediaTypeFilter(e.target.value)}
                className="w-full px-4 py-2 bg-background border-2 border-border rounded-lg focus:outline-none focus:border-primary"
              >
                <option value="all">All Types</option>
                <option value="movie">Movies Only</option>
                <option value="show">TV Shows Only</option>
                <option value="anime">Anime Only</option>
              </select>
            </div>
          </div>
        </div>
        {isLoading ? (
          <div className="text-center py-12">Loading {config.name.toLowerCase()} content...</div>
        ) : allResults.length > 0 ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
              {allResults.map((item: Media) => {
                const isAnime = item.media_type === 'anime';
                return (
                  <div
                    key={`${item.media_type}-${item.id}`}
                    onClick={() => {
                      setSelectedMedia(item);
                      setShowModal(true);
                    }}
                    className="bg-card text-card-foreground rounded-lg shadow overflow-hidden hover:shadow-lg transition cursor-pointer"
                  >
                    <div className="relative aspect-[2/3]">
                      <img
                        src={getPosterUrl(item.poster_path, isAnime)}
                        alt={getTitle(item)}
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <div className="p-3">
                      <h3 className="font-semibold text-sm truncate" title={getTitle(item)}>
                        {getTitle(item)}
                      </h3>
                      <div className="flex justify-between items-center mt-2">
                        <span className="text-xs text-muted-foreground">{getYear(item)}</span>
                        {item.vote_average > 0 && (
                          <div className="flex items-center text-xs">
                            <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
                            </svg>
                            {item.vote_average.toFixed(1)}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Infinite Scroll Trigger */}
            <div ref={loadMoreRef} className="py-8 text-center">
              {isFetchingNextPage ? (
                <div className="text-muted-foreground">Loading more...</div>
              ) : hasNextPage ? (
                <div className="text-muted-foreground">Scroll for more</div>
              ) : (
                <div className="text-muted-foreground">No more content</div>
              )}
            </div>
          </>
        ) : (
          <div className="text-center py-12 text-muted-foreground">
            No {config.name.toLowerCase()} content available
          </div>
        )}
      </div>

      <MediaDetailModal
        media={selectedMedia}
        isOpen={showModal}
        onClose={() => {
          setShowModal(false);
          setSelectedMedia(null);
        }}
      />
    </div>
  );
}
