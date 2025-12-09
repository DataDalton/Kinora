'use client';

interface QualityCheckboxListProps {
  items: string[];
  selected: string[];
  onChange: (items: string[]) => void;
  label: string;
  description?: string;
}

export default function QualityCheckboxList({
  items,
  selected,
  onChange,
  label,
  description
}: QualityCheckboxListProps) {
  const toggleItem = (item: string) => {
    if (selected.includes(item)) {
      onChange(selected.filter(i => i !== item));
    } else {
      onChange([...selected, item]);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-lg font-semibold text-foreground mb-1">{label}</label>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {items.map((item, index) => {
          const isSelected = selected.includes(item);
          const qualityRank = index + 1;
          return (
            <button
              type="button"
              key={item}
              onClick={() => toggleItem(item)}
              className={`relative flex items-center gap-4 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                isSelected
                  ? 'bg-primary/10 border-primary shadow-md'
                  : 'bg-muted/30 border-border hover:border-muted-foreground/30 hover:bg-muted/50'
              }`}
            >
              {/* Selection Bubble */}
              <div className={`flex-shrink-0 w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all ${
                isSelected
                  ? 'bg-primary border-primary'
                  : 'border-muted-foreground/30'
              }`}>
                {isSelected && (
                  <svg className="w-4 h-4 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>

              {/* Content */}
              <div className="flex-1 text-left">
                <div className="font-semibold text-base">{item}</div>
                <div className="text-xs text-muted-foreground mt-0.5">Quality Rank #{qualityRank}</div>
              </div>

              {/* Rank Badge */}
              <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                isSelected
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground'
              }`}>
                {qualityRank}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
