'use client';

import { SectionProps } from '../types';
import { QualityCheckboxList } from '../shared';

const HDR_FORMATS = ['Dolby Vision', 'HDR10+', 'HDR10', 'SDR'];

export default function HDRFormats({ formData, setFormData }: SectionProps) {
  return (
    <div className="space-y-6">
      <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
        <h4 className="font-semibold text-sm mb-2">HDR Format Selection</h4>
        <p className="text-xs text-muted-foreground">
          HDR (High Dynamic Range) formats control color depth and dynamic range.
          Dolby Vision (#1) is the highest quality, followed by HDR10+ (#2), HDR10 (#3), and SDR (#4).
        </p>
      </div>
      <QualityCheckboxList
        items={HDR_FORMATS}
        selected={formData.hdr}
        onChange={(items) => setFormData({ ...formData, hdr: items })}
        label="Select HDR Formats"
        description="Select all HDR formats you want. Higher numbers = better quality."
      />
    </div>
  );
}
