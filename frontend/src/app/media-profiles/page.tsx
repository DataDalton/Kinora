'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import ISO6391 from 'iso-639-1';
import PageHeader from '@/components/PageHeader';
import ConfirmModal from '@/components/ConfirmModal';
import {
  MediaProfileFormData,
  NavigationGroup,
  createDefaultFormData,
  Navigation,
  ProfileGroup,
  MoviesGroup,
  TVShowsGroup,
  AnimeGroup,
  MusicGroup,
  SearchGroup,
  FileOutputGroup,
} from './components';

interface MediaProfile {
  id: number;
  name: string;
  min_size: number;
  max_size: number;
  // Legacy global quality
  resolutions?: string[];
  codecs?: string[];
  sources?: string[];
  audio_codecs?: string[];
  audio_channels?: string[];
  hdr_formats?: string[];
  editions?: string[];
  // Per-media-type quality: Movies
  movie_resolutions?: string[];
  movie_codecs?: string[];
  movie_sources?: string[];
  movie_audio_codecs?: string[];
  movie_audio_channels?: string[];
  movie_hdr_formats?: string[];
  movie_editions?: string[];
  movie_min_size?: number;
  movie_max_size?: number;
  // Per-media-type quality: TV Shows
  show_resolutions?: string[];
  show_codecs?: string[];
  show_sources?: string[];
  show_audio_codecs?: string[];
  show_audio_channels?: string[];
  show_hdr_formats?: string[];
  show_min_size?: number;
  show_max_size?: number;
  // Per-media-type quality: Anime
  anime_resolutions?: string[];
  anime_codecs?: string[];
  anime_sources?: string[];
  anime_audio_codecs?: string[];
  anime_audio_channels?: string[];
  anime_hdr_formats?: string[];
  anime_min_size?: number;
  anime_max_size?: number;
  // Common settings
  languages?: string[];
  subtitle_languages?: string[];
  upgrade_allowed: boolean;
  indexers?: string[];
  uploaders?: string[];
  release_groups?: string[];
  regex_filters?: string[];
  seeder_weight?: number;
  size_weight?: number;
  recency_weight?: number;
  search_sort_preference?: string;
  season_pack_preference?: string;
  search_timeout?: number;
  max_retries?: number;
  max_results?: number;
  // Naming formats
  movie_naming_format?: string;
  movie_folder_format?: string;
  show_naming_format?: string;
  show_folder_format?: string;
  anime_naming_format?: string;
  anime_folder_format?: string;
  // Anime options
  anime_subtitle_preference?: string;
  anime_allow_hardsub?: boolean;
  anime_prefer_dual_audio?: boolean;
  anime_audio_language?: string;
  anime_subtitle_language?: string;
  // Indexers per media type
  movie_indexers?: string[];
  show_indexers?: string[];
  anime_indexers?: string[];
  music_indexers?: string[];
  // Music settings
  music_artist_folder_format?: string;
  music_album_folder_format?: string;
  music_track_naming_format?: string;
  music_multi_disc_format?: string;
  music_preferred_quality?: string[];
  music_embed_lyrics?: boolean;
  music_embed_artwork?: boolean;
  // File output settings
  use_hardlinks?: boolean;
  illegal_char_replacement?: string;
  colon_replacement?: string;
  // Torrent validation settings
  validation_enabled?: boolean;
  allowed_extensions?: string[];
  forbidden_extensions?: string[];
  validation_failure_action?: string;
  movie_allowed_extensions?: string[];
  show_allowed_extensions?: string[];
  anime_allowed_extensions?: string[];
  music_allowed_extensions?: string[];
}

const LANGUAGES = ISO6391.getAllCodes().map(code => ({
  code,
  name: ISO6391.getName(code),
  nativeName: ISO6391.getNativeName(code)
}));

