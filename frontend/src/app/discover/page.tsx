'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import Link from 'next/link';
import MediaDetailModal from '@/components/MediaDetailModal';
import PageHeader from '@/components/PageHeader';

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

export default function DiscoverPage() {
  const [selectedMedia, setSelectedMedia] = useState<Media | null>(null);
  const [showModal, setShowModal] = useState(false);

  const { data: trending, isLoading: trendingLoading } = useQuery({
    queryKey: ['discover', 'trending'],
    queryFn: async () => {
      const response = await api.get('/discover/trending');
      return response.data;
    },
  });

  const { data: popular, isLoading: popularLoading } = useQuery({
    queryKey: ['discover', 'popular'],
    queryFn: async () => {
      const response = await api.get('/discover/popular');
      return response.data;
    },
  });

  const { data: upcoming, isLoading: upcomingLoading } = useQuery({
    queryKey: ['discover', 'upcoming'],
    queryFn: async () => {
      const response = await api.get('/discover/upcoming');
      return response.data;
    },
  });

  const { data: topRated, isLoading: topRatedLoading } = useQuery({
    queryKey: ['discover', 'top-rated'],
    queryFn: async () => {
      const response = await api.get('/discover/top-rated');
      return response.data;
    },
  });

  const { data: popularMovies, isLoading: popularMoviesLoading } = useQuery({
    queryKey: ['discover', 'popular', 'movie'],
    queryFn: async () => {
      const response = await api.get('/discover/popular?media_type=movie');
      return response.data;
    },
  });

  const { data: popularShows, isLoading: popularShowsLoading } = useQuery({
    queryKey: ['discover', 'popular', 'show'],
    queryFn: async () => {
      const response = await api.get('/discover/popular?media_type=show');
      return response.data;
    },
  });

  const { data: popularAnime, isLoading: popularAnimeLoading } = useQuery({
    queryKey: ['discover', 'popular', 'anime'],
    queryFn: async () => {
      const response = await api.get('/discover/popular?media_type=anime');
      return response.data;
    },
  });

  const { data: actionGenre } = useQuery({
    queryKey: ['discover', 'genre', 'action'],
    queryFn: async () => {
      const response = await api.get('/discover/genre?genre=action');
      return response.data;
    },
  });

  const { data: comedyGenre } = useQuery({
    queryKey: ['discover', 'genre', 'comedy'],
    queryFn: async () => {
      const response = await api.get('/discover/genre?genre=comedy');
      return response.data;
    },
  });

  const { data: dramaGenre } = useQuery({
    queryKey: ['discover', 'genre', 'drama'],
    queryFn: async () => {
      const response = await api.get('/discover/genre?genre=drama');
      return response.data;
    },
  });

  const { data: scifiGenre } = useQuery({
    queryKey: ['discover', 'genre', 'scifi'],
    queryFn: async () => {
      const response = await api.get('/discover/genre?genre=scifi');
      return response.data;
    },
  });

  const { data: horrorGenre } = useQuery({
    queryKey: ['discover', 'genre', 'horror'],
    queryFn: async () => {
      const response = await api.get('/discover/genre?genre=horror');
      return response.data;
    },
  });

  const { data: romanceGenre } = useQuery({
    queryKey: ['discover', 'genre', 'romance'],
    queryFn: async () => {
      const response = await api.get('/discover/genre?genre=romance');
      return response.data;
    },
  });

  const getPosterUrl = (path: string | null, isAnime: boolean = false) => {
    if (!path) return '/placeholder-poster.jpg';
    if (isAnime) return path;
    return `https://image.tmdb.org/t/p/w500${path}`;
  };

  const getTitle = (item: Media) => {
    return item.title || item.name || 'Unknown';
  };

  const getYear = (item: Media) => {
    const date = item.release_date || item.first_air_date;
    return date ? new Date(date).getFullYear() : '';
  };

  const getDetailUrl = (item: Media) => {
    const mediaType = item.media_type || 'movie';

    if (mediaType === 'movie') {
      return `/movies/${item.id}`;
    } else if (mediaType === 'show' || mediaType === 'tv') {
      return `/shows/${item.id}`;
    } else if (mediaType === 'anime') {
      return `/anime/${item.anilist_id || item.id}`;
    }

    return `/search?query=${encodeURIComponent(getTitle(item))}`;
  };

  const renderGenreCard = (genre: string, genreData: any, title: string) => {
    const posters = genreData?.results?.slice(0, 4).map((item: Media) => {
      const isAnime = item.media_type === 'anime';
      return getPosterUrl(item.poster_path, isAnime);
    }) || [];

    return (
      <Link
        href={`/discover/${genre}`}
        className="relative rounded-lg overflow-hidden aspect-[3/2] group hover:shadow-xl transition transform hover:scale-105"
      >
        <div className="absolute inset-0 grid grid-cols-2 grid-rows-2 gap-1">
          {posters.map((poster: string, idx: number) => (
            <div
              key={idx}
              className="bg-cover bg-center"
              style={{ backgroundImage: `url(${poster})` }}
            />
          ))}
          {posters.length === 0 && (
            <div className="col-span-2 row-span-2 bg-gradient-to-br from-gray-700 to-gray-900" />
          )}
        </div>
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent" />
        <div className="absolute bottom-0 left-0 right-0 p-4">
          <h3 className="text-xl font-bold text-white">{title}</h3>
        </div>
      </Link>
    );
  };

  const renderMediaGrid = (items: Media[], title: string, loading: boolean) => (
    <div className="mb-12">
      <h2 className="text-2xl font-bold mb-4">{title}</h2>
      {loading ? (
        <div className="text-center py-12">Loading...</div>
      ) : items && items.length > 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {items.slice(0, 12).map((item) => {
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
      ) : (
        <div className="text-center py-12 text-muted-foreground">No content available</div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen">
      <PageHeader
        title="Discover"
        description="Explore trending and popular content across all categories"
        gradientFrom="cyan-600/10"
        gradientVia="blue-600/10"
        gradientTo="indigo-600/10"
      />

      {/* Content Section */}
      <div className="container mx-auto px-6 py-8">
        {/* Browse by Genre/Category */}
        <div className="mb-12">
          <h2 className="text-2xl font-bold mb-4">Browse by Category</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
            {renderGenreCard('action', actionGenre, 'Action')}
            {renderGenreCard('comedy', comedyGenre, 'Comedy')}
            {renderGenreCard('drama', dramaGenre, 'Drama')}
            {renderGenreCard('scifi', scifiGenre, 'Sci-Fi')}
            {renderGenreCard('horror', horrorGenre, 'Horror')}
            {renderGenreCard('romance', romanceGenre, 'Romance')}
          </div>
        </div>

        {renderMediaGrid(trending?.results || [], 'Trending Now', trendingLoading)}
        {renderMediaGrid(popular?.results || [], 'Popular Across All Media', popularLoading)}
        {renderMediaGrid(topRated?.results || [], 'Top Rated', topRatedLoading)}
        {renderMediaGrid(upcoming?.results || [], 'Upcoming Movies', upcomingLoading)}

        {/* Media type sections */}
        {renderMediaGrid(popularMovies?.results || [], 'Popular Movies', popularMoviesLoading)}
        {renderMediaGrid(popularShows?.results || [], 'Popular TV Shows', popularShowsLoading)}
        {renderMediaGrid(popularAnime?.results || [], 'Popular Anime', popularAnimeLoading)}
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
