'use client';

import { SectionProps } from '../types';
import { QualityCheckboxList } from '../shared';

const CODECS = ['AV1', 'HEVC', 'x265', 'H265', 'x264', 'H264', 'XVID'];

export default function VideoCodecs({ formData, setFormData, hasAttemptedSubmit }: SectionProps) {
  return (
    <div className={`space-y-6 p-4 rounded-lg border-2 ${
      hasAttemptedSubmit && formData.codecs.length === 0
        ? 'border-yellow-500 bg-yellow-500/5'
        : 'border-transparent'
    }`}>
      <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
        <h4 className="font-semibold text-sm mb-2">How Codec Selection Works</h4>
        <p className="text-xs text-muted-foreground">
          Codecs are ranked by efficiency and quality. Lower rank numbers indicate better compression and quality.
          AV1 (#1) is the most efficient, followed by HEVC/x265 (#2-3), then x264/H264 (#4-5).
        </p>
      </div>
      <QualityCheckboxList
        items={CODECS}
        selected={formData.codecs}
        onChange={(items) => setFormData({ ...formData, codecs: items })}
        label="Select Video Codecs"
        description="Select all codecs you want. Higher numbers = better compression and quality."
      />
    </div>
  );
}
