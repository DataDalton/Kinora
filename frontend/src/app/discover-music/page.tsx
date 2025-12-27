'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import Link from 'next/link';
import PageHeader from '@/components/PageHeader';

interface Artist {
  id: number;
  name: string;
  picture?: string;
  picture_medium?: string;
  picture_big?: string;
  picture_xl?: string;
  nb_fan?: number;
  nb_album?: number;
}

interface Album {
  id: number;
  title: string;
  cover?: string;
  cover_medium?: string;
  cover_xl?: string;
  artist_name?: string;
  artist_id?: number;
  release_date?: string;
  nb_tracks?: number;
  record_type?: string;
}

interface Track {
  id: number;
  title: string;
  artist: {
    id: number;
    name: string;
  };
  album: {
    id: number;
    title: string;
    cover_medium?: string;
    cover_xl?: string;
  };
  duration: number;
  preview?: string;
  position?: number;
}

interface Genre {
  id: number;
  name: string;
  picture?: string;
  picture_medium?: string;
  picture_big?: string;
}

export default function DiscoverMusicPage() {
  const [selectedGenre, setSelectedGenre] = useState<Genre | null>(null);

  const { data: charts, isLoading: chartsLoading } = useQuery({
    queryKey: ['discover', 'music', 'charts'],
    queryFn: async () => {
      const response = await api.get('/discover/music/charts?limit=20');
      return response.data;
    },
  });

  const { data: newReleases, isLoading: newReleasesLoading } = useQuery({
    queryKey: ['discover', 'music', 'new-releases'],
    queryFn: async () => {
      const response = await api.get('/discover/music/new-releases?limit=20');
      return response.data;
    },
  });

  const { data: genres, isLoading: genresLoading } = useQuery({
    queryKey: ['discover', 'music', 'genres'],
    queryFn: async () => {
      const response = await api.get('/discover/music/genres');
      return response.data;
    },
  });

  const { data: genreArtists, isLoading: genreArtistsLoading } = useQuery({
    queryKey: ['discover', 'music', 'genre', selectedGenre?.id],
    queryFn: async () => {
      if (!selectedGenre) return null;
      const response = await api.get(`/discover/music/genre/${selectedGenre.id}?limit=20`);
      return response.data;
    },
    enabled: !!selectedGenre,
  });

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatFans = (count: number) => {
    if (count >= 1000000) {
      return `${(count / 1000000).toFixed(1)}M fans`;
    }
    if (count >= 1000) {
      return `${(count / 1000).toFixed(1)}K fans`;
    }
    return `${count} fans`;
  };

  const renderArtistGrid = (artists: Artist[], title: string, loading: boolean) => (
    <div className="mb-12">
      <h2 className="text-2xl font-bold mb-4">{title}</h2>
      {loading ? (
        <div className="text-center py-12">Loading...</div>
      ) : artists && artists.length > 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {artists.slice(0, 12).map((artist) => (
            <Link
              key={artist.id}
              href={`/search?type=music&query=${encodeURIComponent(artist.name)}`}
              className="bg-card text-card-foreground rounded-lg shadow overflow-hidden hover:shadow-lg transition group"
            >
              <div className="relative aspect-square">
                <img
                  src={artist.picture_xl || artist.picture_big || artist.picture_medium || artist.picture || '/placeholder-poster.svg'}
                  alt={artist.name}
                  className="w-full h-full object-cover rounded-t-lg"
                />
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition" />
              </div>
              <div className="p-3">
                <h3 className="font-semibold text-sm truncate" title={artist.name}>
                  {artist.name}
                </h3>
                <div className="flex justify-between items-center mt-2">
                  {artist.nb_fan && (
                    <span className="text-xs text-muted-foreground">
                      {formatFans(artist.nb_fan)}
                    </span>
                  )}
                  {artist.nb_album && (
                    <span className="text-xs text-muted-foreground">
                      {artist.nb_album} albums
                    </span>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-muted-foreground">No artists available</div>
      )}
    </div>
  );

  const renderAlbumGrid = (albums: Album[], title: string, loading: boolean) => (
    <div className="mb-12">
      <h2 className="text-2xl font-bold mb-4">{title}</h2>
      {loading ? (
        <div className="text-center py-12">Loading...</div>
      ) : albums && albums.length > 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {albums.slice(0, 12).map((album) => (
            <Link
              key={album.id}
              href={`/search?type=music&query=${encodeURIComponent(album.title)}`}
              className="bg-card text-card-foreground rounded-lg shadow overflow-hidden hover:shadow-lg transition group"
            >
              <div className="relative aspect-square">
                <img
                  src={album.cover_xl || album.cover_medium || album.cover || '/placeholder-poster.svg'}
                  alt={album.title}
                  className="w-full h-full object-cover"
                />
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition" />
              </div>
              <div className="p-3">
                <h3 className="font-semibold text-sm truncate" title={album.title}>
                  {album.title}
                </h3>
                {album.artist_name && (
                  <p className="text-xs text-muted-foreground truncate mt-1">{album.artist_name}</p>
                )}
                <div className="flex justify-between items-center mt-2">
                  {album.release_date && (
                    <span className="text-xs text-muted-foreground">
                      {new Date(album.release_date).getFullYear()}
                    </span>
                  )}
                  {album.nb_tracks && (
                    <span className="text-xs text-muted-foreground">
                      {album.nb_tracks} tracks
                    </span>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-muted-foreground">No albums available</div>
      )}
    </div>
  );

  const renderTrackList = (tracks: Track[], title: string, loading: boolean) => (
    <div className="mb-12">
      <h2 className="text-2xl font-bold mb-4">{title}</h2>
      {loading ? (
        <div className="text-center py-12">Loading...</div>
      ) : tracks && tracks.length > 0 ? (
        <div className="bg-card rounded-lg shadow overflow-hidden">
          <div className="divide-y divide-border">
            {tracks.slice(0, 10).map((track, index) => (
              <Link
                key={track.id}
                href={`/search?type=music&query=${encodeURIComponent(track.title + ' ' + track.artist?.name)}`}
                className="flex items-center gap-4 p-4 hover:bg-accent/50 transition"
              >
                <span className="w-8 text-center text-muted-foreground font-medium">
                  {index + 1}
                </span>
                <img
                  src={track.album?.cover_medium || track.album?.cover_xl || '/placeholder-poster.svg'}
                  alt={track.album?.title}
                  className="w-12 h-12 rounded object-cover"
                />
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-sm truncate">{track.title}</h3>
                  <p className="text-xs text-muted-foreground truncate">{track.artist?.name}</p>
                </div>
                <span className="text-sm text-muted-foreground">
                  {formatDuration(track.duration)}
                </span>
              </Link>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-center py-12 text-muted-foreground">No tracks available</div>
      )}
    </div>
  );

  const renderGenreGrid = (genreList: Genre[], loading: boolean) => (
    <div className="mb-12">
      <h2 className="text-2xl font-bold mb-4">Browse by Genre</h2>
      {loading ? (
        <div className="text-center py-12">Loading...</div>
      ) : genreList && genreList.length > 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-3">
          {genreList.filter((g: Genre) => g.id !== 0).slice(0, 16).map((genre) => (
            <button
              key={genre.id}
              onClick={() => setSelectedGenre(selectedGenre?.id === genre.id ? null : genre)}
              className={`relative rounded-lg overflow-hidden aspect-square group cursor-pointer transition-all ${
                selectedGenre?.id === genre.id
                  ? 'ring-2 ring-primary ring-offset-2 ring-offset-background'
                  : 'hover:scale-105'
              }`}
            >
              <img
                src={genre.picture_big || genre.picture_medium || genre.picture || '/placeholder-poster.svg'}
                alt={genre.name}
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-linear-to-t from-black/80 via-black/40 to-transparent" />
              <div className="absolute bottom-0 left-0 right-0 p-2">
                <h3 className="text-sm font-bold text-white text-center truncate">{genre.name}</h3>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-muted-foreground">No genres available</div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen">
      <PageHeader
        title="Discover Music"
        description="Explore top charts, new releases, and genres"
        gradientFrom="purple-600/10"
        gradientVia="pink-600/10"
        gradientTo="rose-600/10"
      />

      <div className="container mx-auto px-6 py-8">
        {renderGenreGrid(genres?.results || [], genresLoading)}

        {selectedGenre && (
          <div className="mb-12">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold">Top {selectedGenre.name} Artists</h2>
              <button
                onClick={() => setSelectedGenre(null)}
                className="text-sm text-muted-foreground hover:text-foreground transition cursor-pointer"
              >
                Clear filter
              </button>
            </div>
            {genreArtistsLoading ? (
              <div className="text-center py-12">Loading...</div>
            ) : genreArtists?.results && genreArtists.results.length > 0 ? (
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                {genreArtists.results.slice(0, 12).map((artist: Artist) => (
                  <Link
                    key={artist.id}
                    href={`/search?type=music&query=${encodeURIComponent(artist.name)}`}
                    className="bg-card text-card-foreground rounded-lg shadow overflow-hidden hover:shadow-lg transition group"
                  >
                    <div className="relative aspect-square">
                      <img
                        src={artist.picture_xl || artist.picture_big || artist.picture_medium || artist.picture || '/placeholder-poster.svg'}
                        alt={artist.name}
                        className="w-full h-full object-cover rounded-t-lg"
                      />
                    </div>
                    <div className="p-3">
                      <h3 className="font-semibold text-sm truncate" title={artist.name}>
                        {artist.name}
                      </h3>
                      {artist.nb_fan && (
                        <span className="text-xs text-muted-foreground">
                          {formatFans(artist.nb_fan)}
                        </span>
                      )}
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">No artists found for this genre</div>
            )}
          </div>
        )}

        {renderTrackList(charts?.tracks || [], 'Top Tracks', chartsLoading)}
        {renderArtistGrid(charts?.artists || [], 'Top Artists', chartsLoading)}
        {renderAlbumGrid(charts?.albums || [], 'Top Albums', chartsLoading)}
        {renderAlbumGrid(newReleases?.results || [], 'New Releases', newReleasesLoading)}
      </div>
    </div>
  );
}
