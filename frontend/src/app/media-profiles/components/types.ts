// Quality settings that apply to a specific media type
export interface MediaTypeQuality {
  resolutions: string[];
  codecs: string[];
  sources: string[];
  audioCodecs: string[];
  audioChannels: string[];
  hdrFormats: string[];
  editions?: string[]; // Only for movies
  minSize?: number;
  maxSize?: number;
}

export interface MediaProfileFormData {
  name: string;
  // Per-media-type quality: Movies
  movie_resolutions: string[];
  movie_codecs: string[];
  movie_sources: string[];
  movie_audio_codecs: string[];
  movie_audio_channels: string[];
  movie_hdr_formats: string[];
  movie_editions: string[];
  movie_min_size: number | null;
  movie_max_size: number | null;
  // Per-media-type quality: TV Shows
  show_resolutions: string[];
  show_codecs: string[];
  show_sources: string[];
  show_audio_codecs: string[];
  show_audio_channels: string[];
  show_hdr_formats: string[];
  show_min_size: number | null;
  show_max_size: number | null;
  // Per-media-type quality: Anime
  anime_resolutions: string[];
  anime_codecs: string[];
  anime_sources: string[];
  anime_audio_codecs: string[];
  anime_audio_channels: string[];
  anime_hdr_formats: string[];
  anime_min_size: number | null;
  anime_max_size: number | null;
  // Common settings
  languages: string[];
  subtitle_languages: string[];
  upgrade_allowed: boolean;
  // Indexers per media type
  movie_indexers: string[];
  show_indexers: string[];
  anime_indexers: string[];
  music_indexers: string[];
  // Search settings
  search_timeout: number;
  max_retries: number;
  max_results: number;
  uploader_filter: string;
  release_group_filter: string;
  custom_regex: string;
  search_sort_preference: 'weighted' | 'seeders' | 'size' | 'date';
  seeder_weight: number;
  size_weight: number;
  recency_weight: number;
  // TV options
  season_pack_preference: 'prefer' | 'only' | 'avoid';
  // File output settings
  use_hardlinks: boolean;
  illegal_char_replacement: string;
  colon_replacement: string;
  // Naming formats
  movie_naming_format: string;
  movie_folder_format: string;
  show_naming_format: string;
  show_folder_format: string;
  anime_naming_format: string;
  anime_folder_format: string;
  // Anime options
  anime_subtitle_preference: 'softsub' | 'hardsub' | 'dual_audio';
  anime_allow_hardsub: boolean;
  anime_prefer_dual_audio: boolean;
  anime_audio_language: string;
  anime_subtitle_language: string;
  // Music settings
  music_artist_folder_format: string;
  music_album_folder_format: string;
  music_track_naming_format: string;
  music_multi_disc_format: string;
  music_preferred_quality: string[];
  music_embed_lyrics: boolean;
  music_embed_artwork: boolean;
  // Torrent validation settings
  validation_enabled: boolean;
  validation_mode: 'blocklist' | 'allowlist';
  forbidden_extensions: string[];
  validation_failure_action: 'delete' | 'pause_notify' | 'quarantine';
  movie_allowed_extensions: string[];
  show_allowed_extensions: string[];
  anime_allowed_extensions: string[];
  music_allowed_extensions: string[];
}

export interface SectionProps {
  formData: MediaProfileFormData;
  setFormData: (data: MediaProfileFormData) => void;
  hasAttemptedSubmit?: boolean;
}

// Navigation structure types
export type NavigationGroup =
  | 'profile'
  | 'movies'
  | 'tvshows'
  | 'anime'
  | 'music'
  | 'search'
  | 'fileoutput';

export type ProfileTab = 'general' | 'languages' | 'validation';
export type MoviesTab = 'indexers' | 'quality' | 'naming';
export type TVShowsTab = 'indexers' | 'quality' | 'naming' | 'options';
export type AnimeTab = 'indexers' | 'quality' | 'naming' | 'options';
export type MusicTab = 'indexers' | 'quality' | 'naming';
export type SearchTab = 'sorting' | 'filters' | 'timing';
export type FileOutputTab = 'files';

export interface NavigationItem {
  id: NavigationGroup;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  tabs: {
    id: string;
    label: string;
  }[];
}
