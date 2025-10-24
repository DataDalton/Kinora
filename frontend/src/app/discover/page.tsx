'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import Link from 'next/link';

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
}

export default function DiscoverPage() {
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

  const getPosterUrl = (path: string | null) => {
    if (!path) return '/placeholder-poster.jpg';
    return `https://image.tmdb.org/t/p/w500${path}`;
  };

  const getTitle = (item: Media) => {
    return item.title || item.name || 'Unknown';
  };

  const getYear = (item: Media) => {
    const date = item.release_date || item.first_air_date;
    return date ? new Date(date).getFullYear() : '';
  };

  const renderMediaGrid = (items: Media[], title: string, loading: boolean) => (
    <div className="mb-12">
      <h2 className="text-2xl font-bold mb-4">{title}</h2>
      {loading ? (
        <div className="text-center py-12">Loading...</div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {items?.slice(0, 12).map((item) => (
            <Link
              key={item.id}
              href={`/search?query=${encodeURIComponent(getTitle(item))}`}
              className="bg-card text-card-foreground rounded-lg shadow overflow-hidden hover:shadow-lg transition cursor-pointer"
            >
              <div className="relative aspect-[2/3]">
                <img
                  src={getPosterUrl(item.poster_path)}
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
            </Link>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen">
      {/* Header Section */}
      <div className="bg-gradient-to-r from-cyan-600/10 via-blue-600/10 to-indigo-600/10 border-b-2 border-border">
        <div className="container mx-auto px-6 py-8">
          <h1 className="text-4xl font-bold mb-2">Discover</h1>
          <p className="text-muted-foreground">Explore trending and popular content across all categories</p>
        </div>
      </div>

      {/* Content Section */}
      <div className="container mx-auto px-6 py-8">
        {renderMediaGrid(trending?.results || [], 'Trending Now', trendingLoading)}
        {renderMediaGrid(popular?.results || [], 'Popular', popularLoading)}

        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
          <Link
            href="/discover/movies"
            className="bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg p-8 text-white hover:shadow-xl transition"
          >
            <h3 className="text-2xl font-bold mb-2">Movies</h3>
            <p className="text-blue-100">Explore and discover movies</p>
          </Link>

          <Link
            href="/discover/shows"
            className="bg-gradient-to-r from-green-500 to-teal-600 rounded-lg p-8 text-white hover:shadow-xl transition"
          >
            <h3 className="text-2xl font-bold mb-2">TV Shows</h3>
            <p className="text-green-100">Browse popular TV series</p>
          </Link>

          <Link
            href="/discover/anime"
            className="bg-gradient-to-r from-pink-500 to-red-600 rounded-lg p-8 text-white hover:shadow-xl transition"
          >
            <h3 className="text-2xl font-bold mb-2">Anime</h3>
            <p className="text-pink-100">Discover anime series and movies</p>
          </Link>
        </div>
      </div>
    </div>
  );
}
