'use client';

import { useState } from 'react';
import ISO6391 from 'iso-639-1';
import { MediaProfileFormData, AnimeTab } from '../types';
import { QualityCheckboxList } from '../shared';
import {
  RESOLUTIONS,
  VIDEO_CODECS,
  SOURCES,
  AUDIO_CODECS,
  AUDIO_CHANNELS,
  HDR_FORMATS,
  ANIME_PRESETS
} from '../constants';

const INDEXERS_BY_TYPE = {
  anime: ['Nyaa'],
};

const LANGUAGES = ISO6391.getAllCodes().map(code => ({
  code,
  name: ISO6391.getName(code),
  nativeName: ISO6391.getNativeName(code)
}));

const ANIME_TOKENS = [
  { token: '{Anime Title}', description: 'Anime title', example: 'Attack on Titan' },
  { token: '{Anime CleanTitle}', description: 'Clean title without special chars', example: 'Attack on Titan' },
  { token: '{Movie CleanTitle}', description: 'Movie clean title (for films)', example: 'Your Name' },
  { token: '{Release Year}', description: 'Release year', example: '2013' },
  { token: '{TmdbId}', description: 'TMDB database ID', example: '1429' },
  { token: '{AnilistId}', description: 'AniList database ID', example: '16498' },
  { token: '{MalId}', description: 'MyAnimeList database ID', example: '16498' },
  { token: '{Season}', description: 'Season number', example: '01' },
  { token: '{Episode}', description: 'Episode number', example: '25' },
  { token: '{Absolute Episode}', description: 'Absolute episode number', example: '87' },
  { token: '{Episode Title}', description: 'Episode title', example: 'Wall' },
  { token: '{Edition Tags}', description: 'Edition info', example: 'Uncensored' },
  { token: '{Quality Full}', description: 'Full quality string', example: 'Bluray-1080p' },
  { token: '{Quality Resolution}', description: 'Resolution', example: '1080p' },
  { token: '{MediaInfo VideoCodec}', description: 'Video codec', example: 'x265' },
  { token: '{MediaInfo VideoBitDepth}', description: 'Bit depth', example: '10' },
  { token: '{MediaInfo VideoDynamicRangeType}', description: 'HDR type', example: 'HDR10' },
  { token: '{MediaInfo AudioCodec}', description: 'Audio codec', example: 'FLAC' },
  { token: '{MediaInfo AudioChannels}', description: 'Audio channels', example: '2.0' },
  { token: '{MediaInfo AudioLanguages}', description: 'Audio languages', example: 'JA' },
  { token: '{MediaInfo SubtitleLanguages}', description: 'Subtitle languages', example: 'EN' },
  { token: '{Release Group}', description: 'Release group name', example: 'SubsPlease' },
];

interface AnimeGroupProps {
  formData: MediaProfileFormData;
  setFormData: (data: MediaProfileFormData) => void;
  activeTab: AnimeTab;
}

