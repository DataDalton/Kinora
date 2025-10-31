'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import ISO6391 from 'iso-639-1';
import PageHeader from '@/components/PageHeader';

interface ResolutionSize {
  minSize: number;
  maxSize: number;
}

interface QualityProfile {
  id: number;
  name: string;
  min_size: number;
  max_size: number;
  preferred_qualities: string[];
  allowed_qualities: string[];
  preferred_codecs: string[];
  preferred_sources: string[];
  preferred_audio: string[];
  preferred_resolutions: string[];
  allowed_resolutions: string[];
  preferred_hdr: string[];
  allowed_hdr: string[];
  preferred_audio_channels: string[];
  preferred_editions: string[];
  upgrade_allowed: boolean;
  languages?: string[];
  subtitle_languages?: string[];
}

// Quality hierarchies ordered from highest to lowest quality (best first)
const RESOLUTIONS = ['4320p', '2160p', '1080p', '720p', '576p', '480p', '360p', '240p'];
const SOURCES = ['REMUX', 'BLURAY', 'WEB-DL', 'WEBRIP', 'DVD', 'HDTV', 'SDTV', 'DVDSCR', 'SCREENER', 'TELESYNC', 'CAM'];
const CODECS = ['AV1', 'HEVC', 'x265', 'H265', 'x264', 'H264', 'XVID'];
const AUDIO_CODECS = ['FLAC', 'TrueHD', 'Dolby Atmos', 'DTS-HD MA', 'DTS', 'AC3', 'AAC', 'MP3'];
const AUDIO_CHANNELS = ['Atmos', '7.1', '5.1', '2.0'];
const HDR_FORMATS = ['Dolby Vision', 'HDR10+', 'HDR10', 'SDR'];
const EDITIONS = ['IMAX', 'Remastered', "Director's Cut", 'Unrated', 'Extended', 'Theatrical'];

const LANGUAGES = ISO6391.getAllCodes().map(code => ({
  code,
  name: ISO6391.getName(code),
  nativeName: ISO6391.getNativeName(code)
}));

const formatSize = (mb: number): string => {
  if (mb === 0) return '0 MB';
  if (mb >= 1024) {
    return `${(mb / 1024).toFixed(1)} GB`;
  }
  return `${mb} MB`;
};

const parseSizeInput = (value: string): number => {
  const match = value.match(/^(\d+(?:\.\d+)?)\s*(GB|MB)?$/i);
  if (!match) return 0;
  const num = parseFloat(match[1]);
  const unit = match[2]?.toUpperCase();
  if (unit === 'GB') return Math.round(num * 1024);
  return Math.round(num);
};

