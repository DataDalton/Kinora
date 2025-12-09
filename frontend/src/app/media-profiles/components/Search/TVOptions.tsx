'use client';

import { SectionProps } from '../types';

export default function TVOptions({ formData, setFormData }: SectionProps) {
  return (
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
  );
}