export default function AnimeGroup({ formData, setFormData, activeTab }: AnimeGroupProps) {
  const [animeAudioLanguageSearch, setAnimeAudioLanguageSearch] = useState('');
  const [animeSubtitleLanguageSearch, setAnimeSubtitleLanguageSearch] = useState('');
  const [showBuilder, setShowBuilder] = useState(false);
  const [activeField, setActiveField] = useState<'folder' | 'file'>('file');

  const insertToken = (token: string) => {
    if (activeField === 'folder') {
      setFormData({ ...formData, anime_folder_format: formData.anime_folder_format + token });
    } else {
      setFormData({ ...formData, anime_naming_format: formData.anime_naming_format + token });
    }
  };

  const applyPreset = (preset: typeof ANIME_PRESETS[0]) => {
    setFormData({
      ...formData,
      anime_folder_format: preset.folder,
      anime_naming_format: preset.file
    });
  };

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

  return (
    <div className="space-y-6">
      {/* Indexers Tab */}
      {activeTab === 'indexers' && (
        <div className="space-y-6">
          <div className="bg-purple-500/20 border border-purple-500/30 rounded-lg p-4">
            <h4 className="font-semibold text-sm mb-2">Anime Indexer Configuration</h4>
            <p className="text-xs text-muted-foreground">
              Configure indexers specifically for anime content. Nyaa is the primary anime torrent indexer.
            </p>
          </div>

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
                    <span className="ml-1 px-1.5 py-0.5 text-xs bg-purple-500/20 text-purple-400 rounded">Anime Only</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Quality Tab */}
      {activeTab === 'quality' && (
        <div className="space-y-6">
          <div className="bg-purple-500/20 border border-purple-500/30 rounded-lg p-4">
            <h4 className="font-semibold text-sm mb-2">Anime Quality Settings</h4>
            <p className="text-xs text-muted-foreground">
              Configure quality preferences specifically for anime content. These settings override global quality settings for anime.
            </p>
          </div>

          {/* Resolutions */}
          <div>
            <QualityCheckboxList
              items={RESOLUTIONS}
              selected={formData.anime_resolutions}
              onChange={(items) => setFormData({ ...formData, anime_resolutions: items })}
              label="Anime Resolutions"
              description="Select resolutions for anime content"
            />
          </div>

          {/* Video Codecs */}
          <div>
            <QualityCheckboxList
              items={VIDEO_CODECS}
              selected={formData.anime_codecs}
              onChange={(items) => setFormData({ ...formData, anime_codecs: items })}
              label="Anime Video Codecs"
              description="Select video codecs for anime content"
            />
          </div>

          {/* Sources */}
          <div>
            <QualityCheckboxList
              items={SOURCES}
              selected={formData.anime_sources}
              onChange={(items) => setFormData({ ...formData, anime_sources: items })}
              label="Anime Sources"
              description="Select sources for anime content"
            />
          </div>

          {/* Audio Codecs */}
          <div>
            <QualityCheckboxList
              items={AUDIO_CODECS}
              selected={formData.anime_audio_codecs}
              onChange={(items) => setFormData({ ...formData, anime_audio_codecs: items })}
              label="Anime Audio Codecs"
              description="Select audio codecs for anime content"
            />
          </div>

          {/* Audio Channels */}
          <div>
            <QualityCheckboxList
              items={AUDIO_CHANNELS}
              selected={formData.anime_audio_channels}
              onChange={(items) => setFormData({ ...formData, anime_audio_channels: items })}
              label="Anime Audio Channels"
              description="Select audio channel configurations for anime content"
            />
          </div>

          {/* HDR Formats */}
          <div>
            <QualityCheckboxList
              items={HDR_FORMATS}
              selected={formData.anime_hdr_formats}
              onChange={(items) => setFormData({ ...formData, anime_hdr_formats: items })}
              label="Anime HDR Formats"
              description="Select HDR formats for anime content"
            />
          </div>

          {/* Size Limits */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold mb-2">
                Min Size: {formatSize(formData.anime_min_size || 0)}
              </label>
              <input
                type="range"
                min="0"
                max="102400"
                step="100"
                value={formData.anime_min_size || 0}
                onChange={(e) => {
                  const newMin = parseInt(e.target.value);
                  setFormData({
                    ...formData,
                    anime_min_size: newMin,
                    anime_max_size: formData.anime_max_size && formData.anime_max_size < newMin
                      ? newMin
                      : formData.anime_max_size
                  });
                }}
                className="w-full h-2 bg-background rounded-lg appearance-none cursor-pointer accent-primary"
              />
              <input
                type="text"
                value={formatSize(formData.anime_min_size || 0)}
                onChange={(e) => {
                  const newMin = parseSizeInput(e.target.value);
                  setFormData({
                    ...formData,
                    anime_min_size: newMin,
                    anime_max_size: formData.anime_max_size && formData.anime_max_size < newMin
                      ? newMin
                      : formData.anime_max_size
                  });
                }}
                className="mt-2 w-full px-3 py-1.5 text-sm border-input bg-background text-foreground border rounded"
                placeholder="e.g., 500 MB or 2 GB"
              />
              <p className="text-xs text-muted-foreground mt-1">Minimum file size for anime</p>
            </div>

            <div>
              <label className="block text-sm font-semibold mb-2">
                Max Size: {formatSize(formData.anime_max_size || 0)}
              </label>
              <input
                type="range"
                min={formData.anime_min_size || 0}
                max="102400"
                step="100"
                value={formData.anime_max_size || formData.anime_min_size || 0}
                onChange={(e) => {
                  const newMax = parseInt(e.target.value);
                  setFormData({
                    ...formData,
                    anime_max_size: Math.max(newMax, formData.anime_min_size || 0)
                  });
                }}
                className="w-full h-2 bg-background rounded-lg appearance-none cursor-pointer accent-primary"
              />
              <input
                type="text"
                value={formatSize(formData.anime_max_size || 0)}
                onChange={(e) => {
                  const newMax = parseSizeInput(e.target.value);
                  setFormData({
                    ...formData,
                    anime_max_size: Math.max(newMax, formData.anime_min_size || 0)
                  });
                }}
                className="mt-2 w-full px-3 py-1.5 text-sm border-input bg-background text-foreground border rounded"
                placeholder="e.g., 5 GB or 5000 MB"
              />
              <p className="text-xs text-muted-foreground mt-1">Maximum file size for anime</p>
            </div>
          </div>
        </div>
      )}

      {/* Naming Tab */}
      {activeTab === 'naming' && (
        <div className="space-y-4">
          <div className="bg-purple-500/20 border border-purple-500/30 rounded-lg p-4">
            <h4 className="font-semibold text-sm mb-2">Anime Naming Configuration</h4>
            <p className="text-xs text-muted-foreground">
              Configure folder and file naming formats for anime content using tokens.
            </p>
          </div>

          {/* Anime Folder Format */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="block text-sm font-semibold">Anime Folder Format</label>
              <button
                type="button"
                onClick={() => { setActiveField('folder'); setShowBuilder(true); }}
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

          {/* Anime File Naming Format */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="block text-sm font-semibold">Anime File Naming Format</label>
              <button
                type="button"
                onClick={() => { setActiveField('file'); setShowBuilder(true); }}
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

          {/* Naming Builder Modal */}
          {showBuilder && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
              <div className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden">
                <div className="p-4 border-b border-border flex justify-between items-center">
                  <h3 className="font-semibold text-lg">
                    Anime {activeField === 'folder' ? 'Folder' : 'File'} Naming Builder
                  </h3>
                  <button
                    type="button"
                    onClick={() => setShowBuilder(false)}
                    className="text-muted-foreground hover:text-foreground cursor-pointer"
                  >
                    ✕
                  </button>
                </div>

                <div className="p-4 overflow-y-auto max-h-[calc(90vh-120px)]">
                  {/* Presets */}
                  <div className="mb-6">
                    <h4 className="font-semibold text-sm mb-2">Quick Presets</h4>
                    <div className="flex flex-wrap gap-2">
                      {ANIME_PRESETS.map((preset) => (
                        <button
                          key={preset.name}
                          type="button"
                          onClick={() => applyPreset(preset)}
                          className="px-3 py-1.5 text-xs bg-muted hover:bg-muted/80 rounded-lg cursor-pointer"
                        >
                          {preset.name}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Current Format */}
                  <div className="mb-6">
                    <h4 className="font-semibold text-sm mb-2">Current Format</h4>
                    <textarea
                      value={activeField === 'folder' ? formData.anime_folder_format : formData.anime_naming_format}
                      onChange={(e) => {
                        if (activeField === 'folder') {
                          setFormData({ ...formData, anime_folder_format: e.target.value });
                        } else {
                          setFormData({ ...formData, anime_naming_format: e.target.value });
                        }
                      }}
                      className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
                      rows={3}
                    />
                  </div>

                  {/* Available Tokens */}
                  <div>
                    <h4 className="font-semibold text-sm mb-2">Available Tokens</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {ANIME_TOKENS.map((item) => (
                        <button
                          key={item.token}
                          type="button"
                          onClick={() => insertToken(item.token)}
                          className="flex flex-col items-start p-3 bg-muted/50 hover:bg-muted rounded-lg border border-border cursor-pointer text-left"
                        >
                          <code className="text-xs font-mono text-primary">{item.token}</code>
                          <span className="text-xs text-muted-foreground mt-1">{item.description}</span>
                          <span className="text-xs text-muted-foreground/70 mt-0.5">e.g., {item.example}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="p-4 border-t border-border flex justify-end">
                  <button
                    type="button"
                    onClick={() => setShowBuilder(false)}
                    className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 cursor-pointer"
                  >
                    Done
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Options Tab */}
      {activeTab === 'options' && (
        <div className="space-y-6">
          <div className="bg-purple-500/20 border border-purple-500/30 rounded-lg p-4">
            <h4 className="font-semibold text-sm mb-2">Anime-Specific Options</h4>
            <p className="text-xs text-muted-foreground">
              Configure anime torrent preferences including subtitle types, dub vs sub, and language settings.
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
                  ✕
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
                  ✕
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

          {/* Additional Preferences */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <button
              type="button"
              onClick={() => setFormData({ ...formData, anime_allow_hardsub: !formData.anime_allow_hardsub })}
              className={`flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                formData.anime_allow_hardsub
                  ? 'bg-primary/10 border-primary'
                  : 'bg-muted/30 border-border hover:border-muted-foreground/30'
              }`}
            >
              <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${
                formData.anime_allow_hardsub
                  ? 'bg-primary border-primary'
                  : 'border-muted-foreground/30'
              }`}>
                {formData.anime_allow_hardsub && (
                  <svg className="w-4 h-4 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>
              <div className="text-left">
                <div className="font-semibold text-sm">Allow Hardsubs</div>
                <div className="text-xs text-muted-foreground">Allow torrents with burned-in subtitles</div>
              </div>
            </button>

            <button
              type="button"
              onClick={() => setFormData({ ...formData, anime_prefer_dual_audio: !formData.anime_prefer_dual_audio })}
              className={`flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                formData.anime_prefer_dual_audio
                  ? 'bg-primary/10 border-primary'
                  : 'bg-muted/30 border-border hover:border-muted-foreground/30'
              }`}
            >
              <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${
                formData.anime_prefer_dual_audio
                  ? 'bg-primary border-primary'
                  : 'border-muted-foreground/30'
              }`}>
                {formData.anime_prefer_dual_audio && (
                  <svg className="w-4 h-4 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>
              <div className="text-left">
                <div className="font-semibold text-sm">Prefer Dual Audio</div>
                <div className="text-xs text-muted-foreground">Prioritize Japanese + English audio tracks</div>
              </div>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