const QualityCheckboxList = ({
  items,
  selected,
  onChange,
  label,
  description
}: {
  items: string[];
  selected: string[];
  onChange: (items: string[]) => void;
  label: string;
  description?: string;
}) => {
  const toggleItem = (item: string) => {
    if (selected.includes(item)) {
      onChange(selected.filter(i => i !== item));
    } else {
      onChange([...selected, item]);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-lg font-semibold text-foreground mb-1">{label}</label>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {items.map((item, index) => {
          const isSelected = selected.includes(item);
          const qualityRank = index + 1;
          return (
            <button
              type="button"
              key={item}
              onClick={() => toggleItem(item)}
              className={`relative flex items-center gap-4 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                isSelected
                  ? 'bg-primary/10 border-primary shadow-md'
                  : 'bg-muted/30 border-border hover:border-muted-foreground/30 hover:bg-muted/50'
              }`}
            >
              {/* Selection Bubble */}
              <div className={`flex-shrink-0 w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all ${
                isSelected
                  ? 'bg-primary border-primary'
                  : 'border-muted-foreground/30'
              }`}>
                {isSelected && (
                  <svg className="w-4 h-4 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>

              {/* Content */}
              <div className="flex-1 text-left">
                <div className="font-semibold text-base">{item}</div>
                <div className="text-xs text-muted-foreground mt-0.5">Quality Rank #{qualityRank}</div>
              </div>

              {/* Rank Badge */}
              <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                isSelected
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground'
              }`}>
                {qualityRank}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default function QualityProfilesPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editingProfile, setEditingProfile] = useState<QualityProfile | null>(null);
  const [advancedMode, setAdvancedMode] = useState(false);
  const [activeSection, setActiveSection] = useState<string>('profile');

  const getDefaultLanguage = () => {
    if (typeof window === 'undefined') return 'en';
    const browserLang = navigator.language.split('-')[0];
    const isSupported = LANGUAGES.some(l => l.code === browserLang);
    return isSupported ? browserLang : 'en';
  };

  const [formData, setFormData] = useState({
    name: '',
    min_size: 0,
    max_size: 0,
    resolutions: [] as string[],
    sources: [] as string[],
    codecs: [] as string[],
    audio: [] as string[],
    audio_channels: [] as string[],
    hdr: [] as string[],
    editions: [] as string[],
    languages: [getDefaultLanguage()] as string[],
    subtitle_languages: [] as string[],
    upgrade_allowed: true,
    // Indexer settings by media type
    movie_indexers: [] as string[],
    show_indexers: [] as string[],
    anime_indexers: [] as string[],
    search_timeout: 30,
    max_retries: 3,
    max_results: 100,
    uploader_filter: '',
    release_group_filter: '',
    custom_regex: '',
    search_sort_preference: 'weighted' as 'weighted' | 'seeders' | 'size' | 'date',
    seeder_weight: 40,
    size_weight: 40,
    recency_weight: 20,
    season_pack_preference: 'prefer' as 'prefer' | 'only' | 'avoid',
    // Media server settings
    media_server: 'jellyfin' as 'jellyfin' | 'custom',
    use_hardlinks: true,
    // Naming settings
    movie_naming_format: '{Movie CleanTitle} ({Release Year}) [tmdbid-{TmdbId}] - {Edition Tags} {[Quality Full]}{[MediaInfo AudioCodec} {MediaInfo AudioChannels]}{[MediaInfo VideoDynamicRangeType]}{[MediaInfo VideoCodec]}{-Release Group}',
    movie_folder_format: '{Movie CleanTitle} ({Release Year}) [tmdbid-{TmdbId}]',
    show_naming_format: '{Show Title} - S{Season}E{Episode} - {Episode Title}',
    show_folder_format: '{Show Title} ({Release Year}) [tvdbid-{TvdbId}]',
    anime_naming_format: '{Movie CleanTitle} ({Release Year}) [tmdbid-{TmdbId}] - {Edition Tags} {[Quality Full]}{[MediaInfo AudioCodec} {MediaInfo AudioChannels]}{MediaInfo AudioLanguages}{[MediaInfo VideoDynamicRangeType]}[{MediaInfo VideoCodec }{MediaInfo VideoBitDepth}bit]{-Release Group}',
    anime_folder_format: '{Anime Title} ({Release Year}) [anilistid-{AnilistId}]',
    // Anime-specific settings
    anime_subtitle_preference: 'softsub' as 'softsub' | 'hardsub' | 'dual_audio',
    anime_allow_hardsub: false,
    anime_prefer_dual_audio: false,
    anime_audio_language: 'ja' as string, // Preferred audio language
    anime_subtitle_language: 'en' as string, // Preferred subtitle language
    illegal_char_replacement: '_',
    colon_replacement: ' -',
  });

  const [resolutionSizes, setResolutionSizes] = useState<Record<string, ResolutionSize>>({});
  const [languageSearch, setLanguageSearch] = useState('');
  const [subtitleLanguageSearch, setSubtitleLanguageSearch] = useState('');
  const [animeAudioLanguageSearch, setAnimeAudioLanguageSearch] = useState('');
  const [animeSubtitleLanguageSearch, setAnimeSubtitleLanguageSearch] = useState('');
  const [showNamingBuilder, setShowNamingBuilder] = useState(false);
  const [builderType, setBuilderType] = useState<'movie' | 'show' | 'anime' | 'movie_folder' | 'show_folder' | 'anime_folder'>('movie');
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);
  const [hasAttemptedSubmit, setHasAttemptedSubmit] = useState(false);

  const navigationSections = [
    { id: 'profile', label: 'Basic Info', group: 'Profile' },
    { id: 'indexers', label: 'Indexers', group: 'Search' },
    { id: 'filters', label: 'Filters', group: 'Search' },
    { id: 'sorting', label: 'Result Sorting', group: 'Search' },
    { id: 'tvOptions', label: 'TV Options', group: 'Search' },
    { id: 'animeOptions', label: 'Anime Options', group: 'Search' },
    { id: 'mediaServer', label: 'Configuration', group: 'Media Server' },
    { id: 'movieNaming', label: 'Movies', group: 'Naming' },
    { id: 'showNaming', label: 'TV Shows', group: 'Naming' },
    { id: 'animeNaming', label: 'Anime', group: 'Naming' },
    { id: 'resolutions', label: 'Resolutions', group: 'Quality' },
    { id: 'sources', label: 'Sources', group: 'Quality' },
    { id: 'codecs', label: 'Video Codecs', group: 'Quality' },
    { id: 'audio', label: 'Audio', group: 'Quality' },
    { id: 'hdr', label: 'HDR Formats', group: 'Quality' },
    { id: 'editions', label: 'Special Editions', group: 'Quality' },
  ];

  const INDEXERS_BY_TYPE = {
    movies: ['1337x', 'YTS'],
    shows: ['1337x'],
    anime: ['Nyaa'],
  };

  const NAMING_TOKENS = {
    movie: [
      { token: '{Movie Title}', desc: 'Full movie title' },
      { token: '{Movie CleanTitle}', desc: 'Movie title without special characters' },
      { token: '{Release Year}', desc: 'Movie release year' },
      { token: '{TmdbId}', desc: 'TMDB database ID' },
      { token: '{ImdbId}', desc: 'IMDB database ID' },
      { token: '{Edition Tags}', desc: 'Edition info (Extended, IMAX, etc)' },
      { token: '{Quality Full}', desc: 'Full quality string (Bluray-1080p)' },
      { token: '{Quality Title}', desc: 'Quality name (Bluray)' },
      { token: '{Resolution}', desc: 'Resolution (1080p, 2160p)' },
      { token: '{MediaInfo 3D}', desc: '3D indicator if applicable' },
      { token: '{Custom Formats}', desc: 'Custom format tags' },
      { token: '{MediaInfo AudioCodec}', desc: 'Audio codec (DTS, AC3)' },
      { token: '{MediaInfo AudioChannels}', desc: 'Audio channels (5.1, 7.1)' },
      { token: '{MediaInfo AudioLanguages}', desc: 'Audio language codes' },
      { token: '{MediaInfo VideoDynamicRangeType}', desc: 'HDR type (HDR10, DV)' },
      { token: '{MediaInfo VideoCodec}', desc: 'Video codec (x264, x265)' },
      { token: '{MediaInfo VideoBitDepth}', desc: 'Bit depth (8bit, 10bit)' },
      { token: '{MediaInfo VideoBitrate}', desc: 'Video bitrate' },
      { token: '{MediaInfo AudioBitrate}', desc: 'Audio bitrate' },
      { token: '{Release Group}', desc: 'Release group name' },
      { token: '{Source}', desc: 'Source type (Bluray, WEB-DL)' },
      { token: '{Codec}', desc: 'Combined codec info' },
    ],
    show: [
      { token: '{Show Title}', desc: 'TV show title' },
      { token: '{Show CleanTitle}', desc: 'Show title without special characters' },
      { token: '{Season}', desc: 'Season number (01, 02)' },
      { token: '{Season:0}', desc: 'Season without leading zero' },
      { token: '{Episode}', desc: 'Episode number (01, 02)' },
      { token: '{Episode:0}', desc: 'Episode without leading zero' },
      { token: '{Episode Title}', desc: 'Episode title' },
      { token: '{Episode CleanTitle}', desc: 'Episode title without special characters' },
      { token: '{Release Year}', desc: 'Show first air year' },
      { token: '{Air Date}', desc: 'Episode air date' },
      { token: '{TvdbId}', desc: 'TVDB database ID' },
      { token: '{ImdbId}', desc: 'IMDB database ID' },
      { token: '{Quality Full}', desc: 'Full quality string' },
      { token: '{Resolution}', desc: 'Resolution' },
      { token: '{MediaInfo AudioCodec}', desc: 'Audio codec' },
      { token: '{MediaInfo AudioChannels}', desc: 'Audio channels' },
      { token: '{MediaInfo VideoDynamicRangeType}', desc: 'HDR type' },
      { token: '{MediaInfo VideoCodec}', desc: 'Video codec' },
      { token: '{Release Group}', desc: 'Release group' },
    ],
    anime: [
      { token: '{Anime Title}', desc: 'Anime title' },
      { token: '{Anime CleanTitle}', desc: 'Anime title without special characters' },
      { token: '{Release Year}', desc: 'Anime release year' },
      { token: '{Absolute Episode}', desc: 'Absolute episode number' },
      { token: '{Episode}', desc: 'Episode number' },
      { token: '{Episode Title}', desc: 'Episode title' },
      { token: '{AnilistId}', desc: 'AniList database ID' },
      { token: '{TmdbId}', desc: 'TMDB database ID' },
      { token: '{Quality Full}', desc: 'Full quality string' },
      { token: '{Resolution}', desc: 'Resolution' },
      { token: '{MediaInfo AudioCodec}', desc: 'Audio codec' },
      { token: '{MediaInfo AudioChannels}', desc: 'Audio channels' },
      { token: '{MediaInfo AudioLanguages}', desc: 'Audio language codes' },
      { token: '{MediaInfo VideoDynamicRangeType}', desc: 'HDR type' },
      { token: '{MediaInfo VideoCodec}', desc: 'Video codec' },
      { token: '{MediaInfo VideoBitDepth}', desc: 'Bit depth' },
      { token: '{Release Group}', desc: 'Release group' },
    ],
  };

  const { data: profiles, isLoading } = useQuery({
    queryKey: ['media-profiles'],
    queryFn: async () => {
      const response = await api.get('/media-profiles');
      return response.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: typeof formData) => {
      const response = await api.post('/media-profiles', {
        name: data.name,
        min_size: data.min_size,
        max_size: data.max_size,
        preferred_resolutions: data.resolutions,
        allowed_resolutions: data.resolutions,
        preferred_sources: data.sources,
        preferred_codecs: data.codecs,
        preferred_audio: data.audio,
        preferred_audio_channels: data.audio_channels,
        preferred_hdr: data.hdr,
        allowed_hdr: data.hdr,
        preferred_editions: data.editions,
        languages: data.languages,
        upgrade_allowed: data.upgrade_allowed,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['media-profiles'] });
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<typeof formData> }) => {
      const response = await api.put(`/media-profiles/${id}`, {
        name: data.name,
        min_size: data.min_size,
        max_size: data.max_size,
        preferred_resolutions: data.resolutions,
        allowed_resolutions: data.resolutions,
        preferred_sources: data.sources,
        preferred_codecs: data.codecs,
        preferred_audio: data.audio,
        preferred_audio_channels: data.audio_channels,
        preferred_hdr: data.hdr,
        allowed_hdr: data.hdr,
        preferred_editions: data.editions,
        languages: data.languages,
        upgrade_allowed: data.upgrade_allowed,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['media-profiles'] });
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.delete(`/media-profiles/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['media-profiles'] });
    },
  });

  const resetForm = () => {
    setFormData({
      name: '',
      min_size: 0,
      max_size: 0,
      resolutions: [],
      sources: [],
      codecs: [],
      audio: [],
      audio_channels: [],
      hdr: [],
      editions: [],
      languages: [getDefaultLanguage()],
      subtitle_languages: [],
      upgrade_allowed: true,
      movie_indexers: [],
      show_indexers: [],
      anime_indexers: [],
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
      season_pack_preference: 'prefer',
      media_server: 'jellyfin',
      use_hardlinks: true,
      movie_naming_format: '{Movie CleanTitle} ({Release Year}) [tmdbid-{TmdbId}] - {Edition Tags} {[Quality Full]}{[MediaInfo AudioCodec} {MediaInfo AudioChannels]}{[MediaInfo VideoDynamicRangeType]}{[MediaInfo VideoCodec]}{-Release Group}',
      movie_folder_format: '{Movie CleanTitle} ({Release Year}) [tmdbid-{TmdbId}]',
      show_naming_format: '{Show Title} - S{Season}E{Episode} - {Episode Title}',
      show_folder_format: '{Show Title} ({Release Year}) [tvdbid-{TvdbId}]',
      anime_naming_format: '{Movie CleanTitle} ({Release Year}) [tmdbid-{TmdbId}] - {Edition Tags} {[Quality Full]}{[MediaInfo AudioCodec} {MediaInfo AudioChannels]}{MediaInfo AudioLanguages}{[MediaInfo VideoDynamicRangeType]}[{MediaInfo VideoCodec }{MediaInfo VideoBitDepth}bit]{-Release Group}',
      anime_folder_format: '{Anime Title} ({Release Year}) [anilistid-{AnilistId}]',
      anime_subtitle_preference: 'softsub',
      anime_allow_hardsub: false,
      anime_prefer_dual_audio: false,
      anime_audio_language: 'ja',
      anime_subtitle_language: 'en',
      illegal_char_replacement: '_',
      colon_replacement: ' -',
    });
    setEditingProfile(null);
    setShowForm(false);
    setActiveSection('profile');
    setValidationErrors([]);
    setValidationWarnings([]);
    setHasAttemptedSubmit(false);
  };

  const handleEdit = (profile: QualityProfile) => {
    setValidationErrors([]);
    setValidationWarnings([]);
    setHasAttemptedSubmit(false);
    setFormData({
      name: profile.name,
      min_size: profile.min_size,
      max_size: profile.max_size,
      resolutions: profile.preferred_resolutions || profile.allowed_resolutions || [],
      sources: profile.preferred_sources || [],
      codecs: profile.preferred_codecs || [],
      audio: profile.preferred_audio || [],
      audio_channels: profile.preferred_audio_channels || [],
      hdr: profile.preferred_hdr || profile.allowed_hdr || [],
      editions: profile.preferred_editions || [],
      languages: profile.languages || ['en'],
      subtitle_languages: profile.subtitle_languages || [],
      upgrade_allowed: profile.upgrade_allowed,
      movie_indexers: [],
      show_indexers: [],
      anime_indexers: [],
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
      season_pack_preference: 'prefer',
      media_server: 'jellyfin',
      use_hardlinks: true,
      movie_naming_format: '{Movie CleanTitle} ({Release Year}) [tmdbid-{TmdbId}] - {Edition Tags} {[Quality Full]}{[MediaInfo AudioCodec} {MediaInfo AudioChannels]}{[MediaInfo VideoDynamicRangeType]}{[MediaInfo VideoCodec]}{-Release Group}',
      movie_folder_format: '{Movie CleanTitle} ({Release Year}) [tmdbid-{TmdbId}]',
      show_naming_format: '{Show Title} - S{Season}E{Episode} - {Episode Title}',
      show_folder_format: '{Show Title} ({Release Year}) [tvdbid-{TvdbId}]',
      anime_naming_format: '{Movie CleanTitle} ({Release Year}) [tmdbid-{TmdbId}] - {Edition Tags} {[Quality Full]}{[MediaInfo AudioCodec} {MediaInfo AudioChannels]}{MediaInfo AudioLanguages}{[MediaInfo VideoDynamicRangeType]}[{MediaInfo VideoCodec }{MediaInfo VideoBitDepth}bit]{-Release Group}',
      anime_folder_format: '{Anime Title} ({Release Year}) [anilistid-{AnilistId}]',
      anime_subtitle_preference: 'softsub',
      anime_allow_hardsub: false,
      anime_prefer_dual_audio: false,
      anime_audio_language: 'ja',
      anime_subtitle_language: 'en',
      illegal_char_replacement: '_',
      colon_replacement: ' -',
    });
    setEditingProfile(profile);
    setShowForm(true);
  };

  const getSectionErrors = () => {
    const sectionErrors: Record<string, boolean> = {};

    if (!formData.name.trim()) {
      sectionErrors.profile = true;
    }

    const hasIndexers = formData.movie_indexers.length > 0 ||
                       formData.show_indexers.length > 0 ||
                       formData.anime_indexers.length > 0;
    if (!hasIndexers) {
      sectionErrors.indexers = true;
    }

    return sectionErrors;
  };

  const getSectionWarnings = () => {
    const sectionWarnings: Record<string, boolean> = {};

    const hasQualityFilters = formData.resolutions.length > 0 ||
                             formData.codecs.length > 0 ||
                             formData.sources.length > 0;
    if (!hasQualityFilters) {
      sectionWarnings.resolutions = true;
      sectionWarnings.codecs = true;
      sectionWarnings.sources = true;
    }

    if (formData.min_size === 0 && formData.max_size === 0) {
      sectionWarnings.profile = true;
    }

    const hasReleaseFilters = formData.uploader_filter.trim() ||
                             formData.release_group_filter.trim() ||
                             formData.custom_regex.trim();
    if (!hasReleaseFilters) {
      sectionWarnings.filters = true;
    }

    if (formData.languages.length === 0) {
      sectionWarnings.profile = true;
    }

    return sectionWarnings;
  };

  const validateForm = () => {
    const errors: string[] = [];
    const warnings: string[] = [];

    // Hard requirements
    if (!formData.name.trim()) {
      errors.push('Profile name is required');
    }

    // At least one indexer must be selected
    const hasIndexers = formData.movie_indexers.length > 0 ||
                       formData.show_indexers.length > 0 ||
                       formData.anime_indexers.length > 0;
    if (!hasIndexers) {
      errors.push('At least one indexer must be selected (Movies, TV Shows, or Anime)');
    }

    // Soft warnings
    const hasQualityFilters = formData.resolutions.length > 0 ||
                             formData.codecs.length > 0 ||
                             formData.sources.length > 0;
    if (!hasQualityFilters) {
      warnings.push('No quality filters set - this will accept any quality');
    }

    if (formData.min_size === 0 && formData.max_size === 0) {
      warnings.push('No size restrictions set - will accept any file size');
    }

    const hasReleaseFilters = formData.uploader_filter.trim() ||
                             formData.release_group_filter.trim() ||
                             formData.custom_regex.trim();
    if (!hasReleaseFilters) {
      warnings.push('No release filters set - will accept releases from all uploaders and groups');
    }

    if (formData.languages.length === 0) {
      warnings.push('No languages selected - will accept any language');
    }

    setValidationErrors(errors);
    setValidationWarnings(warnings);

    return errors.length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setHasAttemptedSubmit(true);

    if (!validateForm()) {
      return;
    }

    if (editingProfile) {
      updateMutation.mutate({ id: editingProfile.id, data: formData });
    } else {
      createMutation.mutate(formData);
    }
  };

  const handleDelete = (id: number) => {
    if (confirm('Are you sure you want to delete this quality profile?')) {
      deleteMutation.mutate(id);
    }
  };

  const groupedSections = navigationSections.reduce((acc, section) => {
    if (!acc[section.group]) {
      acc[section.group] = [];
    }
    acc[section.group].push(section);
    return acc;
  }, {} as Record<string, typeof navigationSections>);

  return (
    <div className="min-h-screen">
      <PageHeader
        title="Media Profiles"
        description="Configure quality, indexer, naming, and media server preferences"
        gradientFrom="violet-600/10"
        gradientVia="purple-600/10"
        gradientTo="fuchsia-600/10"
      />

      <div className="container mx-auto px-6 py-8">
        {!showForm && profiles && profiles.length > 0 && (
          <div className="flex justify-between items-center mb-6">
            <button
              onClick={() => setShowForm(true)}
              className="px-6 py-2.5 bg-primary text-primary-foreground rounded-lg hover:opacity-90 font-medium shadow-sm ml-auto cursor-pointer"
            >
              + Add Profile
            </button>
          </div>
        )}

        {showForm && (
          <div className="bg-card text-card-foreground rounded-xl shadow-lg mb-8 border border-border overflow-hidden">
            <div className="p-6 border-b border-border">
              <h2 className="text-2xl font-bold">
                {editingProfile ? 'Edit Media Profile' : 'Create New Media Profile'}
              </h2>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col h-[calc(100vh-12rem)]">
              <div className="flex flex-1 overflow-hidden">
                {/* Sidebar Navigation */}
                <div className="w-64 bg-muted/30 border-r border-border p-4 space-y-1 overflow-y-auto">
                  {Object.entries(groupedSections).map(([group, sections]) => {
                    const sectionErrors = getSectionErrors();
                    const sectionWarnings = getSectionWarnings();

                    return (
                      <div key={group} className="mb-4">
                        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-3 py-2">
                          {group}
                        </h3>
                        <div className="space-y-1">
                          {sections.map((section) => {
                            const hasError = hasAttemptedSubmit && sectionErrors[section.id];
                            const hasWarning = hasAttemptedSubmit && !hasError && sectionWarnings[section.id];

                            return (
                              <button
                                key={section.id}
                                type="button"
                                onClick={() => setActiveSection(section.id)}
                                className={`w-full text-left px-3 py-2 rounded-lg transition-colors cursor-pointer ${
                                  activeSection === section.id
                                    ? 'bg-primary text-primary-foreground font-medium'
                                    : 'text-foreground hover:bg-muted/50'
                                } ${
                                  hasError || hasWarning ? 'border-2' : ''
                                } ${
                                  hasError
                                    ? 'border-destructive'
                                    : hasWarning
                                    ? 'border-warning'
                                    : ''
                                }`}
                              >
                                {section.label}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Content Area */}
                <div className="flex-1 p-6 space-y-6 overflow-y-auto">
                  {/* Validation Errors */}
                  {validationErrors.length > 0 && (
                    <div className="rounded-lg bg-destructive/10 border border-destructive/50 p-4">
                      <div className="flex items-center gap-3">
                        <div className="text-destructive font-semibold">Errors:</div>
                        <ul className="flex-1 space-y-1">
                          {validationErrors.map((error, index) => (
                            <li key={index} className="text-sm text-destructive">{error}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}

                  {/* Validation Warnings */}
                  {validationWarnings.length > 0 && (
                    <div className="rounded-lg bg-yellow-500/10 border border-yellow-500/50 p-4">
                      <div className="flex items-center gap-3">
                        <div className="text-yellow-600 dark:text-yellow-500 font-semibold">Warnings:</div>
                        <ul className="flex-1 space-y-1">
                          {validationWarnings.map((warning, index) => (
                            <li key={index} className="text-sm text-yellow-600 dark:text-yellow-500">{warning}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}

              {/* Profile Settings */}
              {activeSection === 'profile' && (
                <div className="space-y-4">
                  {/* Profile Name */}
                  <div>
                    <label className="block text-sm font-semibold mb-2">Profile Name</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className={`w-full px-4 py-2.5 bg-background text-foreground border-2 rounded-lg focus:ring-2 focus:ring-primary ${
                        hasAttemptedSubmit && !formData.name.trim()
                          ? 'border-destructive'
                          : 'border-input'
                      }`}
                      placeholder="e.g., Ultra HD, High Quality"
                    />
                  </div>

                  {/* Languages */}
                  <div className={`space-y-3 p-4 rounded-lg border-2 ${
                    hasAttemptedSubmit && formData.languages.length === 0
                      ? 'border-yellow-500 bg-yellow-500/5'
                      : 'border-transparent'
                  }`}>
                <div>
                  <label className="block text-sm font-semibold mb-2">Languages</label>
                    <p className="text-xs text-muted-foreground mb-2">Search and add languages in order of priority. First = most preferred.</p>

                    <div className="relative mb-3">
                      <input
                        type="text"
                        value={languageSearch}
                        onChange={(e) => setLanguageSearch(e.target.value)}
                        onFocus={() => setLanguageSearch(languageSearch || ' ')}
                        onBlur={() => setTimeout(() => setLanguageSearch(''), 200)}
                        className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
                        placeholder="Search languages..."
                      />
                      {languageSearch && (
                        <div className="absolute z-10 w-full mt-1 bg-background border border-border rounded-lg shadow-lg max-h-48 overflow-y-auto">
                          {LANGUAGES.filter(lang =>
                            !formData.languages.includes(lang.code) &&
                            (lang.name.toLowerCase().includes(languageSearch.trim().toLowerCase()) ||
                             lang.code.toLowerCase().includes(languageSearch.trim().toLowerCase()) ||
                             (lang.nativeName && lang.nativeName.toLowerCase().includes(languageSearch.trim().toLowerCase())))
                          ).map(lang => (
                            <button
                              key={lang.code}
                              type="button"
                              onClick={() => {
                                setFormData({
                                  ...formData,
                                  languages: [...formData.languages, lang.code]
                                });
                                setLanguageSearch('');
                              }}
                              className="w-full px-4 py-2 text-left hover:bg-muted transition-colors cursor-pointer text-sm"
                            >
                              <span className="font-medium">{lang.name}</span>
                              {lang.nativeName && lang.nativeName !== lang.name && (
                                <span className="text-xs text-muted-foreground ml-2">({lang.nativeName})</span>
                              )}
                              <span className="text-xs text-muted-foreground ml-2">{lang.code}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                  {formData.languages.length > 0 && (
                    <div className="flex flex-wrap gap-2 p-3 bg-muted rounded-lg border border-border">
                      {formData.languages.map((langCode, index) => {
                        const lang = LANGUAGES.find(l => l.code === langCode);
                        return (
                          <div
                            key={langCode}
                            className="flex items-center gap-2 px-3 py-1.5 bg-primary/20 border-2 border-primary rounded-lg text-sm font-medium"
                          >
                            <span className="text-xs text-muted-foreground">#{index + 1}</span>
                            <span>{lang?.name || langCode}</span>
                            <button
                              type="button"
                              onClick={() => {
                                setFormData({
                                  ...formData,
                                  languages: formData.languages.filter(l => l !== langCode)
                                });
                              }}
                              className="ml-1 text-muted-foreground hover:text-foreground cursor-pointer"
                            >
                              ×
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              {/* Subtitle Languages */}
              <div className="space-y-3 p-4 rounded-lg border-2 border-transparent">
                <div>
                  <label className="block text-sm font-semibold mb-2">Subtitle Languages</label>
                  <p className="text-xs text-muted-foreground mb-2">Optional: Add subtitle languages to download. Leave empty to skip subtitle downloads. Uses Podnapisi for movies/shows.</p>

                  <div className="relative mb-3">
                    <input
                      type="text"
                      value={subtitleLanguageSearch}
                      onChange={(e) => setSubtitleLanguageSearch(e.target.value)}
                      onFocus={() => setSubtitleLanguageSearch(subtitleLanguageSearch || ' ')}
                      onBlur={() => setTimeout(() => setSubtitleLanguageSearch(''), 200)}
                      className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
                      placeholder="Search subtitle languages..."
                    />
                    {subtitleLanguageSearch && (
                      <div className="absolute z-10 w-full mt-1 bg-background border border-border rounded-lg shadow-lg max-h-48 overflow-y-auto">
                        {LANGUAGES.filter(lang =>
                          !formData.subtitle_languages.includes(lang.code) &&
                          (lang.name.toLowerCase().includes(subtitleLanguageSearch.trim().toLowerCase()) ||
                           lang.code.toLowerCase().includes(subtitleLanguageSearch.trim().toLowerCase()) ||
                           (lang.nativeName && lang.nativeName.toLowerCase().includes(subtitleLanguageSearch.trim().toLowerCase())))
                        ).map(lang => (
                          <button
                            key={lang.code}
                            type="button"
                            onClick={() => {
                              setFormData({
                                ...formData,
                                subtitle_languages: [...formData.subtitle_languages, lang.code]
                              });
                              setSubtitleLanguageSearch('');
                            }}
                            className="w-full px-4 py-2 text-left hover:bg-muted transition-colors cursor-pointer text-sm"
                          >
                            <span className="font-medium">{lang.name}</span>
                            {lang.nativeName && lang.nativeName !== lang.name && (
                              <span className="text-xs text-muted-foreground ml-2">({lang.nativeName})</span>
                            )}
                            <span className="text-xs text-muted-foreground ml-2">{lang.code}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {formData.subtitle_languages.length > 0 && (
                    <div className="flex flex-wrap gap-2 p-3 bg-muted rounded-lg border border-border">
                      {formData.subtitle_languages.map((langCode, index) => {
                        const lang = LANGUAGES.find(l => l.code === langCode);
                        return (
                          <div
                            key={langCode}
                            className="flex items-center gap-2 px-3 py-1.5 bg-primary/20 border-2 border-primary rounded-lg text-sm font-medium"
                          >
                            <span className="text-xs text-muted-foreground">#{index + 1}</span>
                            <span>{lang?.name || langCode}</span>
                            <button
                              type="button"
                              onClick={() => {
                                setFormData({
                                  ...formData,
                                  subtitle_languages: formData.subtitle_languages.filter(l => l !== langCode)
                                });
                              }}
                              className="ml-1 text-muted-foreground hover:text-foreground cursor-pointer"
                            >
                              ×
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              {/* Upgrade Behavior & Mode */}
              <div className="p-4 bg-muted/50 rounded-lg border border-border">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-semibold mb-2">Upgrade Behavior</label>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setFormData({ ...formData, upgrade_allowed: true })}
                        className={`flex-1 px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                          formData.upgrade_allowed
                            ? 'bg-primary text-primary-foreground shadow-md'
                            : 'bg-muted text-muted-foreground hover:bg-muted/80'
                        }`}
                      >
                        Auto Upgrade
                      </button>
                      <button
                        type="button"
                        onClick={() => setFormData({ ...formData, upgrade_allowed: false })}
                        className={`flex-1 px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                          !formData.upgrade_allowed
                            ? 'bg-primary text-primary-foreground shadow-md'
                            : 'bg-muted text-muted-foreground hover:bg-muted/80'
                        }`}
                      >
                        One-Time Grab
                      </button>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {formData.upgrade_allowed ? 'Automatically upgrade to higher quality over time' : 'Grab highest quality once and stop'}
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-semibold mb-2">Mode</label>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setAdvancedMode(false)}
                        className={`flex-1 px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                          !advancedMode
                            ? 'bg-primary text-primary-foreground shadow-md'
                            : 'bg-muted text-muted-foreground hover:bg-muted/80'
                        }`}
                      >
                        Simple
                      </button>
                      <button
                        type="button"
                        onClick={() => setAdvancedMode(true)}
                        className={`flex-1 px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                          advancedMode
                            ? 'bg-primary text-primary-foreground shadow-md'
                            : 'bg-muted text-muted-foreground hover:bg-muted/80'
                        }`}
                      >
                        Advanced
                      </button>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {advancedMode ? 'Per-resolution size limits and detailed controls' : 'Basic quality selection'}
                    </p>
                  </div>
                </div>

              </div>

                  {/* File Size Limits (Simple Mode) */}
                  {!advancedMode && (
                    <div className={`p-4 rounded-lg border-2 ${
                      hasAttemptedSubmit && formData.min_size === 0 && formData.max_size === 0
                        ? 'border-warning bg-warning/5'
                        : 'border-transparent'
                    }`}>
                      <h4 className="font-semibold text-sm mb-3">File Size Limits</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-semibold mb-2">Min Size (MB)</label>
                          <input
                            type="number"
                            value={formData.min_size}
                            onChange={(e) => setFormData({ ...formData, min_size: parseInt(e.target.value) || 0 })}
                            className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
                            min="0"
                            placeholder="0 = No minimum"
                          />
                        </div>

                        <div>
                          <label className="block text-sm font-semibold mb-2">Max Size (MB)</label>
                          <input
                            type="number"
                            value={formData.max_size}
                            onChange={(e) => setFormData({ ...formData, max_size: parseInt(e.target.value) || 0 })}
                            className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
                            min="0"
                            placeholder="0 = No maximum"
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Indexers */}
              {activeSection === 'indexers' && (
                  <div className="space-y-6">
                    <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
                      <h4 className="font-semibold text-sm mb-2">Indexer Configuration</h4>
                      <p className="text-xs text-muted-foreground">
                        Configure indexer priority separately for movies, TV shows, and anime. Higher priority = searched first.
                      </p>
                    </div>

                    <div className={`space-y-6 p-4 rounded-lg border-2 ${
                      hasAttemptedSubmit &&
                      formData.movie_indexers.length === 0 &&
                      formData.show_indexers.length === 0 &&
                      formData.anime_indexers.length === 0
                        ? 'border-destructive bg-destructive/5'
                        : 'border-transparent'
                    }`}>
                      {/* Movie Indexers */}
                      <div>
                        <label className="block text-sm font-semibold mb-2">Movie Indexers</label>
                        <p className="text-xs text-muted-foreground mb-2">Indexers for movie searches</p>
                      <div className="flex flex-wrap gap-2 p-3 bg-muted/50 rounded-lg border border-border">
                        {INDEXERS_BY_TYPE.movies.map((indexer) => {
                          const index = formData.movie_indexers.indexOf(indexer);
                          const isSelected = index !== -1;
                          return (
                            <button
                              key={indexer}
                              type="button"
                              onClick={() => {
                                if (isSelected) {
                                  setFormData({
                                    ...formData,
                                    movie_indexers: formData.movie_indexers.filter(i => i !== indexer)
                                  });
                                } else {
                                  setFormData({
                                    ...formData,
                                    movie_indexers: [...formData.movie_indexers, indexer]
                                  });
                                }
                              }}
                              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all cursor-pointer ${
                                isSelected
                                  ? 'bg-primary/20 border-2 border-primary'
                                  : 'bg-background border border-border hover:border-primary/50'
                              }`}
                            >
                              {isSelected && <span className="text-xs text-muted-foreground">#{index + 1}</span>}
                              <span>{indexer}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* TV Show Indexers */}
                    <div>
                      <label className="block text-sm font-semibold mb-2">TV Show Indexers</label>
                      <p className="text-xs text-muted-foreground mb-2">Indexers for TV show searches</p>
                      <div className="flex flex-wrap gap-2 p-3 bg-muted/50 rounded-lg border border-border">
                        {INDEXERS_BY_TYPE.shows.map((indexer) => {
                          const index = formData.show_indexers.indexOf(indexer);
                          const isSelected = index !== -1;
                          return (
                            <button
                              key={indexer}
                              type="button"
                              onClick={() => {
                                if (isSelected) {
                                  setFormData({
                                    ...formData,
                                    show_indexers: formData.show_indexers.filter(i => i !== indexer)
                                  });
                                } else {
                                  setFormData({
                                    ...formData,
                                    show_indexers: [...formData.show_indexers, indexer]
                                  });
                                }
                              }}
                              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all cursor-pointer ${
                                isSelected
                                  ? 'bg-primary/20 border-2 border-primary'
                                  : 'bg-background border border-border hover:border-primary/50'
                              }`}
                            >
                              {isSelected && <span className="text-xs text-muted-foreground">#{index + 1}</span>}
                              <span>{indexer}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* Anime Indexers */}
                    <div>
                      <label className="block text-sm font-semibold mb-2">Anime Indexers</label>
                      <p className="text-xs text-muted-foreground mb-2">Indexers for anime searches</p>
                      <div className="flex flex-wrap gap-2 p-3 bg-muted/50 rounded-lg border border-border">
                        {INDEXERS_BY_TYPE.anime.map((indexer) => {
                          const index = formData.anime_indexers.indexOf(indexer);
                          const isSelected = index !== -1;
                          return (
                            <button
                              key={indexer}
                              type="button"
                              onClick={() => {
                                if (isSelected) {
                                  setFormData({
                                    ...formData,
                                    anime_indexers: formData.anime_indexers.filter(i => i !== indexer)
                                  });
                                } else {
                                  setFormData({
                                    ...formData,
                                    anime_indexers: [...formData.anime_indexers, indexer]
                                  });
                                }
                              }}
                              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all cursor-pointer ${
                                isSelected
                                  ? 'bg-primary/20 border-2 border-primary'
                                  : 'bg-background border border-border hover:border-primary/50'
                              }`}
                            >
                              {isSelected && <span className="text-xs text-muted-foreground">#{index + 1}</span>}
                              <span>{indexer}</span>
                              {indexer === 'Nyaa' && <span className="ml-1 px-1.5 py-0.5 text-xs bg-purple-500/20 text-purple-400 rounded">Anime Only</span>}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <label className="block text-sm font-semibold mb-2">Search Timeout (seconds)</label>
                        <input
                          type="number"
                          value={formData.search_timeout}
                          onChange={(e) => setFormData({ ...formData, search_timeout: parseInt(e.target.value) || 30 })}
                          className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
                          min="5"
                          max="300"
                        />
                        <p className="text-xs text-muted-foreground mt-1">How long to wait for indexer response</p>
                      </div>

                      <div>
                        <label className="block text-sm font-semibold mb-2">Max Retries</label>
                        <input
                          type="number"
                          value={formData.max_retries}
                          onChange={(e) => setFormData({ ...formData, max_retries: parseInt(e.target.value) || 3 })}
                          className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
                          min="0"
                          max="10"
                        />
                        <p className="text-xs text-muted-foreground mt-1">Retry attempts on failure</p>
                      </div>

                      <div>
                        <label className="block text-sm font-semibold mb-2">Max Results</label>
                        <input
                          type="number"
                          value={formData.max_results}
                          onChange={(e) => setFormData({ ...formData, max_results: parseInt(e.target.value) || 100 })}
                          className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
                          min="10"
                          max="1000"
                        />
                        <p className="text-xs text-muted-foreground mt-1">Maximum search results per indexer</p>
                      </div>
                    </div>
                  </div>
              )}

              {/* Filters */}
              {activeSection === 'filters' && (
                  <div className={`space-y-6 p-4 rounded-lg border-2 ${
                    hasAttemptedSubmit &&
                    !formData.uploader_filter.trim() &&
                    !formData.release_group_filter.trim() &&
                    !formData.custom_regex.trim()
                      ? 'border-warning bg-warning/5'
                      : 'border-transparent'
                  }`}>
                    <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
                      <h4 className="font-semibold text-sm mb-2">Release Filters</h4>
                      <p className="text-xs text-muted-foreground">
                        Filter search results by uploader, release group, or custom regex patterns. These filters apply before quality scoring.
                      </p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-semibold mb-2">Uploader Filter</label>
                        <input
                          type="text"
                          value={formData.uploader_filter}
                          onChange={(e) => setFormData({ ...formData, uploader_filter: e.target.value })}
                          className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
                          placeholder="e.g., YIFY, RARBG (comma separated)"
                        />
                        <p className="text-xs text-muted-foreground mt-1">Only include releases from these uploaders</p>
                      </div>

                      <div>
                        <label className="block text-sm font-semibold mb-2">Release Group Filter</label>
                        <input
                          type="text"
                          value={formData.release_group_filter}
                          onChange={(e) => setFormData({ ...formData, release_group_filter: e.target.value })}
                          className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
                          placeholder="e.g., SPARKS, EVO (comma separated)"
                        />
                        <p className="text-xs text-muted-foreground mt-1">Only include releases from these groups</p>
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-semibold mb-2">Custom Regex Filter</label>
                      <input
                        type="text"
                        value={formData.custom_regex}
                        onChange={(e) => setFormData({ ...formData, custom_regex: e.target.value })}
                        className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-sm"
                        placeholder="e.g., ^(?!.*CAM).*$ (exclude CAM releases)"
                      />
                      <p className="text-xs text-muted-foreground mt-1">Advanced filtering with regular expressions</p>
                    </div>
                  </div>
              )}

              {/* Sorting */}
              {activeSection === 'sorting' && (
                  <div className="space-y-6">
                    <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
                      <h4 className="font-semibold text-sm mb-2">Search Result Sorting</h4>
                      <p className="text-xs text-muted-foreground">
                        Choose how to sort and score search results. Weighted scoring combines multiple factors for the best overall result.
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-semibold mb-2">Sorting Method</label>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, search_sort_preference: 'weighted' })}
                          className={`px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                            formData.search_sort_preference === 'weighted'
                              ? 'bg-primary text-primary-foreground shadow-md'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          }`}
                        >
                          Best Overall
                        </button>
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, search_sort_preference: 'seeders' })}
                          className={`px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                            formData.search_sort_preference === 'seeders'
                              ? 'bg-primary text-primary-foreground shadow-md'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          }`}
                        >
                          Highest Seeders
                        </button>
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, search_sort_preference: 'size' })}
                          className={`px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                            formData.search_sort_preference === 'size'
                              ? 'bg-primary text-primary-foreground shadow-md'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          }`}
                        >
                          File Size
                        </button>
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, search_sort_preference: 'date' })}
                          className={`px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                            formData.search_sort_preference === 'date'
                              ? 'bg-primary text-primary-foreground shadow-md'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          }`}
                        >
                          Most Recent
                        </button>
                      </div>
                      <p className="text-xs text-muted-foreground mt-2">
                        {formData.search_sort_preference === 'weighted' && 'Weighted score combining seeders, size, and recency for best overall result'}
                        {formData.search_sort_preference === 'seeders' && 'Prioritize torrents with the most seeders for faster downloads'}
                        {formData.search_sort_preference === 'size' && 'Sort by file size (preferring sizes within your min/max range)'}
                        {formData.search_sort_preference === 'date' && 'Prioritize the most recently uploaded torrents'}
                      </p>

                      {formData.search_sort_preference === 'weighted' && (
                        <div className="mt-4 p-4 bg-muted/50 rounded-lg border border-border space-y-4">
                          <h5 className="font-semibold text-sm">Customize Weights</h5>
                          <p className="text-xs text-muted-foreground">Adjust how much each factor influences the overall score (must total 100%)</p>

                          <div className="space-y-3">
                            <div>
                              <div className="flex justify-between items-center mb-2">
                                <label className="text-xs font-semibold">Seeders</label>
                                <span className="text-xs text-muted-foreground">{formData.seeder_weight}%</span>
                              </div>
                              <input
                                type="range"
                                min="0"
                                max="100"
                                value={formData.seeder_weight}
                                onChange={(e) => {
                                  const newValue = parseInt(e.target.value);
                                  const remaining = 100 - newValue;
                                  const sizeRatio = formData.size_weight / (formData.size_weight + formData.recency_weight) || 0.5;
                                  setFormData({
                                    ...formData,
                                    seeder_weight: newValue,
                                    size_weight: Math.round(remaining * sizeRatio),
                                    recency_weight: Math.round(remaining * (1 - sizeRatio))
                                  });
                                }}
                                className="w-full h-2 bg-background rounded-lg appearance-none cursor-pointer accent-primary"
                              />
                            </div>

                            <div>
                              <div className="flex justify-between items-center mb-2">
                                <label className="text-xs font-semibold">File Size</label>
                                <span className="text-xs text-muted-foreground">{formData.size_weight}%</span>
                              </div>
                              <input
                                type="range"
                                min="0"
                                max="100"
                                value={formData.size_weight}
                                onChange={(e) => {
                                  const newValue = parseInt(e.target.value);
                                  const remaining = 100 - newValue;
                                  const seederRatio = formData.seeder_weight / (formData.seeder_weight + formData.recency_weight) || 0.5;
                                  setFormData({
                                    ...formData,
                                    size_weight: newValue,
                                    seeder_weight: Math.round(remaining * seederRatio),
                                    recency_weight: Math.round(remaining * (1 - seederRatio))
                                  });
                                }}
                                className="w-full h-2 bg-background rounded-lg appearance-none cursor-pointer accent-primary"
                              />
                            </div>

                            <div>
                              <div className="flex justify-between items-center mb-2">
                                <label className="text-xs font-semibold">Recency</label>
                                <span className="text-xs text-muted-foreground">{formData.recency_weight}%</span>
                              </div>
                              <input
                                type="range"
                                min="0"
                                max="100"
                                value={formData.recency_weight}
                                onChange={(e) => {
                                  const newValue = parseInt(e.target.value);
                                  const remaining = 100 - newValue;
                                  const seederRatio = formData.seeder_weight / (formData.seeder_weight + formData.size_weight) || 0.5;
                                  setFormData({
                                    ...formData,
                                    recency_weight: newValue,
                                    seeder_weight: Math.round(remaining * seederRatio),
                                    size_weight: Math.round(remaining * (1 - seederRatio))
                                  });
                                }}
                                className="w-full h-2 bg-background rounded-lg appearance-none cursor-pointer accent-primary"
                              />
                            </div>
                          </div>

                          <div className="flex justify-between items-center pt-2 border-t border-border">
                            <span className="text-xs font-semibold">Total</span>
                            <span className={`text-xs font-semibold ${
                              formData.seeder_weight + formData.size_weight + formData.recency_weight === 100
                                ? 'text-green-500'
                                : 'text-destructive'
                            }`}>
                              {formData.seeder_weight + formData.size_weight + formData.recency_weight}%
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
              )}

              {/* TV Options */}
              {activeSection === 'tvOptions' && (
                  <div className="space-y-6">
                    <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
                      <h4 className="font-semibold text-sm mb-2">TV Show Options</h4>
                      <p className="text-xs text-muted-foreground">
                        Configure TV show specific options like season pack preferences.
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-semibold mb-2">Season Pack Preference</label>
                      <p className="text-xs text-muted-foreground mb-2">Choose whether to prioritize season packs or individual episodes for TV shows</p>
                      <div className="grid grid-cols-3 gap-2">
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, season_pack_preference: 'prefer' })}
                          className={`px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                            formData.season_pack_preference === 'prefer'
                              ? 'bg-primary text-primary-foreground shadow-md'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          }`}
                        >
                          Prefer Season Packs
                        </button>
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, season_pack_preference: 'only' })}
                          className={`px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                            formData.season_pack_preference === 'only'
                              ? 'bg-primary text-primary-foreground shadow-md'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          }`}
                        >
                          Season Packs Only
                        </button>
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, season_pack_preference: 'avoid' })}
                          className={`px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                            formData.season_pack_preference === 'avoid'
                              ? 'bg-primary text-primary-foreground shadow-md'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          }`}
                        >
                          Individual Episodes
                        </button>
                      </div>
                      <p className="text-xs text-muted-foreground mt-2">
                        {formData.season_pack_preference === 'prefer' && 'Try season packs first, fall back to individual episodes if not found'}
                        {formData.season_pack_preference === 'only' && 'Only download complete season packs, reject individual episodes'}
                        {formData.season_pack_preference === 'avoid' && 'Only download individual episodes, reject season packs'}
                      </p>
                    </div>
                  </div>
              )}

              {/* Anime Options */}
              {activeSection === 'animeOptions' && (
                  <div className="space-y-6">
                    <div className="bg-purple-500/20 border border-purple-500/30 rounded-lg p-4 mb-4">
                      <h4 className="font-semibold text-sm mb-2">Anime-Specific Options</h4>
                      <p className="text-xs text-muted-foreground">
                        Configure anime torrent preferences including subtitle types, dub vs sub, and indexers.
                      </p>
                    </div>

                    {/* Audio Language Preference */}
                    <div>
                      <label className="block text-sm font-semibold mb-2">Preferred Audio Language</label>
                      <p className="text-xs text-muted-foreground mb-2">Search and select preferred audio language for anime</p>

                      <div className="relative">
                        <input
                          type="text"
                          value={animeAudioLanguageSearch || (formData.anime_audio_language ? LANGUAGES.find(l => l.code === formData.anime_audio_language)?.name : '')}
                          onChange={(e) => setAnimeAudioLanguageSearch(e.target.value)}
                          onFocus={() => setAnimeAudioLanguageSearch(animeAudioLanguageSearch || ' ')}
                          onBlur={() => setTimeout(() => setAnimeAudioLanguageSearch(''), 200)}
                          className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
                          placeholder="Search audio language..."
                        />
                        {animeAudioLanguageSearch && (
                          <div className="absolute z-10 w-full mt-1 bg-background border border-border rounded-lg shadow-lg max-h-48 overflow-y-auto">
                            {LANGUAGES.filter(lang =>
                              lang.name.toLowerCase().includes(animeAudioLanguageSearch.trim().toLowerCase()) ||
                              lang.code.toLowerCase().includes(animeAudioLanguageSearch.trim().toLowerCase()) ||
                              (lang.nativeName && lang.nativeName.toLowerCase().includes(animeAudioLanguageSearch.trim().toLowerCase()))
                            ).map(lang => (
                              <button
                                key={lang.code}
                                type="button"
                                onClick={() => {
                                  setFormData({ ...formData, anime_audio_language: lang.code });
                                  setAnimeAudioLanguageSearch('');
                                }}
                                className="w-full px-4 py-2 text-left hover:bg-muted transition-colors cursor-pointer text-sm"
                              >
                                <span className="font-medium">{lang.name}</span>
                                {lang.nativeName && lang.nativeName !== lang.name && (
                                  <span className="text-xs text-muted-foreground ml-2">({lang.nativeName})</span>
                                )}
                                <span className="text-xs text-muted-foreground ml-2">{lang.code}</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>

                      {formData.anime_audio_language && (
                        <div className="mt-2 flex items-center gap-2 px-3 py-1.5 bg-primary/20 border-2 border-primary rounded-lg text-sm font-medium w-fit">
                          <span>{LANGUAGES.find(l => l.code === formData.anime_audio_language)?.name || formData.anime_audio_language}</span>
                          <span className="text-xs text-muted-foreground">({formData.anime_audio_language})</span>
                          <button
                            type="button"
                            onClick={() => setFormData({ ...formData, anime_audio_language: 'ja' })}
                            className="ml-1 text-muted-foreground hover:text-foreground cursor-pointer"
                          >
                            ×
                          </button>
                        </div>
                      )}

                      <p className="text-xs text-muted-foreground mt-2">
                        Original audio language (Japanese for anime, Chinese for donghua, Korean for aeni, etc.)
                      </p>
                    </div>

                    {/* Subtitle Language Preference */}
                    <div>
                      <label className="block text-sm font-semibold mb-2">Preferred Subtitle Language</label>
                      <p className="text-xs text-muted-foreground mb-2">Search and select preferred subtitle language</p>

                      <div className="relative">
                        <input
                          type="text"
                          value={animeSubtitleLanguageSearch || (formData.anime_subtitle_language ? LANGUAGES.find(l => l.code === formData.anime_subtitle_language)?.name : '')}
                          onChange={(e) => setAnimeSubtitleLanguageSearch(e.target.value)}
                          onFocus={() => setAnimeSubtitleLanguageSearch(animeSubtitleLanguageSearch || ' ')}
                          onBlur={() => setTimeout(() => setAnimeSubtitleLanguageSearch(''), 200)}
                          className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
                          placeholder="Search subtitle language..."
                        />
                        {animeSubtitleLanguageSearch && (
                          <div className="absolute z-10 w-full mt-1 bg-background border border-border rounded-lg shadow-lg max-h-48 overflow-y-auto">
                            {LANGUAGES.filter(lang =>
                              lang.name.toLowerCase().includes(animeSubtitleLanguageSearch.trim().toLowerCase()) ||
                              lang.code.toLowerCase().includes(animeSubtitleLanguageSearch.trim().toLowerCase()) ||
                              (lang.nativeName && lang.nativeName.toLowerCase().includes(animeSubtitleLanguageSearch.trim().toLowerCase()))
                            ).map(lang => (
                              <button
                                key={lang.code}
                                type="button"
                                onClick={() => {
                                  setFormData({ ...formData, anime_subtitle_language: lang.code });
                                  setAnimeSubtitleLanguageSearch('');
                                }}
                                className="w-full px-4 py-2 text-left hover:bg-muted transition-colors cursor-pointer text-sm"
                              >
                                <span className="font-medium">{lang.name}</span>
                                {lang.nativeName && lang.nativeName !== lang.name && (
                                  <span className="text-xs text-muted-foreground ml-2">({lang.nativeName})</span>
                                )}
                                <span className="text-xs text-muted-foreground ml-2">{lang.code}</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>

                      {formData.anime_subtitle_language && (
                        <div className="mt-2 flex items-center gap-2 px-3 py-1.5 bg-primary/20 border-2 border-primary rounded-lg text-sm font-medium w-fit">
                          <span>{LANGUAGES.find(l => l.code === formData.anime_subtitle_language)?.name || formData.anime_subtitle_language}</span>
                          <span className="text-xs text-muted-foreground">({formData.anime_subtitle_language})</span>
                          <button
                            type="button"
                            onClick={() => setFormData({ ...formData, anime_subtitle_language: 'en' })}
                            className="ml-1 text-muted-foreground hover:text-foreground cursor-pointer"
                          >
                            ×
                          </button>
                        </div>
                      )}

                      <p className="text-xs text-muted-foreground mt-2">
                        Subtitle language (for softsubs and hardsubs)
                      </p>
                    </div>

                    {/* Subtitle Type Preference */}
                    <div>
                      <label className="block text-sm font-semibold mb-2">Subtitle Type Preference</label>
                      <p className="text-xs text-muted-foreground mb-2">Choose your preferred subtitle format for anime</p>
                      <div className="grid grid-cols-3 gap-2">
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, anime_subtitle_preference: 'softsub' })}
                          className={`px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                            formData.anime_subtitle_preference === 'softsub'
                              ? 'bg-primary text-primary-foreground shadow-md'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          }`}
                        >
                          Softsub
                        </button>
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, anime_subtitle_preference: 'hardsub' })}
                          className={`px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                            formData.anime_subtitle_preference === 'hardsub'
                              ? 'bg-primary text-primary-foreground shadow-md'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          }`}
                        >
                          Hardsub
                        </button>
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, anime_subtitle_preference: 'dual_audio' })}
                          className={`px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                            formData.anime_subtitle_preference === 'dual_audio'
                              ? 'bg-primary text-primary-foreground shadow-md'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          }`}
                        >
                          Dual Audio
                        </button>
                      </div>
                      <p className="text-xs text-muted-foreground mt-2">
                        {formData.anime_subtitle_preference === 'softsub' && 'Prefer embedded subtitle tracks (can be toggled on/off)'}
                        {formData.anime_subtitle_preference === 'hardsub' && 'Prefer burned-in subtitles (cannot be disabled)'}
                        {formData.anime_subtitle_preference === 'dual_audio' && 'Prefer releases with both Japanese and English audio tracks'}
                      </p>
                    </div>

                    {/* Allow Hardsubs Toggle */}
                    <div>
                      <label className="flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={formData.anime_allow_hardsub}
                          onChange={(e) => setFormData({ ...formData, anime_allow_hardsub: e.target.checked })}
                          className="w-4 h-4 rounded border-border bg-background text-primary focus:ring-2 focus:ring-ring cursor-pointer"
                        />
                        <span className="ml-2 text-sm font-semibold">Allow Hardsubs</span>
                      </label>
                      <p className="text-xs text-muted-foreground mt-1 ml-6">
                        Allow torrents with burned-in subtitles (hardsubs) even if softsubs are preferred
                      </p>
                    </div>

                    {/* Prefer Dual Audio Toggle */}
                    <div>
                      <label className="flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={formData.anime_prefer_dual_audio}
                          onChange={(e) => setFormData({ ...formData, anime_prefer_dual_audio: e.target.checked })}
                          className="w-4 h-4 rounded border-border bg-background text-primary focus:ring-2 focus:ring-ring cursor-pointer"
                        />
                        <span className="ml-2 text-sm font-semibold">Prefer Dual Audio</span>
                      </label>
                      <p className="text-xs text-muted-foreground mt-1 ml-6">
                        Prioritize releases with both Japanese and English audio tracks
                      </p>
                    </div>
                  </div>
              )}

              {/* Media Server Settings */}
              {activeSection === 'mediaServer' && (
                <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-semibold mb-2">Media Server</label>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, media_server: 'jellyfin' })}
                          className={`flex-1 px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                            formData.media_server === 'jellyfin'
                              ? 'bg-primary text-primary-foreground shadow-md'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          }`}
                        >
                          Jellyfin
                        </button>
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, media_server: 'custom' })}
                          className={`flex-1 px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                            formData.media_server === 'custom'
                              ? 'bg-primary text-primary-foreground shadow-md'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          }`}
                        >
                          Custom
                        </button>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">Jellyfin uses optimized naming with TMDB IDs and folder structure</p>
                    </div>

                    <div className="p-4 bg-muted/50 rounded-lg border border-border">
                      <label className="block text-sm font-semibold mb-2">File Management</label>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, use_hardlinks: true })}
                          className={`flex-1 px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                            formData.use_hardlinks
                              ? 'bg-primary text-primary-foreground shadow-md'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          }`}
                        >
                          Use Hardlinks
                        </button>
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, use_hardlinks: false })}
                          className={`flex-1 px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
                            !formData.use_hardlinks
                              ? 'bg-primary text-primary-foreground shadow-md'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          }`}
                        >
                          Copy Files
                        </button>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        Hardlinks save disk space by creating links instead of copying files
                      </p>
                    </div>

                    {/* Character Replacement */}
                    <div>
                      <h4 className="font-semibold text-sm mb-3">Character Replacement</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-semibold mb-2">Illegal Character Replacement</label>
                          <input
                            type="text"
                            value={formData.illegal_char_replacement}
                            onChange={(e) => setFormData({ ...formData, illegal_char_replacement: e.target.value })}
                            className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
                            placeholder="_"
                            maxLength={5}
                          />
                          <p className="text-xs text-muted-foreground mt-1">
                            Replace illegal filename characters (/, \, :, *, ?, ", &lt;, &gt;, |)
                          </p>
                        </div>

                        <div>
                          <label className="block text-sm font-semibold mb-2">Colon Replacement</label>
                          <input
                            type="text"
                            value={formData.colon_replacement}
                            onChange={(e) => setFormData({ ...formData, colon_replacement: e.target.value })}
                            className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
                            placeholder=" -"
                            maxLength={5}
                          />
                          <p className="text-xs text-muted-foreground mt-1">
                            Replace colons in filenames (common in movie titles)
                          </p>
                        </div>
                      </div>
                    </div>
                </div>
              )}

              {/* Movie Naming */}
              {activeSection === 'movieNaming' && (
                <div className="space-y-4">
                            <div>
                              <div className="flex justify-between items-center mb-2">
                                <label className="block text-sm font-semibold">Movie Folder Format</label>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setBuilderType('movie_folder');
                                    setShowNamingBuilder(true);
                                  }}
                                  className="px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
                                >
                                  Open Builder
                                </button>
                              </div>
                              <input
                                type="text"
                                value={formData.movie_folder_format}
                                onChange={(e) => setFormData({ ...formData, movie_folder_format: e.target.value })}
                                className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
                              />
                              <div className="mt-2 p-2 bg-muted rounded border border-border">
                                <p className="text-xs font-semibold text-muted-foreground mb-1">Example:</p>
                                <p className="text-xs font-mono">Movie Title (2024) [tmdbid-12345]</p>
                              </div>
                            </div>

                            <div>
                              <div className="flex justify-between items-center mb-2">
                                <label className="block text-sm font-semibold">Movie File Naming Format</label>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setBuilderType('movie');
                                    setShowNamingBuilder(true);
                                  }}
                                  className="px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
                                >
                                  Open Builder
                                </button>
                              </div>
                              <textarea
                                value={formData.movie_naming_format}
                                onChange={(e) => setFormData({ ...formData, movie_naming_format: e.target.value })}
                                className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
                                rows={2}
                              />
                              <div className="mt-2 p-2 bg-muted rounded border border-border">
                                <p className="text-xs font-semibold text-muted-foreground mb-1">Example:</p>
                                <p className="text-xs font-mono">Movie Title (2024) [tmdbid-12345] - [Bluray-1080p][DTS 5.1][x265]-GROUP</p>
                              </div>
                            </div>
                </div>
              )}

              {/* TV Show Naming */}
              {activeSection === 'showNaming' && (
                <div className="space-y-4">
                            <div>
                              <div className="flex justify-between items-center mb-2">
                                <label className="block text-sm font-semibold">Show Folder Format</label>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setBuilderType('show_folder');
                                    setShowNamingBuilder(true);
                                  }}
                                  className="px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
                                >
                                  Open Builder
                                </button>
                              </div>
                              <input
                                type="text"
                                value={formData.show_folder_format}
                                onChange={(e) => setFormData({ ...formData, show_folder_format: e.target.value })}
                                className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
                              />
                              <div className="mt-2 p-2 bg-muted rounded border border-border">
                                <p className="text-xs font-semibold text-muted-foreground mb-1">Example:</p>
                                <p className="text-xs font-mono">Show Title (2024) [tvdbid-67890]</p>
                              </div>
                            </div>

                            <div>
                              <div className="flex justify-between items-center mb-2">
                                <label className="block text-sm font-semibold">Show File Naming Format</label>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setBuilderType('show');
                                    setShowNamingBuilder(true);
                                  }}
                                  className="px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
                                >
                                  Open Builder
                                </button>
                              </div>
                              <input
                                type="text"
                                value={formData.show_naming_format}
                                onChange={(e) => setFormData({ ...formData, show_naming_format: e.target.value })}
                                className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
                              />
                              <div className="mt-2 p-2 bg-muted rounded border border-border">
                                <p className="text-xs font-semibold text-muted-foreground mb-1">Example:</p>
                                <p className="text-xs font-mono">Show Title - S01E01 - Episode Title</p>
                              </div>
                            </div>
                </div>
              )}

              {/* Anime Naming */}
              {activeSection === 'animeNaming' && (
                <div className="space-y-4">
                            <div>
                              <div className="flex justify-between items-center mb-2">
                                <label className="block text-sm font-semibold">Anime Folder Format</label>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setBuilderType('anime_folder');
                                    setShowNamingBuilder(true);
                                  }}
                                  className="px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
                                >
                                  Open Builder
                                </button>
                              </div>
                              <input
                                type="text"
                                value={formData.anime_folder_format}
                                onChange={(e) => setFormData({ ...formData, anime_folder_format: e.target.value })}
                                className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
                              />
                              <div className="mt-2 p-2 bg-muted rounded border border-border">
                                <p className="text-xs font-semibold text-muted-foreground mb-1">Example:</p>
                                <p className="text-xs font-mono">Anime Title (2024) [anilistid-98765]</p>
                              </div>
                            </div>

                            <div>
                              <div className="flex justify-between items-center mb-2">
                                <label className="block text-sm font-semibold">Anime File Naming Format</label>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setBuilderType('anime');
                                    setShowNamingBuilder(true);
                                  }}
                                  className="px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
                                >
                                  Open Builder
                                </button>
                              </div>
                              <textarea
                                value={formData.anime_naming_format}
                                onChange={(e) => setFormData({ ...formData, anime_naming_format: e.target.value })}
                                className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
                                rows={2}
                              />
                              <div className="mt-2 p-2 bg-muted rounded border border-border">
                                <p className="text-xs font-semibold text-muted-foreground mb-1">Example:</p>
                                <p className="text-xs font-mono">Anime Title (2024) [tmdbid-54321] - [Bluray-1080p][AAC 2.0][JA][10bit][x265]-GROUP</p>
                              </div>
                            </div>
                </div>
              )}

              {/* Resolutions */}
              {activeSection === 'resolutions' && (
                <div className={`space-y-6 p-4 rounded-lg border-2 ${
                  hasAttemptedSubmit && formData.resolutions.length === 0
                    ? 'border-yellow-500 bg-yellow-500/5'
                    : 'border-transparent'
                }`}>
                    <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
                      <h4 className="font-semibold text-sm mb-2">How Resolution Upgrades Work</h4>
                      <p className="text-xs text-muted-foreground mb-2">
                        Resolutions are ranked from highest (#1 = 4320p) to lowest (#8 = 240p). Lower rank numbers are better quality.
                      </p>
                      <p className="text-xs text-muted-foreground">
                        <strong>If "Allow Upgrades" is enabled:</strong> System will upgrade from lower to higher quality until reaching the highest selected resolution.<br/>
                        <strong>If "Allow Upgrades" is disabled:</strong> System will grab the highest quality available and stop.
                      </p>
                    </div>
                    <QualityCheckboxList
                      items={RESOLUTIONS}
                      selected={formData.resolutions}
                      onChange={(items) => setFormData({ ...formData, resolutions: items })}
                      label="Select Resolutions"
                      description="Select all resolutions you want. Higher numbers = better quality. System always prefers higher quality."
                    />

                    {advancedMode && formData.resolutions.length > 0 && (
                      <div className="space-y-4 mt-6">
                        <h4 className="font-semibold text-sm">Per-Resolution Size Limits</h4>
                        {formData.resolutions.map((resolution) => {
                          const sizes = resolutionSizes[resolution] || { minSize: 0, maxSize: 0 };
                          return (
                            <div key={resolution} className="bg-muted border border-border rounded-lg p-4 space-y-3">
                              <div className="font-medium text-sm">{resolution}</div>

                              <div className="space-y-2">
                                <label className="text-xs font-semibold">Min Size: {formatSize(sizes.minSize)}</label>
                                <input
                                  type="range"
                                  min="0"
                                  max="102400"
                                  step="100"
                                  value={sizes.minSize}
                                  onChange={(e) => {
                                    const newMin = parseInt(e.target.value);
                                    setResolutionSizes({
                                      ...resolutionSizes,
                                      [resolution]: {
                                        ...sizes,
                                        minSize: newMin,
                                        maxSize: sizes.maxSize > 0 && sizes.maxSize < newMin ? newMin : sizes.maxSize
                                      }
                                    });
                                  }}
                                  className="w-full h-2 bg-background rounded-lg appearance-none cursor-pointer accent-primary"
                                />
                                <div className="flex gap-2">
                                  <input
                                    type="text"
                                    value={formatSize(sizes.minSize)}
                                    onChange={(e) => {
                                      const newMin = parseSizeInput(e.target.value);
                                      setResolutionSizes({
                                        ...resolutionSizes,
                                        [resolution]: {
                                          ...sizes,
                                          minSize: newMin,
                                          maxSize: sizes.maxSize > 0 && sizes.maxSize < newMin ? newMin : sizes.maxSize
                                        }
                                      });
                                    }}
                                    className="flex-1 px-3 py-1.5 text-sm border-input bg-background text-foreground border rounded"
                                    placeholder="e.g., 500 MB or 2 GB"
                                  />
                                </div>
                              </div>

                              <div className="space-y-2">
                                <label className="text-xs font-semibold">Max Size: {formatSize(sizes.maxSize)}</label>
                                <input
                                  type="range"
                                  min={sizes.minSize}
                                  max="102400"
                                  step="100"
                                  value={sizes.maxSize || sizes.minSize}
                                  onChange={(e) => {
                                    const newMax = parseInt(e.target.value);
                                    setResolutionSizes({
                                      ...resolutionSizes,
                                      [resolution]: { ...sizes, maxSize: Math.max(newMax, sizes.minSize) }
                                    });
                                  }}
                                  className="w-full h-2 bg-background rounded-lg appearance-none cursor-pointer accent-primary"
                                />
                                <div className="flex gap-2">
                                  <input
                                    type="text"
                                    value={formatSize(sizes.maxSize)}
                                    onChange={(e) => {
                                      const newMax = parseSizeInput(e.target.value);
                                      setResolutionSizes({
                                        ...resolutionSizes,
                                        [resolution]: { ...sizes, maxSize: Math.max(newMax, sizes.minSize) }
                                      });
                                    }}
                                    className="flex-1 px-3 py-1.5 text-sm border-input bg-background text-foreground border rounded"
                                    placeholder="e.g., 5 GB or 5000 MB"
                                  />
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                </div>
              )}

              {/* Sources */}
              {activeSection === 'sources' && (
                <div className={`space-y-6 p-4 rounded-lg border-2 ${
                  hasAttemptedSubmit && formData.sources.length === 0
                    ? 'border-yellow-500 bg-yellow-500/5'
                    : 'border-transparent'
                }`}>
                    <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
                      <h4 className="font-semibold text-sm mb-2">How Source Upgrades Work</h4>
                      <p className="text-xs text-muted-foreground mb-2">
                        Sources are ranked from highest (#1 = REMUX) to lowest (#11 = CAM) quality.
                        System always prefers lower rank numbers (higher quality sources).
                      </p>
                      <p className="text-xs text-muted-foreground">
                        <strong>Examples:</strong> CAM (theater recording) → WEB-DL (streaming) → BLURAY (disc) → REMUX (uncompressed disc)
                      </p>
                    </div>
                    <QualityCheckboxList
                      items={SOURCES}
                      selected={formData.sources}
                      onChange={(items) => setFormData({ ...formData, sources: items })}
                      label="Select Sources"
                      description="Select all sources you want. System always prefers higher ranked sources."
                    />
                </div>
              )}

              {/* Video Codecs */}
              {activeSection === 'codecs' && (
                <div className={`space-y-6 p-4 rounded-lg border-2 ${
                  hasAttemptedSubmit && formData.codecs.length === 0
                    ? 'border-yellow-500 bg-yellow-500/5'
                    : 'border-transparent'
                }`}>
                    <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
                      <h4 className="font-semibold text-sm mb-2">How Codec Selection Works</h4>
                      <p className="text-xs text-muted-foreground">
                        Codecs are ranked by efficiency and quality. Lower rank numbers indicate better compression and quality.
                        AV1 (#1) is the most efficient, followed by HEVC/x265 (#2-3), then x264/H264 (#4-5).
                      </p>
                    </div>
                    <QualityCheckboxList
                      items={CODECS}
                      selected={formData.codecs}
                      onChange={(items) => setFormData({ ...formData, codecs: items })}
                      label="Select Video Codecs"
                      description="Select all codecs you want. Higher numbers = better compression and quality."
                    />
                </div>
              )}

              {/* Audio */}
              {activeSection === 'audio' && (
                <div className="space-y-6">
                    <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
                      <h4 className="font-semibold text-sm mb-2">How Audio Selection Works</h4>
                      <p className="text-xs text-muted-foreground">
                        Audio codecs and channels are ranked by quality. Lower rank numbers are better quality.
                        FLAC/TrueHD (#1-2) are lossless, DTS/Dolby (#3-5) are high quality lossy.
                      </p>
                    </div>
                    <QualityCheckboxList
                      items={AUDIO_CODECS}
                      selected={formData.audio}
                      onChange={(items) => setFormData({ ...formData, audio: items })}
                      label="Select Audio Codecs"
                      description="Select all audio codecs you want. Higher numbers = better quality."
                    />
                    <QualityCheckboxList
                      items={AUDIO_CHANNELS}
                      selected={formData.audio_channels}
                      onChange={(items) => setFormData({ ...formData, audio_channels: items })}
                      label="Select Audio Channels"
                      description="Select channel configurations you want. More channels = more immersive sound."
                    />
                </div>
              )}

              {/* HDR Formats */}
              {activeSection === 'hdr' && (
                <div className="space-y-6">
                    <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
                      <h4 className="font-semibold text-sm mb-2">HDR Format Selection</h4>
                      <p className="text-xs text-muted-foreground">
                        HDR (High Dynamic Range) formats control color depth and dynamic range.
                        Dolby Vision (#1) is the highest quality, followed by HDR10+ (#2), HDR10 (#3), and SDR (#4).
                      </p>
                    </div>
                    <QualityCheckboxList
                      items={HDR_FORMATS}
                      selected={formData.hdr}
                      onChange={(items) => setFormData({ ...formData, hdr: items })}
                      label="Select HDR Formats"
                      description="Select all HDR formats you want. Higher numbers = better quality."
                    />
                </div>
              )}

              {/* Special Editions */}
              {activeSection === 'editions' && (
                <div className="space-y-6">
                    <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
                      <h4 className="font-semibold text-sm mb-2">Special Editions Selection</h4>
                      <p className="text-xs text-muted-foreground">
                        Choose which special editions you prefer. Extended cuts, Director's Cuts, and IMAX versions often contain additional content.
                        PROPER and REPACK indicate fixed/improved releases.
                      </p>
                    </div>
                    <QualityCheckboxList
                      items={EDITIONS}
                      selected={formData.editions}
                      onChange={(items) => setFormData({ ...formData, editions: items })}
                      label="Select Editions"
                      description="Select which special editions you prefer (e.g., Extended, Director's Cut, IMAX)."
                    />
                </div>
              )}
                </div>
              </div>

              {/* Submit Buttons - Fixed Footer */}
              <div className="flex-shrink-0 bg-card border-t border-border p-6">
                <div className="flex gap-4">
                  <button
                    type="submit"
                    disabled={createMutation.isPending || updateMutation.isPending}
                    className="px-8 py-2.5 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 font-medium shadow-sm cursor-pointer"
                  >
                    {editingProfile ? 'Update Profile' : 'Create Profile'}
                  </button>
                  <button
                    type="button"
                    onClick={resetForm}
                    className="px-8 py-2.5 bg-secondary text-secondary-foreground rounded-lg hover:opacity-90 font-medium cursor-pointer"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </form>
          </div>
        )}

        {isLoading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            <p className="mt-4 text-muted-foreground">Loading profiles...</p>
          </div>
        ) : profiles && profiles.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24">
            <div className="text-center max-w-md">
              <div className="text-6xl mb-6">📝</div>
              <h2 className="text-2xl font-bold mb-3">No Media Profiles Yet</h2>
              <p className="text-muted-foreground mb-8">
                Create your first media profile to define quality preferences, indexer settings, naming formats, and more.
              </p>
              <button
                onClick={() => setShowForm(true)}
                className="px-8 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 font-medium shadow-md cursor-pointer text-lg"
              >
                + Create Your First Profile
              </button>
            </div>
          </div>
        ) : (
          <div className="grid gap-6">
            {profiles?.map((profile: QualityProfile) => (
              <div key={profile.id} className="bg-card text-card-foreground rounded-xl shadow-md hover:shadow-lg transition-shadow p-6 border border-border">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-2xl font-bold">{profile.name}</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Upgrades: <span className="font-semibold">{profile.upgrade_allowed ? 'Enabled' : 'Disabled'}</span>
                      {profile.allowed_resolutions && profile.allowed_resolutions.length > 0 && (
                        <> | Max Quality: <span className="font-semibold">{profile.allowed_resolutions[profile.allowed_resolutions.length - 1]}</span></>
                      )}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleEdit(profile)}
                      className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 font-medium text-sm cursor-pointer"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(profile.id)}
                      disabled={deleteMutation.isPending}
                      className="px-4 py-2 bg-destructive text-destructive-foreground rounded-lg hover:opacity-90 disabled:opacity-50 font-medium text-sm cursor-pointer"
                    >
                      Delete
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
                  <div className="bg-muted/50 rounded-lg p-3">
                    <div className="font-semibold text-foreground mb-1">File Size Range</div>
                    <div className="text-muted-foreground">
                      {profile.min_size || 0}MB - {profile.max_size || 'No limit'}
                    </div>
                  </div>

                  {profile.preferred_resolutions && profile.preferred_resolutions.length > 0 && (
                    <div className="bg-muted/50 rounded-lg p-3">
                      <div className="font-semibold text-foreground mb-1">Preferred Resolutions</div>
                      <div className="text-muted-foreground">{profile.preferred_resolutions.join(', ')}</div>
                    </div>
                  )}

                  {profile.preferred_sources && profile.preferred_sources.length > 0 && (
                    <div className="bg-muted/50 rounded-lg p-3">
                      <div className="font-semibold text-foreground mb-1">Preferred Sources</div>
                      <div className="text-muted-foreground">{profile.preferred_sources.join(', ')}</div>
                    </div>
                  )}

                  {profile.preferred_codecs && profile.preferred_codecs.length > 0 && (
                    <div className="bg-muted/50 rounded-lg p-3">
                      <div className="font-semibold text-foreground mb-1">Preferred Codecs</div>
                      <div className="text-muted-foreground">{profile.preferred_codecs.join(', ')}</div>
                    </div>
                  )}

                  {profile.preferred_audio && profile.preferred_audio.length > 0 && (
                    <div className="bg-muted/50 rounded-lg p-3">
                      <div className="font-semibold text-foreground mb-1">Preferred Audio</div>
                      <div className="text-muted-foreground">{profile.preferred_audio.join(', ')}</div>
                    </div>
                  )}

                  {profile.preferred_hdr && profile.preferred_hdr.length > 0 && (
                    <div className="bg-muted/50 rounded-lg p-3">
                      <div className="font-semibold text-foreground mb-1">HDR Formats</div>
                      <div className="text-muted-foreground">{profile.preferred_hdr.join(', ')}</div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Naming Builder Modal */}
      {showNamingBuilder && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-card rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto border border-border">
            <div className="sticky top-0 bg-card border-b border-border p-4 flex justify-between items-center">
              <h3 className="text-xl font-bold">Naming Format Builder</h3>
              <button
                onClick={() => setShowNamingBuilder(false)}
                className="text-muted-foreground hover:text-foreground cursor-pointer text-2xl"
              >
                ×
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Current Format Preview */}
              <div className="p-4 bg-muted/50 rounded-lg border border-border">
                <h4 className="font-semibold text-sm mb-2">Current Format</h4>
                <p className="font-mono text-xs break-all">
                  {builderType === 'movie' && formData.movie_naming_format}
                  {builderType === 'movie_folder' && formData.movie_folder_format}
                  {builderType === 'show' && formData.show_naming_format}
                  {builderType === 'show_folder' && formData.show_folder_format}
                  {builderType === 'anime' && formData.anime_naming_format}
                  {builderType === 'anime_folder' && formData.anime_folder_format}
                </p>
              </div>

              {/* Visual Preview */}
              <div className="p-4 bg-blue-500/10 rounded-lg border border-blue-500/20">
                <h4 className="font-semibold text-sm mb-2">Preview Example</h4>
                <p className="font-mono text-xs break-all">
                  {builderType === 'movie' && 'The Movie Title (2010) [tmdbid-65567] - {edition-Extended} [IMAX][Bluray-1080p][DV HDR10][DTS 5.1][x264]-RlsGrp'}
                  {builderType === 'movie_folder' && 'The Movie Title (2010) [tmdbid-1520211]'}
                  {builderType === 'show' && 'Show Title - S01E05 - Episode Title'}
                  {builderType === 'show_folder' && 'Show Title (2020) [tvdbid-12345]'}
                  {builderType === 'anime' && 'Anime Title (2020) [tmdbid-65567] - [Bluray-1080p][DTS 5.1][JA][10bit][AVC]-RlsGrp'}
                  {builderType === 'anime_folder' && 'Anime Title (2020) [anilistid-54321]'}
                </p>
              </div>

              {/* Available Tokens */}
              <div>
                <h4 className="font-semibold text-sm mb-3">Available Tokens (Click to Add)</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-96 overflow-y-auto">
                  {NAMING_TOKENS[builderType.replace('_folder', '') as 'movie' | 'show' | 'anime'].map((item) => (
                    <button
                      key={item.token}
                      type="button"
                      onClick={() => {
                        const currentFormat =
                          builderType === 'movie' ? formData.movie_naming_format :
                          builderType === 'movie_folder' ? formData.movie_folder_format :
                          builderType === 'show' ? formData.show_naming_format :
                          builderType === 'show_folder' ? formData.show_folder_format :
                          builderType === 'anime' ? formData.anime_naming_format :
                          formData.anime_folder_format;

                        const newFormat = currentFormat + item.token;

                        if (builderType === 'movie') setFormData({ ...formData, movie_naming_format: newFormat });
                        else if (builderType === 'movie_folder') setFormData({ ...formData, movie_folder_format: newFormat });
                        else if (builderType === 'show') setFormData({ ...formData, show_naming_format: newFormat });
                        else if (builderType === 'show_folder') setFormData({ ...formData, show_folder_format: newFormat });
                        else if (builderType === 'anime') setFormData({ ...formData, anime_naming_format: newFormat });
                        else setFormData({ ...formData, anime_folder_format: newFormat });
                      }}
                      className="text-left p-3 bg-muted/50 hover:bg-muted rounded-lg border border-border transition-colors cursor-pointer"
                    >
                      <div className="font-mono text-xs text-primary mb-1">{item.token}</div>
                      <div className="text-xs text-muted-foreground">{item.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Quick Presets */}
              <div>
                <h4 className="font-semibold text-sm mb-3">Jellyfin Presets</h4>
                <div className="space-y-2">
                  {builderType === 'movie' && (
                    <button
                      type="button"
                      onClick={() => setFormData({ ...formData, movie_naming_format: '{Movie CleanTitle} ({Release Year}) [tmdbid-{TmdbId}] - {Edition Tags} {[Quality Full]}{[MediaInfo AudioCodec} {MediaInfo AudioChannels]}{[MediaInfo VideoDynamicRangeType]}{[MediaInfo VideoCodec]}{-Release Group}' })}
                      className="w-full p-2 text-left bg-muted hover:bg-muted/80 rounded border border-border cursor-pointer text-xs"
                    >
                      <div className="font-semibold mb-1">Jellyfin Standard (Movies)</div>
                      <div className="font-mono text-xs opacity-70">With edition, quality, audio/video info, release group</div>
                    </button>
                  )}
                  {builderType === 'anime' && (
                    <button
                      type="button"
                      onClick={() => setFormData({ ...formData, anime_naming_format: '{Movie CleanTitle} ({Release Year}) [tmdbid-{TmdbId}] - {Edition Tags} {[Quality Full]}{[MediaInfo AudioCodec} {MediaInfo AudioChannels]}{MediaInfo AudioLanguages}{[MediaInfo VideoDynamicRangeType]}[{MediaInfo VideoCodec }{MediaInfo VideoBitDepth}bit]{-Release Group}' })}
                      className="w-full p-2 text-left bg-muted hover:bg-muted/80 rounded border border-border cursor-pointer text-xs"
                    >
                      <div className="font-semibold mb-1">Jellyfin Standard (Anime)</div>
                      <div className="font-mono text-xs opacity-70">With language codes and bit depth</div>
                    </button>
                  )}
                </div>
              </div>

              {/* Close Button */}
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowNamingBuilder(false)}
                  className="px-6 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 cursor-pointer"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
