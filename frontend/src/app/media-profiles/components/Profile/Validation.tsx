'use client';

import { useState } from 'react';
import { Shield, AlertTriangle, Trash2, Pause, FolderLock, Plus, X, ShieldCheck, ShieldX } from 'lucide-react';
import { SectionProps } from '../types';

// Default extensions for reference
const DEFAULT_VIDEO_EXTENSIONS = ['.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm', '.ts'];
const DEFAULT_AUDIO_EXTENSIONS = ['.flac', '.mp3', '.m4a', '.aac', '.ogg', '.opus', '.wav', '.wma'];
const DEFAULT_FORBIDDEN_EXTENSIONS = ['.exe', '.bat', '.cmd', '.sh', '.msi', '.dll', '.scr', '.com', '.ps1', '.vbs', '.jar'];

const FAILURE_ACTIONS = [
  {
    value: 'pause_notify',
    label: 'Pause & Notify',
    description: 'Keep torrent paused and notify user for manual review',
    icon: Pause,
  },
  {
    value: 'delete',
    label: 'Delete',
    description: 'Automatically delete torrent and downloaded files',
    icon: Trash2,
  },
  {
    value: 'quarantine',
    label: 'Quarantine',
    description: 'Move to quarantine category for later review',
    icon: FolderLock,
  },
];

const VALIDATION_MODES = [
  {
    value: 'allowlist',
    label: 'Allowlist',
    description: 'Only allow specific file extensions per media type',
    icon: ShieldCheck,
  },
  {
    value: 'blocklist',
    label: 'Blocklist',
    description: 'Block specific file extensions, allow everything else',
    icon: ShieldX,
  },
];

