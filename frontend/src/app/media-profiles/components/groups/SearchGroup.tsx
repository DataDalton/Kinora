'use client';

import { MediaProfileFormData } from '../types';
import { SearchTab } from '../types';

interface SearchGroupProps {
  formData: MediaProfileFormData;
  setFormData: (data: MediaProfileFormData) => void;
  activeTab: SearchTab;
}

export default function SearchGroup({ formData, setFormData, activeTab }: SearchGroupProps) {
  if (activeTab === 'sorting') {
    return (
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
    );
  }

  if (activeTab === 'filters') {
    return (
      <div className="space-y-6">
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

  if (activeTab === 'timing') {
    return (
      <div className="space-y-6">
        <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
          <h4 className="font-semibold text-sm mb-2">Search Timing Settings</h4>
          <p className="text-xs text-muted-foreground">
            Configure timeout, retry behavior, and result limits for search operations.
          </p>
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
    );
  }

  return null;
}