export default function MediaProfilesPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editingProfile, setEditingProfile] = useState<MediaProfile | null>(null);
  const [activeGroup, setActiveGroup] = useState<NavigationGroup>('profile');
  const [activeTab, setActiveTab] = useState<string>('general');
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({ isOpen: false, title: '', message: '', onConfirm: () => {} });

  const getDefaultLanguage = () => {
    if (typeof window === 'undefined') return 'en';
    const browserLang = navigator.language.split('-')[0];
    const isSupported = LANGUAGES.some(l => l.code === browserLang);
    return isSupported ? browserLang : 'en';
  };

  const [formData, setFormData] = useState<MediaProfileFormData>(() =>
    createDefaultFormData(getDefaultLanguage())
  );

  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);
  const [hasAttemptedSubmit, setHasAttemptedSubmit] = useState(false);

  const { data: profiles, isLoading } = useQuery({
    queryKey: ['media-profiles'],
    queryFn: async () => {
      const response = await api.get('/media-profiles');
      return response.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: MediaProfileFormData) => {
      const response = await api.post('/media-profiles', {
        name: data.name,
        min_size: data.min_size,
        max_size: data.max_size,
        // Legacy global quality (for backward compatibility)
        resolutions: data.resolutions,
        codecs: data.codecs,
        sources: data.sources,
        audio_codecs: data.audio,
        audio_channels: data.audio_channels,
        hdr_formats: data.hdr,
        editions: data.editions,
        // Per-media-type quality: Movies
        movie_resolutions: data.movie_resolutions,
        movie_codecs: data.movie_codecs,
        movie_sources: data.movie_sources,
        movie_audio_codecs: data.movie_audio_codecs,
        movie_audio_channels: data.movie_audio_channels,
        movie_hdr_formats: data.movie_hdr_formats,
        movie_editions: data.movie_editions,
        movie_min_size: data.movie_min_size,
        movie_max_size: data.movie_max_size,
        // Per-media-type quality: TV Shows
        show_resolutions: data.show_resolutions,
        show_codecs: data.show_codecs,
        show_sources: data.show_sources,
        show_audio_codecs: data.show_audio_codecs,
        show_audio_channels: data.show_audio_channels,
        show_hdr_formats: data.show_hdr_formats,
        show_min_size: data.show_min_size,
        show_max_size: data.show_max_size,
        // Per-media-type quality: Anime
        anime_resolutions: data.anime_resolutions,
        anime_codecs: data.anime_codecs,
        anime_sources: data.anime_sources,
        anime_audio_codecs: data.anime_audio_codecs,
        anime_audio_channels: data.anime_audio_channels,
        anime_hdr_formats: data.anime_hdr_formats,
        anime_min_size: data.anime_min_size,
        anime_max_size: data.anime_max_size,
        // Common settings
        languages: data.languages,
        subtitle_languages: data.subtitle_languages,
        upgrade_allowed: data.upgrade_allowed,
        uploaders: data.uploader_filter ? data.uploader_filter.split(',').map(s => s.trim()).filter(Boolean) : [],
        release_groups: data.release_group_filter ? data.release_group_filter.split(',').map(s => s.trim()).filter(Boolean) : [],
        regex_filters: data.custom_regex ? [data.custom_regex] : [],
        seeder_weight: data.seeder_weight,
        size_weight: data.size_weight,
        recency_weight: data.recency_weight,
        search_sort_preference: data.search_sort_preference,
        season_pack_preference: data.season_pack_preference,
        search_timeout: data.search_timeout,
        max_retries: data.max_retries,
        max_results: data.max_results,
        // Naming formats
        movie_naming_format: data.movie_naming_format,
        movie_folder_format: data.movie_folder_format,
        show_naming_format: data.show_naming_format,
        show_folder_format: data.show_folder_format,
        anime_naming_format: data.anime_naming_format,
        anime_folder_format: data.anime_folder_format,
        // Anime options
        anime_subtitle_preference: data.anime_subtitle_preference,
        anime_allow_hardsub: data.anime_allow_hardsub,
        anime_prefer_dual_audio: data.anime_prefer_dual_audio,
        anime_audio_language: data.anime_audio_language,
        anime_subtitle_language: data.anime_subtitle_language,
        // Indexers per media type
        movie_indexers: data.movie_indexers,
        show_indexers: data.show_indexers,
        anime_indexers: data.anime_indexers,
        music_indexers: data.music_indexers,
        // Music settings
        music_artist_folder_format: data.music_artist_folder_format,
        music_album_folder_format: data.music_album_folder_format,
        music_track_naming_format: data.music_track_naming_format,
        music_multi_disc_format: data.music_multi_disc_format,
        music_preferred_quality: data.music_preferred_quality,
        music_embed_lyrics: data.music_embed_lyrics,
        music_embed_artwork: data.music_embed_artwork,
        // File output settings
        use_hardlinks: data.use_hardlinks,
        illegal_char_replacement: data.illegal_char_replacement,
        colon_replacement: data.colon_replacement,
        // Torrent validation settings
        validation_enabled: data.validation_enabled,
        allowed_extensions: data.allowed_extensions,
        forbidden_extensions: data.forbidden_extensions,
        validation_failure_action: data.validation_failure_action,
        movie_allowed_extensions: data.movie_allowed_extensions,
        show_allowed_extensions: data.show_allowed_extensions,
        anime_allowed_extensions: data.anime_allowed_extensions,
        music_allowed_extensions: data.music_allowed_extensions,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['media-profiles'] });
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: MediaProfileFormData }) => {
      const response = await api.put(`/media-profiles/${id}`, {
        name: data.name,
        min_size: data.min_size,
        max_size: data.max_size,
        // Legacy global quality
        resolutions: data.resolutions,
        codecs: data.codecs,
        sources: data.sources,
        audio_codecs: data.audio,
        audio_channels: data.audio_channels,
        hdr_formats: data.hdr,
        editions: data.editions,
        // Per-media-type quality: Movies
        movie_resolutions: data.movie_resolutions,
        movie_codecs: data.movie_codecs,
        movie_sources: data.movie_sources,
        movie_audio_codecs: data.movie_audio_codecs,
        movie_audio_channels: data.movie_audio_channels,
        movie_hdr_formats: data.movie_hdr_formats,
        movie_editions: data.movie_editions,
        movie_min_size: data.movie_min_size,
        movie_max_size: data.movie_max_size,
        // Per-media-type quality: TV Shows
        show_resolutions: data.show_resolutions,
        show_codecs: data.show_codecs,
        show_sources: data.show_sources,
        show_audio_codecs: data.show_audio_codecs,
        show_audio_channels: data.show_audio_channels,
        show_hdr_formats: data.show_hdr_formats,
        show_min_size: data.show_min_size,
        show_max_size: data.show_max_size,
        // Per-media-type quality: Anime
        anime_resolutions: data.anime_resolutions,
        anime_codecs: data.anime_codecs,
        anime_sources: data.anime_sources,
        anime_audio_codecs: data.anime_audio_codecs,
        anime_audio_channels: data.anime_audio_channels,
        anime_hdr_formats: data.anime_hdr_formats,
        anime_min_size: data.anime_min_size,
        anime_max_size: data.anime_max_size,
        // Common settings
        languages: data.languages,
        subtitle_languages: data.subtitle_languages,
        upgrade_allowed: data.upgrade_allowed,
        uploaders: data.uploader_filter ? data.uploader_filter.split(',').map(s => s.trim()).filter(Boolean) : [],
        release_groups: data.release_group_filter ? data.release_group_filter.split(',').map(s => s.trim()).filter(Boolean) : [],
        regex_filters: data.custom_regex ? [data.custom_regex] : [],
        seeder_weight: data.seeder_weight,
        size_weight: data.size_weight,
        recency_weight: data.recency_weight,
        search_sort_preference: data.search_sort_preference,
        season_pack_preference: data.season_pack_preference,
        search_timeout: data.search_timeout,
        max_retries: data.max_retries,
        max_results: data.max_results,
        // Naming formats
        movie_naming_format: data.movie_naming_format,
        movie_folder_format: data.movie_folder_format,
        show_naming_format: data.show_naming_format,
        show_folder_format: data.show_folder_format,
        anime_naming_format: data.anime_naming_format,
        anime_folder_format: data.anime_folder_format,
        // Anime options
        anime_subtitle_preference: data.anime_subtitle_preference,
        anime_allow_hardsub: data.anime_allow_hardsub,
        anime_prefer_dual_audio: data.anime_prefer_dual_audio,
        anime_audio_language: data.anime_audio_language,
        anime_subtitle_language: data.anime_subtitle_language,
        // Indexers per media type
        movie_indexers: data.movie_indexers,
        show_indexers: data.show_indexers,
        anime_indexers: data.anime_indexers,
        music_indexers: data.music_indexers,
        // Music settings
        music_artist_folder_format: data.music_artist_folder_format,
        music_album_folder_format: data.music_album_folder_format,
        music_track_naming_format: data.music_track_naming_format,
        music_multi_disc_format: data.music_multi_disc_format,
        music_preferred_quality: data.music_preferred_quality,
        music_embed_lyrics: data.music_embed_lyrics,
        music_embed_artwork: data.music_embed_artwork,
        // File output settings
        use_hardlinks: data.use_hardlinks,
        illegal_char_replacement: data.illegal_char_replacement,
        colon_replacement: data.colon_replacement,
        // Torrent validation settings
        validation_enabled: data.validation_enabled,
        allowed_extensions: data.allowed_extensions,
        forbidden_extensions: data.forbidden_extensions,
        validation_failure_action: data.validation_failure_action,
        movie_allowed_extensions: data.movie_allowed_extensions,
        show_allowed_extensions: data.show_allowed_extensions,
        anime_allowed_extensions: data.anime_allowed_extensions,
        music_allowed_extensions: data.music_allowed_extensions,
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
    setFormData(createDefaultFormData(getDefaultLanguage()));
    setEditingProfile(null);
    setShowForm(false);
    setActiveGroup('profile');
    setActiveTab('general');
    setValidationErrors([]);
    setValidationWarnings([]);
    setHasAttemptedSubmit(false);
  };

  const handleEdit = (profile: MediaProfile) => {
    setValidationErrors([]);
    setValidationWarnings([]);
    setHasAttemptedSubmit(false);
    const defaults = createDefaultFormData(profile.languages?.[0] || 'en');
    setFormData({
      ...defaults,
      name: profile.name,
      min_size: profile.min_size || 0,
      max_size: profile.max_size || 0,
      // Legacy global quality
      resolutions: profile.resolutions || [],
      sources: profile.sources || [],
      codecs: profile.codecs || [],
      audio: profile.audio_codecs || [],
      audio_channels: profile.audio_channels || [],
      hdr: profile.hdr_formats || [],
      editions: profile.editions || [],
      // Per-media-type quality: Movies
      movie_resolutions: profile.movie_resolutions || [],
      movie_codecs: profile.movie_codecs || [],
      movie_sources: profile.movie_sources || [],
      movie_audio_codecs: profile.movie_audio_codecs || [],
      movie_audio_channels: profile.movie_audio_channels || [],
      movie_hdr_formats: profile.movie_hdr_formats || [],
      movie_editions: profile.movie_editions || [],
      movie_min_size: profile.movie_min_size ?? null,
      movie_max_size: profile.movie_max_size ?? null,
      // Per-media-type quality: TV Shows
      show_resolutions: profile.show_resolutions || [],
      show_codecs: profile.show_codecs || [],
      show_sources: profile.show_sources || [],
      show_audio_codecs: profile.show_audio_codecs || [],
      show_audio_channels: profile.show_audio_channels || [],
      show_hdr_formats: profile.show_hdr_formats || [],
      show_min_size: profile.show_min_size ?? null,
      show_max_size: profile.show_max_size ?? null,
      // Per-media-type quality: Anime
      anime_resolutions: profile.anime_resolutions || [],
      anime_codecs: profile.anime_codecs || [],
      anime_sources: profile.anime_sources || [],
      anime_audio_codecs: profile.anime_audio_codecs || [],
      anime_audio_channels: profile.anime_audio_channels || [],
      anime_hdr_formats: profile.anime_hdr_formats || [],
      anime_min_size: profile.anime_min_size ?? null,
      anime_max_size: profile.anime_max_size ?? null,
      // Common settings
      languages: profile.languages || ['en'],
      subtitle_languages: profile.subtitle_languages || [],
      upgrade_allowed: profile.upgrade_allowed,
      uploader_filter: profile.uploaders?.join(', ') || '',
      release_group_filter: profile.release_groups?.join(', ') || '',
      custom_regex: profile.regex_filters?.[0] || '',
      seeder_weight: profile.seeder_weight ?? 40,
      size_weight: profile.size_weight ?? 40,
      recency_weight: profile.recency_weight ?? 20,
      search_sort_preference: (profile.search_sort_preference as 'weighted' | 'seeders' | 'size' | 'date') || 'weighted',
      season_pack_preference: (profile.season_pack_preference as 'prefer' | 'only' | 'avoid') || 'prefer',
      search_timeout: profile.search_timeout ?? 30,
      max_retries: profile.max_retries ?? 3,
      max_results: profile.max_results ?? 100,
      // Naming formats
      movie_naming_format: profile.movie_naming_format || defaults.movie_naming_format,
      movie_folder_format: profile.movie_folder_format || defaults.movie_folder_format,
      show_naming_format: profile.show_naming_format || defaults.show_naming_format,
      show_folder_format: profile.show_folder_format || defaults.show_folder_format,
      anime_naming_format: profile.anime_naming_format || defaults.anime_naming_format,
      anime_folder_format: profile.anime_folder_format || defaults.anime_folder_format,
      // Anime options
      anime_subtitle_preference: (profile.anime_subtitle_preference as 'softsub' | 'hardsub' | 'dual_audio') || 'softsub',
      anime_allow_hardsub: profile.anime_allow_hardsub ?? false,
      anime_prefer_dual_audio: profile.anime_prefer_dual_audio ?? false,
      anime_audio_language: profile.anime_audio_language || 'ja',
      anime_subtitle_language: profile.anime_subtitle_language || 'en',
      // Indexers per media type
      movie_indexers: profile.movie_indexers || [],
      show_indexers: profile.show_indexers || [],
      anime_indexers: profile.anime_indexers || [],
      music_indexers: profile.music_indexers || [],
      // Music settings
      music_artist_folder_format: profile.music_artist_folder_format || defaults.music_artist_folder_format,
      music_album_folder_format: profile.music_album_folder_format || defaults.music_album_folder_format,
      music_track_naming_format: profile.music_track_naming_format || defaults.music_track_naming_format,
      music_multi_disc_format: profile.music_multi_disc_format || defaults.music_multi_disc_format,
      music_preferred_quality: profile.music_preferred_quality || defaults.music_preferred_quality,
      music_embed_lyrics: profile.music_embed_lyrics ?? true,
      music_embed_artwork: profile.music_embed_artwork ?? true,
      // File output settings
      use_hardlinks: profile.use_hardlinks ?? true,
      illegal_char_replacement: profile.illegal_char_replacement || '_',
      colon_replacement: profile.colon_replacement || ' -',
      // Torrent validation settings
      validation_enabled: profile.validation_enabled ?? true,
      allowed_extensions: profile.allowed_extensions || [],
      forbidden_extensions: profile.forbidden_extensions || defaults.forbidden_extensions,
      validation_failure_action: (profile.validation_failure_action as 'delete' | 'pause_notify' | 'quarantine') || 'pause_notify',
      movie_allowed_extensions: profile.movie_allowed_extensions || defaults.movie_allowed_extensions,
      show_allowed_extensions: profile.show_allowed_extensions || defaults.show_allowed_extensions,
      anime_allowed_extensions: profile.anime_allowed_extensions || defaults.anime_allowed_extensions,
      music_allowed_extensions: profile.music_allowed_extensions || defaults.music_allowed_extensions,
    });
    setEditingProfile(profile);
    setShowForm(true);
  };

  const validateForm = () => {
    const errors: string[] = [];
    const warnings: string[] = [];

    if (!formData.name.trim()) {
      errors.push('Profile name is required');
    }

    const hasIndexers = formData.movie_indexers.length > 0 ||
                       formData.show_indexers.length > 0 ||
                       formData.anime_indexers.length > 0 ||
                       formData.music_indexers.length > 0;
    if (!hasIndexers) {
      errors.push('At least one indexer must be selected');
    }

    // Check if any quality filters are set for any media type
    const hasMovieQuality = formData.movie_resolutions.length > 0 ||
                           formData.movie_codecs.length > 0 ||
                           formData.movie_sources.length > 0;
    const hasShowQuality = formData.show_resolutions.length > 0 ||
                          formData.show_codecs.length > 0 ||
                          formData.show_sources.length > 0;
    const hasAnimeQuality = formData.anime_resolutions.length > 0 ||
                           formData.anime_codecs.length > 0 ||
                           formData.anime_sources.length > 0;
    const hasMusicQuality = formData.music_preferred_quality.length > 0;

    if (!hasMovieQuality && !hasShowQuality && !hasAnimeQuality && !hasMusicQuality) {
      warnings.push('No quality filters set for any media type - will accept any quality');
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
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Media Profile',
      message: 'Are you sure you want to delete this media profile? This action cannot be undone.',
      onConfirm: () => {
        deleteMutation.mutate(id);
        setConfirmDialog({ isOpen: false, title: '', message: '', onConfirm: () => {} });
      }
    });
  };

  const renderActiveContent = () => {
    const sectionProps = {
      formData,
      setFormData,
      hasAttemptedSubmit,
    };

    switch (activeGroup) {
      case 'profile':
        return <ProfileGroup {...sectionProps} activeTab={activeTab as 'general' | 'languages' | 'validation'} />;
      case 'movies':
        return <MoviesGroup {...sectionProps} activeTab={activeTab as 'indexers' | 'quality' | 'naming'} />;
      case 'tvshows':
        return <TVShowsGroup {...sectionProps} activeTab={activeTab as 'indexers' | 'quality' | 'naming' | 'options'} />;
      case 'anime':
        return <AnimeGroup {...sectionProps} activeTab={activeTab as 'indexers' | 'quality' | 'naming' | 'options'} />;
      case 'music':
        return <MusicGroup {...sectionProps} activeTab={activeTab as 'indexers' | 'quality' | 'naming'} />;
      case 'search':
        return <SearchGroup {...sectionProps} activeTab={activeTab as 'sorting' | 'filters' | 'timing'} />;
      case 'fileoutput':
        return <FileOutputGroup {...sectionProps} />;
      default:
        return null;
    }
  };

  const getProfileSummary = (profile: MediaProfile) => {
    const summaryItems = [];

    // Movie quality
    if (profile.movie_resolutions && profile.movie_resolutions.length > 0) {
      summaryItems.push({
        label: 'Movie Quality',
        value: profile.movie_resolutions.slice(0, 3).join(', ') + (profile.movie_resolutions.length > 3 ? '...' : '')
      });
    }

    // Show quality
    if (profile.show_resolutions && profile.show_resolutions.length > 0) {
      summaryItems.push({
        label: 'TV Quality',
        value: profile.show_resolutions.slice(0, 3).join(', ') + (profile.show_resolutions.length > 3 ? '...' : '')
      });
    }

    // Anime quality
    if (profile.anime_resolutions && profile.anime_resolutions.length > 0) {
      summaryItems.push({
        label: 'Anime Quality',
        value: profile.anime_resolutions.slice(0, 3).join(', ') + (profile.anime_resolutions.length > 3 ? '...' : '')
      });
    }

    // Music quality
    if (profile.music_preferred_quality && profile.music_preferred_quality.length > 0) {
      summaryItems.push({
        label: 'Music Quality',
        value: profile.music_preferred_quality.slice(0, 3).join(', ').toUpperCase()
      });
    }

    // Indexers
    const indexerCount = (profile.movie_indexers?.length || 0) +
                        (profile.show_indexers?.length || 0) +
                        (profile.anime_indexers?.length || 0) +
                        (profile.music_indexers?.length || 0);
    if (indexerCount > 0) {
      summaryItems.push({
        label: 'Indexers',
        value: `${indexerCount} configured`
      });
    }

    return summaryItems;
  };

  return (
    <div className="min-h-screen">
      <PageHeader
        title="Media Profiles"
        description="Configure quality, indexer, naming, and media server preferences for each media type"
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
                {/* Two-Level Navigation Sidebar */}
                <Navigation
                  activeGroup={activeGroup}
                  activeTab={activeTab}
                  onGroupChange={setActiveGroup}
                  onTabChange={setActiveTab}
                />

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

                  {/* Render Active Content */}
                  {renderActiveContent()}
                </div>
              </div>

              {/* Submit Buttons - Fixed Footer */}
              <div className="shrink-0 bg-card border-t border-border p-6">
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
                Create your first media profile to define quality preferences, indexer settings, naming formats, and more for each media type.
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
            {profiles?.map((profile: MediaProfile) => (
              <div key={profile.id} className="bg-card text-card-foreground rounded-xl shadow-md hover:shadow-lg transition-shadow p-6 border border-border">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-2xl font-bold">{profile.name}</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Upgrades: <span className="font-semibold">{profile.upgrade_allowed ? 'Enabled' : 'Disabled'}</span>
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
                  {getProfileSummary(profile).map((item, index) => (
                    <div key={index} className="bg-muted/50 rounded-lg p-3">
                      <div className="font-semibold text-foreground mb-1">{item.label}</div>
                      <div className="text-muted-foreground">{item.value}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Confirm Modal */}
      <ConfirmModal
        isOpen={confirmDialog.isOpen}
        title={confirmDialog.title}
        message={confirmDialog.message}
        variant="danger"
        onConfirm={confirmDialog.onConfirm}
        onCancel={() => setConfirmDialog({ isOpen: false, title: '', message: '', onConfirm: () => {} })}
      />
    </div>
  );
}
