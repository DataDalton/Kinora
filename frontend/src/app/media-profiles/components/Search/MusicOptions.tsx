'use client';

import { SectionProps } from '../types';

const AUDIO_QUALITIES = [
  { value: 'flac', label: 'FLAC', description: 'Lossless' },
  { value: 'mp3_320', label: 'MP3 320', description: '320 kbps' },
  { value: 'mp3_256', label: 'MP3 256', description: '256 kbps' },
  { value: 'mp3_128', label: 'MP3 128', description: '128 kbps' },
  { value: 'aac', label: 'AAC', description: 'Lossy' },
  { value: 'ogg', label: 'OGG', description: 'Vorbis' },
];

export default function MusicOptions({ formData, setFormData }: SectionProps) {
  return (
    <div className="space-y-6">
      <div className="bg-pink-500/20 border border-pink-500/30 rounded-lg p-4 mb-4">
        <h4 className="font-semibold text-sm mb-2">Music-Specific Options</h4>
        <p className="text-xs text-muted-foreground">
          Configure music download preferences including audio quality and metadata embedding.
        </p>
      </div>

      {/* Preferred Audio Quality */}
      <div>
        <label className="block text-sm font-semibold mb-2">Preferred Audio Quality</label>
        <p className="text-xs text-muted-foreground mb-3">Select allowed formats in order of preference</p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {AUDIO_QUALITIES.map((quality) => {
            const isSelected = formData.music_preferred_quality.includes(quality.value);
            const position = formData.music_preferred_quality.indexOf(quality.value);
            return (
              <button
                key={quality.value}
                type="button"
                onClick={() => {
                  if (isSelected) {
                    setFormData({
                      ...formData,
                      music_preferred_quality: formData.music_preferred_quality.filter(q => q !== quality.value)
                    });
                  } else {
                    setFormData({
                      ...formData,
                      music_preferred_quality: [...formData.music_preferred_quality, quality.value]
                    });
                  }
                }}
                className={`relative flex flex-col items-center gap-1 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                  isSelected
                    ? 'bg-primary/10 border-primary shadow-md'
                    : 'bg-muted/30 border-border hover:border-muted-foreground/30 hover:bg-muted/50'
                }`}
              >
                {isSelected && (
                  <span className="absolute top-2 left-2 w-5 h-5 rounded-full bg-primary text-primary-foreground text-xs flex items-center justify-center font-bold">
                    {position + 1}
                  </span>
                )}
                <span className="font-semibold text-sm">{quality.label}</span>
                <span className="text-xs text-muted-foreground">{quality.description}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Embed Options */}
      <div className="space-y-4">
        <h4 className="font-semibold text-sm">Metadata Embedding</h4>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Embed Lyrics */}
          <button
            type="button"
            onClick={() => setFormData({ ...formData, music_embed_lyrics: !formData.music_embed_lyrics })}
            className={`flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all ${
              formData.music_embed_lyrics
                ? 'bg-primary/10 border-primary'
                : 'bg-muted/30 border-border hover:border-muted-foreground/30'
            }`}
          >
            <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${
              formData.music_embed_lyrics
                ? 'bg-primary border-primary'
                : 'border-muted-foreground/30'
            }`}>
              {formData.music_embed_lyrics && (
                <svg className="w-4 h-4 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              )}
            </div>
            <div className="text-left">
              <div className="font-semibold text-sm">Embed Lyrics</div>
              <div className="text-xs text-muted-foreground">Include lyrics in audio file metadata</div>
            </div>
          </button>

          {/* Embed Artwork */}
          <button
            type="button"
            onClick={() => setFormData({ ...formData, music_embed_artwork: !formData.music_embed_artwork })}
            className={`flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all ${
              formData.music_embed_artwork
                ? 'bg-primary/10 border-primary'
                : 'bg-muted/30 border-border hover:border-muted-foreground/30'
            }`}
          >
            <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${
              formData.music_embed_artwork
                ? 'bg-primary border-primary'
                : 'border-muted-foreground/30'
            }`}>
              {formData.music_embed_artwork && (
                <svg className="w-4 h-4 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              )}
            </div>
            <div className="text-left">
              <div className="font-semibold text-sm">Embed Album Artwork</div>
              <div className="text-xs text-muted-foreground">Include album art in audio file metadata</div>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}
