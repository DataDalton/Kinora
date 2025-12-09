'use client';

import { SectionProps } from '../types';
import { QualityCheckboxList } from '../shared';

const RESOLUTIONS = ['4320p', '2160p', '1080p', '720p', '576p', '480p', '360p', '240p'];

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

interface ResolutionSize {
  minSize: number;
  maxSize: number;
}

interface ResolutionsProps extends SectionProps {
  advancedMode: boolean;
  resolutionSizes: Record<string, ResolutionSize>;
  setResolutionSizes: (sizes: Record<string, ResolutionSize>) => void;
}

export default function Resolutions({
  formData,
  setFormData,
  hasAttemptedSubmit,
  advancedMode,
  resolutionSizes,
  setResolutionSizes
}: ResolutionsProps) {
  return (
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
          <strong>If &quot;Allow Upgrades&quot; is enabled:</strong> System will upgrade from lower to higher quality until reaching the highest selected resolution.<br/>
          <strong>If &quot;Allow Upgrades&quot; is disabled:</strong> System will grab the highest quality available and stop.
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
  );
}
