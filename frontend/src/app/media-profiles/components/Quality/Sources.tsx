'use client';

import { SectionProps } from '../types';
import { QualityCheckboxList } from '../shared';

const SOURCES = ['REMUX', 'BLURAY', 'WEB-DL', 'WEBRIP', 'DVD', 'HDTV', 'SDTV', 'DVDSCR', 'SCREENER', 'TELESYNC', 'CAM'];

export default function Sources({ formData, setFormData, hasAttemptedSubmit }: SectionProps) {
  return (
    <div className={`space-y-6 p-4 rounded-lg border-2 ${
      hasAttemptedSubmit && formData.sources.length === 0
        ? 'border-yellow-500 bg-yellow-500/5'
        : 'border-transparent'
    }`}>
      <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
        <h4 className="font-semibold text-sm mb-2">How Source Upgrades Work</h4>
        <p className="text-xs text-muted-foreground mb-2">
          Sources are ranked from highest (#1 = REMUX) to lowest (#11 = CAM) quality.
          System always prefers lower rank numbers (higher quality sources).
        </p>
        <p className="text-xs text-muted-foreground">
          <strong>Examples:</strong> CAM (theater recording) → WEB-DL (streaming) → BLURAY (disc) → REMUX (uncompressed disc)
        </p>
      </div>
      <QualityCheckboxList
        items={SOURCES}
        selected={formData.sources}
        onChange={(items) => setFormData({ ...formData, sources: items })}
        label="Select Sources"
        description="Select all sources you want. System always prefers higher ranked sources."
      />
    </div>
  );
}
