import { MediaProfileFormData } from './types';

// Naming format defaults - single source of truth
export const DEFAULT_NAMING = {
  movie: {
    folder: '{Movie CleanTitle} ({Release Year}) [tmdbid-{TmdbId}]',
    file: '{Movie CleanTitle} ({Release Year}) [tmdbid-{TmdbId}] - {Edition Tags} {[Quality Full]}{[MediaInfo AudioCodec} {MediaInfo AudioChannels]}{[MediaInfo VideoDynamicRangeType]}{[MediaInfo VideoCodec]}{-Release Group}',
  },
  show: {
    folder: '{Show Title} ({Release Year}) [tvdbid-{TvdbId}]',
    file: '{Show Title} - S{Season}E{Episode} - {Episode Title}',
  },
  anime: {
    folder: '{Anime Title} ({Release Year}) [anilistid-{AnilistId}]',
    file: '{Movie CleanTitle} ({Release Year}) [tmdbid-{TmdbId}] - {Edition Tags} {[Quality Full]}{[MediaInfo AudioCodec} {MediaInfo AudioChannels]}{MediaInfo AudioLanguages}{[MediaInfo VideoDynamicRangeType]}[{MediaInfo VideoCodec }{MediaInfo VideoBitDepth}bit]{-Release Group}',
  },
  music: {
    artistFolder: '{artist}',
    albumFolder: '{album} ({year})',
    track: '{track:00} - {title}',
    multiDisc: '{disc:00}-{track:00} - {title}',
  },
};

// Naming presets for each media type
export const MOVIE_PRESETS = [
  {
    name: 'Jellyfin Default',
    folder: DEFAULT_NAMING.movie.folder,
    file: DEFAULT_NAMING.movie.file,
  },
  {
    name: 'Plex Default',
    folder: '{Movie CleanTitle} ({Release Year})',
    file: '{Movie CleanTitle} ({Release Year})',
  },
  {
    name: 'Detailed',
    folder: '{Movie CleanTitle} ({Release Year}) [tmdbid-{TmdbId}]',
    file: '{Movie CleanTitle} ({Release Year}) - [{Quality Full}][{MediaInfo VideoCodec} {MediaInfo VideoBitDepth}bit][{MediaInfo AudioCodec} {MediaInfo AudioChannels}]{-Release Group}',
  },
];

export const SHOW_PRESETS = [
  {
    name: 'Jellyfin Default',
    folder: DEFAULT_NAMING.show.folder,
    file: DEFAULT_NAMING.show.file,
  },
  {
    name: 'Plex Default',
    folder: '{Show Title} ({Release Year})',
    file: '{Show Title} - S{Season:00}E{Episode:00} - {Episode Title}',
  },
  {
    name: 'Detailed',
    folder: '{Show Title} ({Release Year}) [tvdbid-{TvdbId}]',
    file: '{Show Title} - S{Season:00}E{Episode:00} - {Episode Title} [{Quality Full}][{MediaInfo VideoCodec}]{-Release Group}',
  },
];

export const ANIME_PRESETS = [
  {
    name: 'Jellyfin Default',
    folder: DEFAULT_NAMING.anime.folder,
    file: DEFAULT_NAMING.anime.file,
  },
  {
    name: 'Simple',
    folder: '{Anime Title} ({Release Year})',
    file: '{Anime Title} - S{Season}E{Episode} - {Episode Title}',
  },
  {
    name: 'Absolute Numbering',
    folder: '{Anime Title} ({Release Year}) [anilistid-{AnilistId}]',
    file: '{Anime Title} - {Absolute Episode} - {Episode Title} [{Quality Resolution}][{MediaInfo VideoCodec} {MediaInfo VideoBitDepth}bit]{-Release Group}',
  },
  {
    name: 'Detailed (10bit)',
    folder: '{Anime Title} ({Release Year}) [anilistid-{AnilistId}]',
    file: '{Anime Title} ({Release Year}) - [{Quality Full}][{MediaInfo VideoCodec} {MediaInfo VideoBitDepth}bit][{MediaInfo AudioCodec} {MediaInfo AudioChannels}][{MediaInfo AudioLanguages}]{-Release Group}',
  },
];

export const MUSIC_PRESETS = {
  artist: [
    { name: 'Simple', format: DEFAULT_NAMING.music.artistFolder },
    { name: 'With Genre', format: '{genre}/{artist}' },
  ],
  album: [
    { name: 'Name (Year)', format: DEFAULT_NAMING.music.albumFolder },
    { name: 'Year - Name', format: '{year} - {album}' },
    { name: 'Name Only', format: '{album}' },
  ],
  track: [
    { name: 'Number - Title', format: DEFAULT_NAMING.music.track },
    { name: 'Title Only', format: '{title}' },
    { name: 'Artist - Title', format: '{artist} - {title}' },
  ],
  multiDisc: [
    { name: 'Disc-Track - Title', format: DEFAULT_NAMING.music.multiDisc },
    { name: 'Disc.Track - Title', format: '{disc}.{track:00} - {title}' },
    { name: 'Track Only', format: '{track:00} - {title}' },
  ],
};