export default function Validation({ formData, setFormData }: SectionProps) {
  const [newForbiddenExt, setNewForbiddenExt] = useState('');
  const [newMovieExt, setNewMovieExt] = useState('');
  const [newShowExt, setNewShowExt] = useState('');
  const [newAnimeExt, setNewAnimeExt] = useState('');
  const [newMusicExt, setNewMusicExt] = useState('');

  const addExtension = (
    field: 'forbidden_extensions' | 'movie_allowed_extensions' | 'show_allowed_extensions' | 'anime_allowed_extensions' | 'music_allowed_extensions',
    value: string,
    setter: (v: string) => void
  ) => {
    const ext = value.trim().toLowerCase();
    if (!ext) return;
    const normalized = ext.startsWith('.') ? ext : `.${ext}`;
    const currentList = formData[field] || [];
    if (!currentList.includes(normalized)) {
      setFormData({
        ...formData,
        [field]: [...currentList, normalized],
      });
    }
    setter('');
  };

  const removeExtension = (
    field: 'forbidden_extensions' | 'movie_allowed_extensions' | 'show_allowed_extensions' | 'anime_allowed_extensions' | 'music_allowed_extensions',
    ext: string
  ) => {
    setFormData({
      ...formData,
      [field]: (formData[field] || []).filter((e) => e !== ext),
    });
  };

  const resetToDefaults = (
    field: 'forbidden_extensions' | 'movie_allowed_extensions' | 'show_allowed_extensions' | 'anime_allowed_extensions' | 'music_allowed_extensions'
  ) => {
    const defaults: Record<string, string[]> = {
      forbidden_extensions: DEFAULT_FORBIDDEN_EXTENSIONS,
      movie_allowed_extensions: DEFAULT_VIDEO_EXTENSIONS,
      show_allowed_extensions: DEFAULT_VIDEO_EXTENSIONS,
      anime_allowed_extensions: ['.mkv', '.mp4', '.avi', '.m4v'],
      music_allowed_extensions: DEFAULT_AUDIO_EXTENSIONS,
    };
    setFormData({
      ...formData,
      [field]: defaults[field] || [],
    });
  };

  return (
    <div className="space-y-6">
      {/* Enable/Disable Validation */}
      <div className="p-4 bg-muted/50 rounded-lg border border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield className="w-5 h-5 text-primary" />
            <div>
              <h3 className="font-semibold text-sm">Torrent Validation</h3>
              <p className="text-xs text-muted-foreground">
                Validate torrent contents before downloading to prevent malicious files
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setFormData({ ...formData, validation_enabled: !formData.validation_enabled })}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors cursor-pointer ${
              formData.validation_enabled ? 'bg-primary' : 'bg-muted'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                formData.validation_enabled ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      </div>

      {formData.validation_enabled && (
        <>
          {/* Validation Mode Selection */}
          <div className="p-4 rounded-lg border border-border">
            <h3 className="font-semibold text-sm mb-3">Validation Mode</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {VALIDATION_MODES.map((mode) => {
                const Icon = mode.icon;
                const isSelected = formData.validation_mode === mode.value;
                return (
                  <button
                    key={mode.value}
                    type="button"
                    onClick={() =>
                      setFormData({
                        ...formData,
                        validation_mode: mode.value as 'blocklist' | 'allowlist',
                      })
                    }
                    className={`p-4 rounded-lg border-2 text-left transition-all cursor-pointer ${
                      isSelected
                        ? 'border-primary bg-primary/10'
                        : 'border-border hover:border-muted-foreground/50'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <Icon className={`w-4 h-4 ${isSelected ? 'text-primary' : 'text-muted-foreground'}`} />
                      <span className={`font-medium text-sm ${isSelected ? 'text-primary' : ''}`}>
                        {mode.label}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">{mode.description}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Failure Action */}
          <div className="p-4 rounded-lg border border-border">
            <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-warning" />
              On Validation Failure
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {FAILURE_ACTIONS.map((action) => {
                const Icon = action.icon;
                const isSelected = formData.validation_failure_action === action.value;
                return (
                  <button
                    key={action.value}
                    type="button"
                    onClick={() =>
                      setFormData({
                        ...formData,
                        validation_failure_action: action.value as 'delete' | 'pause_notify' | 'quarantine',
                      })
                    }
                    className={`p-4 rounded-lg border-2 text-left transition-all cursor-pointer ${
                      isSelected
                        ? 'border-primary bg-primary/10'
                        : 'border-border hover:border-muted-foreground/50'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <Icon className={`w-4 h-4 ${isSelected ? 'text-primary' : 'text-muted-foreground'}`} />
                      <span className={`font-medium text-sm ${isSelected ? 'text-primary' : ''}`}>
                        {action.label}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">{action.description}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Blocklist Mode: Forbidden Extensions */}
          {formData.validation_mode === 'blocklist' && (
            <div className="p-4 rounded-lg border border-border">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="font-semibold text-sm">Forbidden File Extensions</h3>
                  <p className="text-xs text-muted-foreground">
                    Torrents containing these file types will fail validation
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => resetToDefaults('forbidden_extensions')}
                  className="text-xs text-primary hover:underline cursor-pointer"
                >
                  Reset to defaults
                </button>
              </div>

              <div className="flex gap-2 mb-3">
                <input
                  type="text"
                  value={newForbiddenExt}
                  onChange={(e) => setNewForbiddenExt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addExtension('forbidden_extensions', newForbiddenExt, setNewForbiddenExt);
                    }
                  }}
                  placeholder="e.g., .exe"
                  className="flex-1 px-3 py-2 border-input bg-background text-foreground border rounded-lg text-sm"
                />
                <button
                  type="button"
                  onClick={() => addExtension('forbidden_extensions', newForbiddenExt, setNewForbiddenExt)}
                  className="px-3 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 cursor-pointer"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>

              <div className="flex flex-wrap gap-2">
                {(formData.forbidden_extensions || []).map((ext) => (
                  <span
                    key={ext}
                    className="inline-flex items-center gap-1 px-2 py-1 bg-destructive/20 text-destructive rounded text-sm"
                  >
                    {ext}
                    <button
                      type="button"
                      onClick={() => removeExtension('forbidden_extensions', ext)}
                      className="hover:text-destructive/80 cursor-pointer"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {formData.forbidden_extensions.length === 0 && (
                  <span className="text-xs text-destructive italic">No extensions configured - all files will be allowed</span>
                )}
              </div>
            </div>
          )}

          {/* Allowlist Mode: Allowed Extensions by Media Type */}
          {formData.validation_mode === 'allowlist' && (
            <div className="space-y-4">
              <h3 className="font-semibold text-sm">Allowed Extensions by Media Type</h3>
              <p className="text-xs text-muted-foreground -mt-2">
                Torrents must contain at least one file with an allowed extension
              </p>

              {/* Movies */}
              <ExtensionSection
                title="Movies"
                extensions={formData.movie_allowed_extensions || []}
                newValue={newMovieExt}
                setNewValue={setNewMovieExt}
                onAdd={() => addExtension('movie_allowed_extensions', newMovieExt, setNewMovieExt)}
                onRemove={(ext) => removeExtension('movie_allowed_extensions', ext)}
                onReset={() => resetToDefaults('movie_allowed_extensions')}
              />

              {/* TV Shows */}
              <ExtensionSection
                title="TV Shows"
                extensions={formData.show_allowed_extensions || []}
                newValue={newShowExt}
                setNewValue={setNewShowExt}
                onAdd={() => addExtension('show_allowed_extensions', newShowExt, setNewShowExt)}
                onRemove={(ext) => removeExtension('show_allowed_extensions', ext)}
                onReset={() => resetToDefaults('show_allowed_extensions')}
              />

              {/* Anime */}
              <ExtensionSection
                title="Anime"
                extensions={formData.anime_allowed_extensions || []}
                newValue={newAnimeExt}
                setNewValue={setNewAnimeExt}
                onAdd={() => addExtension('anime_allowed_extensions', newAnimeExt, setNewAnimeExt)}
                onRemove={(ext) => removeExtension('anime_allowed_extensions', ext)}
                onReset={() => resetToDefaults('anime_allowed_extensions')}
              />

              {/* Music */}
              <ExtensionSection
                title="Music"
                extensions={formData.music_allowed_extensions || []}
                newValue={newMusicExt}
                setNewValue={setNewMusicExt}
                onAdd={() => addExtension('music_allowed_extensions', newMusicExt, setNewMusicExt)}
                onRemove={(ext) => removeExtension('music_allowed_extensions', ext)}
                onReset={() => resetToDefaults('music_allowed_extensions')}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

interface ExtensionSectionProps {
  title: string;
  extensions: string[];
  newValue: string;
  setNewValue: (v: string) => void;
  onAdd: () => void;
  onRemove: (ext: string) => void;
  onReset: () => void;
}

function ExtensionSection({
  title,
  extensions,
  newValue,
  setNewValue,
  onAdd,
  onRemove,
  onReset,
}: ExtensionSectionProps) {
  return (
    <div className="p-4 rounded-lg border border-border bg-muted/20">
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-medium text-sm">{title}</h4>
        <button
          type="button"
          onClick={onReset}
          className="text-xs text-primary hover:underline cursor-pointer"
        >
          Reset
        </button>
      </div>

      <div className="flex gap-2 mb-3">
        <input
          type="text"
          value={newValue}
          onChange={(e) => setNewValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              onAdd();
            }
          }}
          placeholder="e.g., .mkv"
          className="flex-1 px-3 py-2 border-input bg-background text-foreground border rounded-lg text-sm"
        />
        <button
          type="button"
          onClick={onAdd}
          className="px-3 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 cursor-pointer"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {extensions.map((ext) => (
          <span
            key={ext}
            className="inline-flex items-center gap-1 px-2 py-1 bg-primary/20 text-primary rounded text-sm"
          >
            {ext}
            <button
              type="button"
              onClick={() => onRemove(ext)}
              className="hover:text-primary/80 cursor-pointer"
            >
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}
        {extensions.length === 0 && (
          <span className="text-xs text-muted-foreground italic">No extensions configured</span>
        )}
      </div>
    </div>
  );
}
