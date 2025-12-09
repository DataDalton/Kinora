'use client';

import { SectionProps } from '../types';

export default function Filters({ formData, setFormData, hasAttemptedSubmit }: SectionProps) {
  return (
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
  );
}