// Quality options
export const RESOLUTIONS = ['4320p', '2160p', '1080p', '720p', '576p', '480p', '360p', '240p'];
export const SOURCES = ['REMUX', 'BLURAY', 'WEB-DL', 'WEBRIP', 'DVD', 'HDTV', 'SDTV', 'DVDSCR', 'SCREENER', 'TELESYNC', 'CAM'];
export const VIDEO_CODECS = ['AV1', 'HEVC', 'x265', 'H265', 'x264', 'H264', 'XVID'];
export const AUDIO_CODECS = ['FLAC', 'TrueHD', 'Dolby Atmos', 'DTS-HD MA', 'DTS', 'AC3', 'AAC', 'MP3'];
export const AUDIO_CHANNELS = ['Atmos', '7.1', '5.1', '2.0'];
export const HDR_FORMATS = ['Dolby Vision', 'DV HDR', 'HDR10+', 'HDR10', 'SDR'];
export const SPECIAL_EDITIONS = ['IMAX', 'Remastered', "Director's Cut", 'Unrated', 'Extended', 'Theatrical'];
export const MUSIC_QUALITY = ['flac', 'mp3_320', 'mp3_256', 'mp3_128', 'aac', 'ogg'];

// Indexers by media type
export const INDEXERS_BY_TYPE = {
  movies: ['1337x', 'YTS', 'Rutracker'],
  shows: ['1337x', 'Rutracker'],
  anime: ['Nyaa'],
  music: ['1337x'],
};

// Default form data factory function
export const createDefaultFormData = (defaultLanguage: string = 'en'): MediaProfileFormData => ({
  name: '',
  // Per-media-type quality: Movies
  movie_resolutions: [],
  movie_codecs: [],
  movie_sources: [],
  movie_audio_codecs: [],
  movie_audio_channels: [],
  movie_hdr_formats: [],
  movie_editions: [],
  movie_min_size: null,
  movie_max_size: null,
  // Per-media-type quality: TV Shows
  show_resolutions: [],
  show_codecs: [],
  show_sources: [],
  show_audio_codecs: [],
  show_audio_channels: [],
  show_hdr_formats: [],
  show_min_size: null,
  show_max_size: null,
  // Per-media-type quality: Anime
  anime_resolutions: [],
  anime_codecs: [],
  anime_sources: [],
  anime_audio_codecs: [],
  anime_audio_channels: [],
  anime_hdr_formats: [],
  anime_min_size: null,
  anime_max_size: null,
  // Common settings
  languages: [defaultLanguage],
  subtitle_languages: [],
  upgrade_allowed: true,
  // Indexers per media type
  movie_indexers: [],
  show_indexers: [],
  anime_indexers: [],
  music_indexers: [],
  // Search settings
  search_timeout: 30,
  max_retries: 3,
  max_results: 100,
  uploader_filter: '',
  release_group_filter: '',
  custom_regex: '',
  search_sort_preference: 'weighted',
  seeder_weight: 40,
  size_weight: 40,
  recency_weight: 20,
  // TV options
  season_pack_preference: 'prefer',
  // File output settings
  use_hardlinks: true,
  illegal_char_replacement: '_',
  colon_replacement: ' -',
  // Naming formats
  movie_naming_format: DEFAULT_NAMING.movie.file,
  movie_folder_format: DEFAULT_NAMING.movie.folder,
  show_naming_format: DEFAULT_NAMING.show.file,
  show_folder_format: DEFAULT_NAMING.show.folder,
  anime_naming_format: DEFAULT_NAMING.anime.file,
  anime_folder_format: DEFAULT_NAMING.anime.folder,
  // Anime options
  anime_subtitle_preference: 'softsub',
  anime_allow_hardsub: false,
  anime_prefer_dual_audio: false,
  anime_audio_language: 'ja',
  anime_subtitle_language: 'en',
  // Music settings
  music_artist_folder_format: DEFAULT_NAMING.music.artistFolder,
  music_album_folder_format: DEFAULT_NAMING.music.albumFolder,
  music_track_naming_format: DEFAULT_NAMING.music.track,
  music_multi_disc_format: DEFAULT_NAMING.music.multiDisc,
  music_preferred_quality: ['flac', 'mp3_320', 'mp3_256', 'aac'],
  music_embed_lyrics: true,
  music_embed_artwork: true,
  // Torrent validation settings
  validation_enabled: true,
  validation_mode: 'allowlist',
  forbidden_extensions: ['.exe', '.bat', '.cmd', '.sh', '.msi', '.dll', '.scr', '.com', '.ps1', '.vbs', '.jar'],
  validation_failure_action: 'pause_notify',
  movie_allowed_extensions: ['.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm', '.ts'],
  show_allowed_extensions: ['.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm', '.ts'],
  anime_allowed_extensions: ['.mkv', '.mp4', '.avi', '.m4v'],
  music_allowed_extensions: ['.flac', '.mp3', '.m4a', '.aac', '.ogg', '.opus', '.wav', '.wma'],
});
