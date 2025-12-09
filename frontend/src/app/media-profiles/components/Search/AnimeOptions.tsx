'use client';

import { useState } from 'react';
import ISO6391 from 'iso-639-1';
import { SectionProps } from '../types';

const LANGUAGES = ISO6391.getAllCodes().map(code => ({
  code,
  name: ISO6391.getName(code),
  nativeName: ISO6391.getNativeName(code)
}));

export default function AnimeOptions({ formData, setFormData }: SectionProps) {
  const [animeAudioLanguageSearch, setAnimeAudioLanguageSearch] = useState('');
  const [animeSubtitleLanguageSearch, setAnimeSubtitleLanguageSearch] = useState('');

  return (
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
  );
}
