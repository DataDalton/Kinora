'use client';

import { MediaProfileFormData, FileOutputTab } from '../types';

interface FileOutputGroupProps {
  formData: MediaProfileFormData;
  setFormData: (data: MediaProfileFormData) => void;
  activeTab: FileOutputTab;
}

export default function FileOutputGroup({ formData, setFormData, activeTab }: FileOutputGroupProps) {
  const renderServerTab = () => (
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
    </div>
  );

  const renderFilesTab = () => (
    <div className="space-y-4">
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
  );

  return (
    <div className="space-y-6">
      {activeTab === 'server' && renderServerTab()}
      {activeTab === 'files' && renderFilesTab()}
    </div>
  );
}
