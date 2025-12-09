'use client';

import { SectionProps } from '../types';
import { QualityCheckboxList } from '../shared';

const EDITIONS = ['IMAX', 'Remastered', "Director's Cut", 'Unrated', 'Extended', 'Theatrical'];

export default function SpecialEditions({ formData, setFormData }: SectionProps) {
  return (
    <div className="space-y-6">
      <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
        <h4 className="font-semibold text-sm mb-2">Special Editions Selection</h4>
        <p className="text-xs text-muted-foreground">
          Choose which special editions you prefer. Extended cuts, Director&apos;s Cuts, and IMAX versions often contain additional content.
          PROPER and REPACK indicate fixed/improved releases.
        </p>
      </div>
      <QualityCheckboxList
        items={EDITIONS}
        selected={formData.editions}
        onChange={(items) => setFormData({ ...formData, editions: items })}
        label="Select Editions"
        description="Select which special editions you prefer (e.g., Extended, Director's Cut, IMAX)."
      />
    </div>
  );
}
