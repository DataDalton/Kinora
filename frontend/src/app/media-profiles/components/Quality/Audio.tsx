'use client';

import { SectionProps } from '../types';
import { QualityCheckboxList } from '../shared';

const AUDIO_CODECS = ['FLAC', 'TrueHD', 'Dolby Atmos', 'DTS-HD MA', 'DTS', 'AC3', 'AAC', 'MP3'];
const AUDIO_CHANNELS = ['Atmos', '7.1', '5.1', '2.0'];

export default function Audio({ formData, setFormData }: SectionProps) {
  return (
    <div className="space-y-6">
      <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
        <h4 className="font-semibold text-sm mb-2">How Audio Selection Works</h4>
        <p className="text-xs text-muted-foreground">
          Audio codecs and channels are ranked by quality. Lower rank numbers are better quality.
          FLAC/TrueHD (#1-2) are lossless, DTS/Dolby (#3-5) are high quality lossy.
        </p>
      </div>
      <QualityCheckboxList
        items={AUDIO_CODECS}
        selected={formData.audio}
        onChange={(items) => setFormData({ ...formData, audio: items })}
        label="Select Audio Codecs"
        description="Select all audio codecs you want. Higher numbers = better quality."
      />
      <QualityCheckboxList
        items={AUDIO_CHANNELS}
        selected={formData.audio_channels}
        onChange={(items) => setFormData({ ...formData, audio_channels: items })}
        label="Select Audio Channels"
        description="Select channel configurations you want. More channels = more immersive sound."
      />
    </div>
  );
}
