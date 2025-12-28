'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useState, useEffect } from 'react';
import Toast from './Toast';
import { Folder, HardDrive } from 'lucide-react';
import { usePermissions } from '@/contexts/PermissionContext';
import { createRequest } from '@/lib/api/requests';

interface Media {
  id: number;
  title?: string;
  name?: string;
  poster_path: string | null;
  backdrop_path: string | null;
  media_type?: string;
  anilist_id?: number;
}

interface RootFolder {
  id: number;
  mediaType: string;
  name: string;
  rootPath: string;
  downloadPath: string;
  freeSpaceBytes: number | null;
  totalSpaceBytes: number | null;
  isDefault: boolean;
  isActive: boolean;
  healthStatus: string;
}

interface MediaDetailModalProps {
  media: Media | null;
  isOpen: boolean;
  onClose: () => void;
  defaultMediaType?: string;
}

const formatBytes = (bytes: number | null): string => {
  if (bytes === null || bytes === undefined) return 'Unknown';
  const gb = bytes / (1024 * 1024 * 1024);
  if (gb >= 1000) {
    return `${(gb / 1024).toFixed(1)} TB`;
  }
  return `${gb.toFixed(1)} GB`;
};

export default function MediaDetailModal({ media, isOpen, onClose, defaultMediaType = 'movie' }: MediaDetailModalProps) {
  const queryClient = useQueryClient();
  const { canManage, canRequest, canDownload } = usePermissions();
  const [showAddModal, setShowAddModal] = useState(false);
  const [showRequestModal, setShowRequestModal] = useState(false);
  const [requestNotes, setRequestNotes] = useState('');
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);
  const [selectedFolderId, setSelectedFolderId] = useState<number | null>(null);
  const [autoSearch, setAutoSearch] = useState(true);
  const [addCollection, setAddCollection] = useState(false);
  const [navigationStack, setNavigationStack] = useState<Media[]>([]);
  const [currentMedia, setCurrentMedia] = useState<Media | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);
  const [isSubmittingRequest, setIsSubmittingRequest] = useState(false);

  const displayMedia = currentMedia || media;
  const mediaType = displayMedia?.media_type || defaultMediaType;

  // Permission-based action determination
  // canManage/canDownload = direct add capability, canRequest = request-only capability
  const getPermissionMediaType = () => {
    if (mediaType === 'artist' || mediaType === 'album' || mediaType === 'track') return 'music';
    if (mediaType === 'show') return 'shows';
    if (mediaType === 'movie') return 'movies';
    return mediaType;
  };
  const permissionMediaType = getPermissionMediaType();
  const canDirectAdd = canManage(permissionMediaType) || canDownload(permissionMediaType);
  const canRequestAdd = canRequest(permissionMediaType) && !canDirectAdd;

  const showToast = (message: string, type: 'success' | 'error' | 'info') => {
    setToast(null);
    setTimeout(() => {
      setToast({ message, type });
    }, 0);
  };

  // Parse genres from various formats (JSON string, array of objects, or array of strings)
  const parseGenres = (genres: any): string[] => {
    if (!genres) return [];

    // If it's a string, try to parse as JSON
    if (typeof genres === 'string') {
      try {
        genres = JSON.parse(genres);
      } catch {
        return [genres]; // Return as single genre if not valid JSON
      }
    }

    // If it's not an array, return empty
    if (!Array.isArray(genres)) return [];

    // Map to genre names (handles both {id, name} objects and plain strings)
    return genres.map((g: any) => (typeof g === 'object' ? g.name : g)).filter(Boolean);
  };

  useEffect(() => {
    if (isOpen && media) {
      setCurrentMedia(media);
      setNavigationStack([]);
    }
  }, [isOpen, media]);

  const { data: profiles } = useQuery({
    queryKey: ['media-profiles'],
    queryFn: async () => {
      const response = await api.get('/media-profiles');
      return response.data;
    },
  });

  // Get the backend media type for folder lookup (music types map to 'music')
  const getFolderMediaType = () => {
    if (mediaType === 'artist' || mediaType === 'album' || mediaType === 'track') return 'music';
    if (mediaType === 'show') return 'shows';
    if (mediaType === 'movie') return 'movies';
    return mediaType;
  };

  const { data: rootFolders } = useQuery<RootFolder[]>({
    queryKey: ['root-folders', getFolderMediaType()],
    queryFn: async () => {
      const response = await api.get(`/root-folders?media_type=${getFolderMediaType()}`);
      const folders = response.data;
      // Transform snake_case to camelCase
      return folders.map((f: any) => ({
        id: f.id,
        mediaType: f.media_type,
        name: f.name,
        rootPath: f.root_path,
        downloadPath: f.download_path,
        freeSpaceBytes: f.free_space_bytes,
        totalSpaceBytes: f.total_space_bytes,
        isDefault: f.is_default,
        isActive: f.is_active,
        healthStatus: f.health_status,
      }));
    },
    enabled: showAddModal,
  });

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

  // Set folder selection when modal opens - default to automatic (null) unless user previously overrode
  useEffect(() => {
    if (rootFolders && rootFolders.length > 0) {
      const savedFolderId = localStorage.getItem(`lastFolder_${getFolderMediaType()}`);
      if (savedFolderId && savedFolderId !== 'automatic') {
        const folderExists = rootFolders.find(f => f.id === parseInt(savedFolderId) && f.isActive);
        if (folderExists) {
          setSelectedFolderId(parseInt(savedFolderId));
          return;
        }
      }
      // Default to automatic (null) - let selection mode decide
      setSelectedFolderId(null);
    }
  }, [rootFolders]);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  const { data: mediaDetails, isLoading: detailsLoading } = useQuery({
    queryKey: ['media-details', displayMedia?.id, mediaType],
    queryFn: async () => {
      if (!displayMedia) return null;
      const response = await api.get(`/search/details/${mediaType}/${displayMedia.id}`);
      return response.data;
    },
    enabled: isOpen && !!displayMedia,
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

  const addMediaMutation = useMutation({
    mutationFn: async (data: { tmdb_id?: number; deezer_id?: number; monitored: boolean; media_profile_id?: number }) => {
      let endpoint: string;
      if (mediaType === 'movie') endpoint = '/movies';
      else if (mediaType === 'show') endpoint = '/shows';
      else if (mediaType === 'anime') endpoint = '/anime';
      else if (mediaType === 'album') endpoint = '/music/albums';
      else if (mediaType === 'artist') endpoint = '/music/artists';
      else if (mediaType === 'track') endpoint = '/music/tracks';
      else endpoint = '/movies';

      const response = await api.post(endpoint, data);
      return response.data;
    },
    onSuccess: (data) => {
      if (selectedProfileId) {
        localStorage.setItem(`lastProfile_${mediaType}`, selectedProfileId.toString());
      }
      // Store folder preference - 'automatic' if using selection mode, otherwise the folder id
      localStorage.setItem(`lastFolder_${getFolderMediaType()}`, selectedFolderId ? selectedFolderId.toString() : 'automatic');
      const queryKey = mediaType === 'movie' ? 'movies' : mediaType === 'show' ? 'shows' : mediaType === 'album' ? 'albums' : mediaType === 'artist' ? 'artists' : mediaType === 'track' ? 'tracks' : 'anime';
      queryClient.invalidateQueries({ queryKey: [queryKey] });

      // Show count of related seasons added for anime
      if (mediaType === 'anime' && data.total_added > 1) {
        showToast(`Added ${data.total_added} entries to library (including ${data.related_added} related seasons)!`, 'success');
      } else {
        showToast('Added to library successfully!', 'success');
      }
      onClose();
      setShowAddModal(false);
    },
  });

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

  const formatRuntime = (minutes: number) => {
    if (!minutes) return '';
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };

  const formatDuration = (seconds: number) => {
    if (!seconds) return '';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatFans = (count: number) => {
    if (!count) return '0';
    if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
    if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
    return count.toLocaleString();
  };

  const isMusic = mediaType === 'artist' || mediaType === 'album' || mediaType === 'track';

  const handleBack = () => {
    if (navigationStack.length > 0) {
      const previous = navigationStack[navigationStack.length - 1];
      setCurrentMedia(previous);
      setNavigationStack(navigationStack.slice(0, -1));
    } else {
      onClose();
    }
  };

  const handleRecommendationClick = (item: any) => {
    if (currentMedia) {
      setNavigationStack([...navigationStack, currentMedia]);
    }
    setCurrentMedia({
      id: item.id,
      title: item.title || item.name,
      name: item.title || item.name,
      poster_path: item.poster_path,
      backdrop_path: item.backdrop_path,
      media_type: mediaDetails.media_type
    });
  };

  if (!isOpen || !media) return null;

  return (
    <>
      <div
        className="fixed inset-0 backdrop-blur-sm bg-background/20 z-50 overflow-y-auto"
        onClick={(e) => {
          if (e.target === e.currentTarget) {
            handleBack();
          }
        }}
      >
        <div
          className="min-h-screen p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              handleBack();
            }
          }}
        >
          <div className="relative bg-background/95 backdrop-blur-sm rounded-lg max-w-6xl mx-auto mt-8 mb-8 overflow-hidden border border-border shadow-2xl">
            <button
              onClick={handleBack}
              className="absolute top-4 left-4 z-20 px-4 py-2 bg-background/90 hover:bg-background text-foreground rounded-lg border border-border shadow-lg cursor-pointer transition-all hover:scale-105"
            >
              ← {navigationStack.length > 0 ? 'Back' : 'Close'}
            </button>

            {detailsLoading ? (
              <div className="p-12 text-center">Loading details...</div>
            ) : mediaDetails ? (
              <>
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

                      <div className="flex items-center gap-4 mb-4 flex-wrap">
                        {isMusic ? (
                          <>
                            {mediaDetails.nb_fan && (
                              <div className="flex items-center">
                                <svg className="w-5 h-5 text-pink-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                  <path fillRule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clipRule="evenodd" />
                                </svg>
                                <span className="font-semibold">{formatFans(mediaDetails.nb_fan)}</span>
                                <span className="text-muted-foreground ml-1">fans</span>
                              </div>
                            )}
                            {mediaDetails.fans && (
                              <div className="flex items-center">
                                <svg className="w-5 h-5 text-pink-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                  <path fillRule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clipRule="evenodd" />
                                </svg>
                                <span className="font-semibold">{formatFans(mediaDetails.fans)}</span>
                                <span className="text-muted-foreground ml-1">fans</span>
                              </div>
                            )}
                            {mediaDetails.nb_album && (
                              <span>{mediaDetails.nb_album} albums</span>
                            )}
                            {mediaDetails.nb_tracks && (
                              <span>{mediaDetails.nb_tracks} tracks</span>
                            )}
                            {mediaDetails.duration && (
                              <span>{Math.floor(mediaDetails.duration / 60)} min</span>
                            )}
                            {mediaDetails.release_date && (
                              <span>{new Date(mediaDetails.release_date).getFullYear()}</span>
                            )}
                            {mediaDetails.label && (
                              <span className="text-muted-foreground">{mediaDetails.label}</span>
                            )}
                          </>
                        ) : (
                          <>
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
                              ) : mediaDetails.first_air_date ? (
                                new Date(mediaDetails.first_air_date).getFullYear()
                              ) : (
                                <span className="text-muted-foreground">Release date unknown</span>
                              )}
                            </span>
                          </>
                        )}
                      </div>

                      {(() => {
                        const genres = parseGenres(mediaDetails.genres);
                        return genres.length > 0 && (
                          <div className="flex flex-wrap gap-2 mb-4">
                            {genres.map((genre: string, index: number) => (
                              <span key={`${genre}-${index}`} className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm">
                                {genre}
                              </span>
                            ))}
                          </div>
                        );
                      })()}

                      <p className="text-foreground/90 mb-6">{mediaDetails.overview}</p>

                      <div className="flex gap-4">
                        {canDirectAdd && (
                          <button
                            onClick={() => setShowAddModal(true)}
                            className="px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 cursor-pointer transition-all hover:scale-105"
                          >
                            Add to Library
                          </button>
                        )}
                        {canRequestAdd && (
                          <button
                            onClick={() => setShowRequestModal(true)}
                            className="px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 cursor-pointer transition-all hover:scale-105"
                          >
                            Request
                          </button>
                        )}
                        {!canDirectAdd && !canRequestAdd && (
                          <button
                            disabled
                            className="px-6 py-3 bg-muted text-muted-foreground rounded-lg cursor-not-allowed"
                          >
                            No Permission
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Artist Top Tracks */}
                  {mediaDetails.media_type === 'artist' && mediaDetails.top_tracks && mediaDetails.top_tracks.length > 0 && (
                    <div className="mt-8 px-8">
                      <h2 className="text-2xl font-bold mb-4">Top Tracks</h2>
                      <div className="bg-card rounded-lg overflow-hidden">
                        <div className="divide-y divide-border">
                          {mediaDetails.top_tracks.map((track: any, index: number) => (
                            <div key={track.id} className="flex items-center gap-4 p-4 hover:bg-accent/50 transition">
                              <span className="w-8 text-center text-muted-foreground font-medium">
                                {index + 1}
                              </span>
                              {track.album?.cover_medium && (
                                <img
                                  src={track.album.cover_medium}
                                  alt={track.album.title}
                                  className="w-12 h-12 rounded object-cover"
                                />
                              )}
                              <div className="flex-1 min-w-0">
                                <h3 className="font-medium text-sm truncate">{track.title}</h3>
                                {track.album?.title && (
                                  <p className="text-xs text-muted-foreground truncate">{track.album.title}</p>
                                )}
                              </div>
                              <span className="text-sm text-muted-foreground">
                                {formatDuration(track.duration)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Artist Albums */}
                  {mediaDetails.media_type === 'artist' && mediaDetails.albums && mediaDetails.albums.length > 0 && (
                    <div className="mt-8 px-8">
                      <h2 className="text-2xl font-bold mb-4">Albums</h2>
                      <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
                        {mediaDetails.albums.map((album: any) => (
                          <div
                            key={album.id}
                            className="cursor-pointer group"
                            onClick={() => {
                              if (currentMedia) {
                                setNavigationStack([...navigationStack, currentMedia]);
                              }
                              setCurrentMedia({
                                id: album.id,
                                title: album.title,
                                name: album.title,
                                poster_path: album.cover_xl || album.cover,
                                backdrop_path: album.cover_xl,
                                media_type: 'album'
                              });
                            }}
                          >
                            <img
                              src={album.cover_xl || album.cover || '/placeholder-poster.svg'}
                              alt={album.title}
                              className="w-full aspect-square object-cover rounded-lg mb-2 group-hover:scale-105 transition-transform"
                            />
                            <p className="font-semibold text-xs line-clamp-2">{album.title}</p>
                            {album.release_date && (
                              <p className="text-xs text-muted-foreground">{new Date(album.release_date).getFullYear()}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Album Track List */}
                  {mediaDetails.media_type === 'album' && mediaDetails.tracks && mediaDetails.tracks.length > 0 && (
                    <div className="mt-8 px-8">
                      <h2 className="text-2xl font-bold mb-4">Tracks</h2>
                      <div className="bg-card rounded-lg overflow-hidden">
                        <div className="divide-y divide-border">
                          {mediaDetails.tracks.map((track: any) => (
                            <div key={track.id} className="flex items-center gap-4 p-4 hover:bg-accent/50 transition">
                              <span className="w-8 text-center text-muted-foreground font-medium">
                                {track.track_position}
                              </span>
                              <div className="flex-1 min-w-0">
                                <h3 className="font-medium text-sm truncate">
                                  {track.title}
                                  {track.explicit_lyrics && (
                                    <span className="ml-2 px-1.5 py-0.5 text-xs bg-muted rounded">E</span>
                                  )}
                                </h3>
                              </div>
                              <span className="text-sm text-muted-foreground">
                                {formatDuration(track.duration)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Album Artist Link */}
                  {mediaDetails.media_type === 'album' && mediaDetails.artist && (
                    <div className="mt-8 px-8">
                      <h2 className="text-2xl font-bold mb-4">Artist</h2>
                      <div
                        className="flex items-center gap-4 p-4 bg-card rounded-lg cursor-pointer hover:bg-accent/50 transition"
                        onClick={() => {
                          if (currentMedia) {
                            setNavigationStack([...navigationStack, currentMedia]);
                          }
                          setCurrentMedia({
                            id: mediaDetails.artist.id,
                            title: mediaDetails.artist.name,
                            name: mediaDetails.artist.name,
                            poster_path: mediaDetails.artist.picture_xl || mediaDetails.artist.picture,
                            backdrop_path: mediaDetails.artist.picture_xl,
                            media_type: 'artist'
                          });
                        }}
                      >
                        {mediaDetails.artist.picture && (
                          <img
                            src={mediaDetails.artist.picture_xl || mediaDetails.artist.picture}
                            alt={mediaDetails.artist.name}
                            className="w-16 h-16 rounded-full object-cover"
                          />
                        )}
                        <div>
                          <h3 className="font-semibold">{mediaDetails.artist.name}</h3>
                          <p className="text-sm text-muted-foreground">View artist</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Track Album Link */}
                  {mediaDetails.media_type === 'track' && mediaDetails.album && (
                    <div className="mt-8 px-8">
                      <h2 className="text-2xl font-bold mb-4">From Album</h2>
                      <div
                        className="flex items-center gap-4 p-4 bg-card rounded-lg cursor-pointer hover:bg-accent/50 transition"
                        onClick={() => {
                          if (currentMedia) {
                            setNavigationStack([...navigationStack, currentMedia]);
                          }
                          setCurrentMedia({
                            id: mediaDetails.album.id,
                            title: mediaDetails.album.title,
                            name: mediaDetails.album.title,
                            poster_path: mediaDetails.album.cover_xl || mediaDetails.album.cover,
                            backdrop_path: mediaDetails.album.cover_xl,
                            media_type: 'album'
                          });
                        }}
                      >
                        {mediaDetails.album.cover && (
                          <img
                            src={mediaDetails.album.cover_xl || mediaDetails.album.cover}
                            alt={mediaDetails.album.title}
                            className="w-16 h-16 rounded object-cover"
                          />
                        )}
                        <div>
                          <h3 className="font-semibold">{mediaDetails.album.title}</h3>
                          <p className="text-sm text-muted-foreground">
                            {mediaDetails.album.release_date ? new Date(mediaDetails.album.release_date).getFullYear() + ' · ' : ''}View album
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Track Artist Link */}
                  {mediaDetails.media_type === 'track' && mediaDetails.artist && (
                    <div className="mt-8 px-8">
                      <h2 className="text-2xl font-bold mb-4">Artist</h2>
                      <div
                        className="flex items-center gap-4 p-4 bg-card rounded-lg cursor-pointer hover:bg-accent/50 transition"
                        onClick={() => {
                          if (currentMedia) {
                            setNavigationStack([...navigationStack, currentMedia]);
                          }
                          setCurrentMedia({
                            id: mediaDetails.artist.id,
                            title: mediaDetails.artist.name,
                            name: mediaDetails.artist.name,
                            poster_path: mediaDetails.artist.picture_xl || mediaDetails.artist.picture,
                            backdrop_path: mediaDetails.artist.picture_xl,
                            media_type: 'artist'
                          });
                        }}
                      >
                        {mediaDetails.artist.picture && (
                          <img
                            src={mediaDetails.artist.picture_xl || mediaDetails.artist.picture}
                            alt={mediaDetails.artist.name}
                            className="w-16 h-16 rounded-full object-cover"
                          />
                        )}
                        <div>
                          <h3 className="font-semibold">{mediaDetails.artist.name}</h3>
                          <p className="text-sm text-muted-foreground">View artist</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {mediaDetails.media_type !== 'anime' && !isMusic && (
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

                  {mediaDetails.media_type === 'anime' && !isMusic && (
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

                  {!isMusic && mediaDetails.recommendations && mediaDetails.recommendations.length > 0 && (
                    <div className="mt-8">
                      <h2 className="text-2xl font-bold mb-4">Recommendations</h2>
                      <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
                        {mediaDetails.recommendations.map((item: any) => (
                          <div
                            key={item.id}
                            className="cursor-pointer group"
                            onClick={() => handleRecommendationClick(item)}
                          >
                            <img
                              src={getPosterUrl(item.poster_path)}
                              alt={item.title || item.name}
                              className="w-full aspect-[2/3] object-cover rounded-lg mb-2 group-hover:scale-105 transition-transform"
                            />
                            <p className="font-semibold text-xs line-clamp-2">{item.title || item.name}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </>
            ) : null}
          </div>
        </div>
      </div>

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
                  className="w-full px-4 py-3 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary cursor-pointer"
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

              <div>
                <label className="block text-sm font-semibold mb-2">Root Folder</label>
                <select
                  value={selectedFolderId ?? ''}
                  onChange={(e) => setSelectedFolderId(e.target.value ? parseInt(e.target.value) : null)}
                  className="w-full px-4 py-3 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary cursor-pointer"
                >
                  {!rootFolders || rootFolders.length === 0 ? (
                    <option value="">No folders configured</option>
                  ) : (
                    <>
                      <option value="">Use Selection Mode</option>
                      {rootFolders.filter(f => f.isActive).map((folder) => (
                        <option key={folder.id} value={folder.id}>
                          {folder.name} - {formatBytes(folder.freeSpaceBytes)} free
                        </option>
                      ))}
                    </>
                  )}
                </select>
                {selectedFolderId === null && rootFolders && rootFolders.length > 0 ? (
                  <div className="mt-2 p-2 bg-primary/10 rounded-lg">
                    <p className="text-xs text-primary">
                      Folder will be selected automatically based on your configured selection mode
                    </p>
                  </div>
                ) : selectedFolderId && rootFolders ? (
                  <div className="mt-2 p-2 bg-muted/50 rounded-lg">
                    {(() => {
                      const folder = rootFolders.find(f => f.id === selectedFolderId);
                      if (!folder) return null;
                      return (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <Folder className="w-3 h-3" />
                          <span className="truncate">{folder.rootPath}</span>
                          <span className={`ml-auto px-1.5 py-0.5 rounded text-xs ${
                            folder.healthStatus === 'healthy' ? 'bg-green-500/20 text-green-500' :
                            folder.healthStatus === 'warning' ? 'bg-yellow-500/20 text-yellow-500' :
                            folder.healthStatus === 'error' ? 'bg-red-500/20 text-red-500' :
                            'bg-gray-500/20 text-gray-500'
                          }`}>
                            {folder.healthStatus}
                          </span>
                        </div>
                      );
                    })()}
                  </div>
                ) : null}
                <p className="text-xs text-muted-foreground mt-1">
                  Where files will be stored after download
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
                      showToast('Please select a media profile', 'info');
                      return;
                    }

                    if (mediaType === 'artist') {
                      addMediaMutation.mutate({
                        name: mediaDetails.name,
                        deezer_id: mediaDetails.id,
                        picture: mediaDetails.picture,
                        picture_medium: mediaDetails.picture_medium,
                        picture_big: mediaDetails.picture_big,
                        picture_xl: mediaDetails.picture_xl || mediaDetails.poster_path,
                        nb_album: mediaDetails.nb_album,
                        nb_fan: mediaDetails.nb_fan,
                        monitored: autoSearch,
                        media_profile_id: selectedProfileId,
                        root_folder_id: selectedFolderId
                      } as any);
                    } else if (mediaType === 'album') {
                      addMediaMutation.mutate({
                        title: mediaDetails.title || mediaDetails.name,
                        deezer_id: mediaDetails.id,
                        cover: mediaDetails.cover || mediaDetails.poster_path,
                        cover_medium: mediaDetails.cover_medium,
                        cover_big: mediaDetails.cover_big,
                        cover_xl: mediaDetails.cover_xl || mediaDetails.poster_path,
                        release_date: mediaDetails.release_date,
                        artist_id: mediaDetails.artist?.id,
                        nb_tracks: mediaDetails.nb_tracks,
                        monitored: autoSearch,
                        media_profile_id: selectedProfileId,
                        root_folder_id: selectedFolderId
                      } as any);
                    } else if (mediaType === 'track') {
                      addMediaMutation.mutate({
                        title: mediaDetails.title || mediaDetails.name,
                        deezer_id: mediaDetails.id,
                        duration: mediaDetails.duration,
                        track_position: mediaDetails.track_position,
                        disk_number: mediaDetails.disk_number,
                        isrc: mediaDetails.isrc,
                        explicit_lyrics: mediaDetails.explicit_lyrics,
                        preview: mediaDetails.preview,
                        artist_name: mediaDetails.artist?.name,
                        album_id: mediaDetails.album?.id,
                        album_title: mediaDetails.album?.title,
                        monitored: autoSearch,
                        media_profile_id: selectedProfileId,
                        root_folder_id: selectedFolderId
                      } as any);
                    } else if (addCollection && collectionDetails?.parts?.length > 0) {
                      // Add all movies from the collection
                      const addPromises = collectionDetails.parts.map((movie: any) =>
                        api.post('/movies', {
                          tmdb_id: movie.id,
                          monitored: autoSearch,
                          media_profile_id: selectedProfileId,
                          root_folder_id: selectedFolderId
                        }).catch(() => null)
                      );
                      Promise.all(addPromises).then((results) => {
                        const successCount = results.filter(r => r !== null).length;
                        localStorage.setItem(`lastFolder_${getFolderMediaType()}`, selectedFolderId ? selectedFolderId.toString() : 'automatic');
                        queryClient.invalidateQueries({ queryKey: ['movies'] });
                        showToast(`Added ${successCount} of ${collectionDetails.parts.length} movies to library!`, 'success');
                        onClose();
                        setShowAddModal(false);
                      });
                    } else if (mediaType === 'anime') {
                      addMediaMutation.mutate({
                        anilist_id: mediaDetails.id,
                        monitored: autoSearch,
                        media_profile_id: selectedProfileId,
                        root_folder_id: selectedFolderId,
                        add_sequels: true
                      } as any);
                    } else {
                      addMediaMutation.mutate({
                        tmdb_id: mediaDetails.id,
                        monitored: autoSearch,
                        media_profile_id: selectedProfileId,
                        root_folder_id: selectedFolderId
                      });
                    }
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
                    // Reset folder selection to automatic on cancel
                    setSelectedFolderId(null);
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

      {/* Request Modal */}
      {showRequestModal && mediaDetails && (
        <div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-[60] flex items-center justify-center p-4">
          <div className="bg-background rounded-lg max-w-md w-full border border-border shadow-2xl p-6">
            <h2 className="text-2xl font-bold mb-2">Request {mediaDetails.title || mediaDetails.name}</h2>
            <p className="text-muted-foreground text-sm mb-6">
              Your request will be sent to an administrator for approval.
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold mb-2">Notes (optional)</label>
                <textarea
                  value={requestNotes}
                  onChange={(e) => setRequestNotes(e.target.value)}
                  placeholder="Add a note for the approver..."
                  className="w-full px-4 py-3 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary resize-none h-24"
                />
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={async () => {
                    setIsSubmittingRequest(true);
                    try {
                      // Determine the correct media type for the request
                      const requestMediaType = mediaType === 'show' ? 'show' :
                                                mediaType === 'anime' ? 'anime' :
                                                mediaType === 'album' ? 'album' : 'movie';

                      await createRequest({
                        mediaType: requestMediaType,
                        externalId: mediaDetails.id,
                        title: mediaDetails.title || mediaDetails.name,
                        posterPath: mediaDetails.poster_path || mediaDetails.cover_xl || mediaDetails.picture_xl,
                        year: mediaDetails.release_date ? new Date(mediaDetails.release_date).getFullYear() :
                              mediaDetails.first_air_date ? new Date(mediaDetails.first_air_date).getFullYear() : undefined,
                        overview: mediaDetails.overview,
                        requestNotes: requestNotes || undefined,
                      });
                      showToast('Request submitted for approval', 'success');
                      setShowRequestModal(false);
                      setRequestNotes('');
                      onClose();
                    } catch (error: any) {
                      showToast(error?.response?.data?.detail || 'Failed to submit request', 'error');
                    } finally {
                      setIsSubmittingRequest(false);
                    }
                  }}
                  disabled={isSubmittingRequest}
                  className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer transition-all hover:scale-105"
                >
                  {isSubmittingRequest ? 'Submitting...' : 'Submit Request'}
                </button>
                <button
                  onClick={() => {
                    setShowRequestModal(false);
                    setRequestNotes('');
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

      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-4 right-4 z-[70]">
          <Toast
            message={toast.message}
            type={toast.type}
            onClose={() => setToast(null)}
          />
        </div>
      )}
    </>
  );
}
