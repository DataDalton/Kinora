'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import Link from 'next/link';

export default function HomePage() {
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: async () => {
      try {
        const [movies, shows, anime] = await Promise.all([
          api.get('/movies', { params: { limit: 1 } }),
          api.get('/shows', { params: { limit: 1 } }),
          api.get('/anime', { params: { limit: 1 } }),
        ]);

        return {
          moviesCount: movies.data.movies?.length || 0,
          showsCount: shows.data.shows?.length || 0,
          animeCount: anime.data.anime?.length || 0,
        };
      } catch (error) {
        return { moviesCount: 0, showsCount: 0, animeCount: 0 };
      }
    },
  });

  const { data: recentMovies } = useQuery({
    queryKey: ['recent-movies'],
    queryFn: async () => {
      try {
        const response = await api.get('/movies', { params: { limit: 6, page: 1 } });
        return response.data.movies || [];
      } catch (error) {
        return [];
      }
    },
  });

  const getPosterUrl = (path: string | null) => {
    if (!path) return '/placeholder-poster.jpg';
    return `https://image.tmdb.org/t/p/w500${path}`;
  };

  return (
    <div className="min-h-screen">
      {/* Header Section */}
      <div className="bg-gradient-to-r from-indigo-600/10 via-purple-600/10 to-pink-600/10 border-b-2 border-border">
        <div className="container mx-auto px-6 py-8">
          <h1 className="text-4xl font-bold mb-2">Dashboard</h1>
          <p className="text-muted-foreground">Overview of your media library</p>
        </div>
      </div>

      {/* Content Section */}
      <div className="container mx-auto px-6 py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <Link href="/movies" className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6 hover:shadow-lg hover:border-primary/50 transition">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-muted-foreground text-sm">Movies</p>
              <p className="text-3xl font-bold">{stats?.moviesCount || 0}</p>
            </div>
            <span className="text-4xl">🎬</span>
          </div>
        </Link>

        <Link href="/shows" className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6 hover:shadow-lg hover:border-primary/50 transition">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-muted-foreground text-sm">TV Shows</p>
              <p className="text-3xl font-bold">{stats?.showsCount || 0}</p>
            </div>
            <span className="text-4xl">📺</span>
          </div>
        </Link>

        <Link href="/anime" className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6 hover:shadow-lg hover:border-primary/50 transition">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-muted-foreground text-sm">Anime</p>
              <p className="text-3xl font-bold">{stats?.animeCount || 0}</p>
            </div>
            <span className="text-4xl">🎌</span>
          </div>
        </Link>
      </div>

      {recentMovies && recentMovies.length > 0 && (
        <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-bold">Recently Added</h2>
            <Link href="/movies" className="text-primary hover:underline">
              View All Movies
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
            {recentMovies.map((movie: any) => (
              <div key={movie.id} className="bg-card/50 rounded-lg overflow-hidden border border-border hover:shadow-lg hover:border-primary/50 transition">
                <img
                  src={getPosterUrl(movie.poster_path)}
                  alt={movie.title}
                  className="w-full aspect-[2/3] object-cover"
                />
                <div className="p-2">
                  <p className="text-sm font-medium truncate">{movie.title}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {(!recentMovies || recentMovies.length === 0) && (
        <div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-12 text-center">
          <h2 className="text-2xl font-bold mb-4">Welcome to Nexarr!</h2>
          <p className="text-muted-foreground mb-6">
            Start by adding movies, TV shows, or anime to your library
          </p>
          <div className="flex justify-center gap-4">
            <Link
              href="/search"
              className="px-6 py-3 bg-primary text-primary-foreground rounded hover:opacity-90"
            >
              Add Media
            </Link>
            <Link
              href="/discover"
              className="px-6 py-3 bg-secondary text-secondary-foreground rounded hover:opacity-90"
            >
              Discover Content
            </Link>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
