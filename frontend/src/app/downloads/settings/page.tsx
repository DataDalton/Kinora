'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
  Plus,
  Trash2,
  Save,
  Sprout,
  Brain,
  ShieldCheck,
  ListChecks,
  Wifi,
  X,
  AlertTriangle,
  Pencil,
} from 'lucide-react';
import { usePermissions } from '@/contexts/PermissionContext';
import {
  getDownloadSettings,
  updateDownloadSettings,
  listIndexerRules,
  upsertIndexerRule,
  deleteIndexerRule,
  getNetworkInterfaces,
  setInterfaceBinding,
  getGluetunStatus,
} from '@/lib/api/downloads';
import type {
  AutomationSettings,
  DownloadSettingsUpdate,
  IndexerSeedRule,
  NetworkInterface,
} from '@/types/downloads';

const DEFAULT_AUTOMATION: AutomationSettings = {
  active_peer_pause_enabled: false,
  active_peer_pause_minutes: 30,
  rare_seed_preserve_enabled: false,
  rare_seed_threshold: 5,
  offpeak_enabled: false,
  offpeak_start_hour: 0,
  offpeak_end_hour: 8,
  offpeak_action: 'alt_speed',
  offpeak_days: [],
  disk_pause_enabled: false,
  disk_min_free_gb: 10,
  disk_min_free_unit: 'gb',
  auto_recovery_enabled: false,
  stall_timeout_minutes: 60,
  seed_then_cleanup_enabled: false,
  gluetun_enabled: true,
  gluetun_url: 'http://gluetun:8000',
  vpn_kill_switch_enabled: true,
  vpn_port_sync_enabled: true,
  dl_limit_kbps: 0,
  up_limit_kbps: 0,
  alt_dl_limit_kbps: 0,
  alt_up_limit_kbps: 0,
};

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const SECTIONS = [
  { key: 'seeding', label: 'Seeding defaults', icon: Sprout },
  { key: 'smart', label: 'Smart rules', icon: Brain },
  { key: 'reliability', label: 'Reliability', icon: ShieldCheck },
  { key: 'indexers', label: 'Indexer rules', icon: ListChecks },
  { key: 'vpn', label: 'VPN & network', icon: Wifi },
] as const;

type SectionKey = (typeof SECTIONS)[number]['key'];

// Minute-based duration presets. null means inherit the client's own limit.
const SEED_TIME_PRESETS = [
  { label: 'Default', minutes: null as number | null },
  { label: '1 day', minutes: 1440 },
  { label: '3 days', minutes: 4320 },
  { label: '1 week', minutes: 10080 },
  { label: '2 weeks', minutes: 20160 },
];
const RULE_RATIO_PRESETS = [
  { label: '1×', value: 1 },
  { label: '2×', value: 2 },
  { label: '3×', value: 3 },
];

function chipClass(active: boolean) {
  return `px-4 py-2 rounded-lg text-sm font-medium transition cursor-pointer ${
    active
      ? 'bg-primary text-primary-foreground shadow-sm'
      : 'bg-muted text-muted-foreground hover:bg-muted/70'
  }`;
}

function Switch({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors cursor-pointer ${
        checked ? 'bg-primary' : 'bg-muted'
      }`}
      aria-pressed={checked}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
          checked ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  );
}

// A settings row: label and helper text on the left, control on the right.
function Row({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-6 py-4">
      <div className="min-w-0">
        <div className="text-sm font-medium">{label}</div>
        {hint && <p className="text-xs text-muted-foreground mt-0.5">{hint}</p>}
      </div>
      <div className="shrink-0 flex flex-wrap items-center justify-end gap-2">{children}</div>
    </div>
  );
}

// A settings block: label on top, full-width control below. For sliders and chip grids.
function Block({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="py-4">
      <div className="text-sm font-medium">{label}</div>
      {hint && <p className="text-xs text-muted-foreground mt-0.5">{hint}</p>}
      <div className="mt-3">{children}</div>
    </div>
  );
}

function Card({
  title,
  desc,
  children,
}: {
  title: string;
  desc?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-card text-card-foreground rounded-lg border border-border shadow-sm p-6">
      <h2 className="text-lg font-semibold">{title}</h2>
      {desc && <p className="text-xs text-muted-foreground mt-1">{desc}</p>}
      <div className="mt-2 divide-y divide-border">{children}</div>
    </div>
  );
}

function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string; danger?: boolean }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex flex-wrap gap-2">
      {options.map((opt) => {
        const selected = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={chipClass(selected)}
            style={
              selected && opt.danger
                ? { backgroundColor: 'var(--color-warning)', color: 'var(--color-warning-foreground)' }
                : undefined
            }
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

// A numeric text field that keeps local text while focused, so decimals like
// "2." type through without the committed value snapping back. Commits null on
// an empty field and ignores non-numeric input rather than wiping the value.
function NumericTextInput({
  value,
  onCommit,
  className,
  placeholder,
  toText,
}: {
  value: number | null;
  onCommit: (v: number | null) => void;
  className: string;
  placeholder?: string;
  toText?: (v: number | null) => string;
}) {
  const format = toText ?? ((v: number | null) => (v == null ? '' : String(+v.toFixed(2))));
  const [text, setText] = useState('');
  const [editing, setEditing] = useState(false);
  const shown = editing ? text : format(value);
  return (
    <input
      type="text"
      inputMode="decimal"
      value={shown}
      placeholder={placeholder}
      onFocus={() => {
        setText(format(value));
        setEditing(true);
      }}
      onBlur={() => setEditing(false)}
      onChange={(e) => {
        setText(e.target.value);
        const raw = e.target.value.trim();
        if (raw === '') return onCommit(null);
        const n = Number(raw);
        if (Number.isFinite(n)) onCommit(n);
      }}
      className={className}
    />
  );
}

// Numeric presets with a Custom escape hatch that reveals an exact input.
function PresetField({
  value,
  presets,
  onChange,
  unit,
}: {
  value: number | null;
  presets: { label: string; value: number | null }[];
  onChange: (v: number | null) => void;
  unit?: string;
}) {
  const [customSelected, setCustomSelected] = useState(false);
  // Shows the exact input when the user picks Custom or the value matches no preset.
  const custom =
    customSelected || (value != null && !presets.some((p) => p.value === value));

  return (
    <>
      {presets.map((p) => (
        <button
          key={p.label}
          type="button"
          onClick={() => {
            setCustomSelected(false);
            onChange(p.value);
          }}
          className={chipClass(!custom && p.value === value)}
        >
          {p.label}
        </button>
      ))}
      <button type="button" onClick={() => setCustomSelected(true)} className={chipClass(custom)}>
        Custom
      </button>
      {custom && (
        <span className="inline-flex items-center gap-1.5">
          <NumericTextInput
            value={value}
            onCommit={onChange}
            className="w-24 px-3 py-2 rounded-lg bg-background border border-border text-sm focus:ring-2 focus:ring-primary focus:outline-none"
          />
          {unit && <span className="text-xs text-muted-foreground">{unit}</span>}
        </span>
      )}
    </>
  );
}

// Duration presets stored in minutes. Custom input is in the given unit (days or minutes).
function DurationField({
  value,
  presets,
  onChange,
  customUnit,
  customDivisor,
}: {
  value: number | null;
  presets: { label: string; minutes: number | null }[];
  onChange: (v: number | null) => void;
  customUnit: string;
  customDivisor: number;
}) {
  const [customSelected, setCustomSelected] = useState(false);
  // Shows the exact input when the user picks Custom or the value matches no preset.
  const custom =
    customSelected || (value != null && !presets.some((p) => p.minutes === value));

  return (
    <>
      {presets.map((p) => (
        <button
          key={p.label}
          type="button"
          onClick={() => {
            setCustomSelected(false);
            onChange(p.minutes);
          }}
          className={chipClass(!custom && p.minutes === value)}
        >
          {p.label}
        </button>
      ))}
      <button type="button" onClick={() => setCustomSelected(true)} className={chipClass(custom)}>
        Custom
      </button>
      {custom && (
        <span className="inline-flex items-center gap-1.5">
          <NumericTextInput
            value={value == null ? null : value / customDivisor}
            onCommit={(d) => onChange(d == null ? null : Math.round(d * customDivisor))}
            className="w-24 px-3 py-2 rounded-lg bg-background border border-border text-sm focus:ring-2 focus:ring-primary focus:outline-none"
          />
          <span className="text-xs text-muted-foreground">{customUnit}</span>
        </span>
      )}
    </>
  );
}

// A drag bar with an editable number readout. Typing a value can exceed the
// bar's maximum, the bar just pins at its max while the number keeps the value.
function SliderWithInput({
  value,
  min,
  max,
  step,
  onChange,
  suffix,
}: {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  suffix?: string;
}) {
  return (
    <div className="flex items-center gap-4">
      <input
        type="range"
        min={min}
        max={max}
        step={step ?? 1}
        value={Math.min(Math.max(value, min), max)}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="flex-1 accent-primary cursor-pointer"
      />
      <div className="flex items-center gap-1.5 shrink-0">
        <input
          type="text"
        inputMode="decimal"
          min={min}
          step={step ?? 1}
          value={value}
          onChange={(e) => {
            const raw = e.target.value;
            if (raw.trim() === '') return onChange(min);
            const n = Number(raw);
            if (Number.isFinite(n)) onChange(n);
          }}
          className="w-20 px-3 py-2 rounded-lg bg-background border border-border text-sm focus:ring-2 focus:ring-primary focus:outline-none text-right"
        />
        {suffix && <span className="text-xs text-muted-foreground">{suffix}</span>}
      </div>
    </div>
  );
}

const DURATION_UNITS = [
  { key: 'minutes', label: 'minutes', factor: 1 },
  { key: 'hours', label: 'hours', factor: 60 },
  { key: 'days', label: 'days', factor: 1440 },
] as const;
type DurationUnit = (typeof DURATION_UNITS)[number]['key'];

function pickDurationUnit(minutes: number): DurationUnit {
  if (minutes > 0 && minutes % 1440 === 0) return 'days';
  if (minutes > 0 && minutes % 60 === 0) return 'hours';
  return 'minutes';
}

// A number field paired with a minutes/hours/days unit dropdown. Stores minutes.
function DurationPicker({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [unit, setUnit] = useState<DurationUnit>(() => pickDurationUnit(value));
  const lastValue = useRef(value);
  // Re-pick the unit only on external value changes (e.g. settings loading), not
  // while the user is typing, so a manual unit choice is preserved.
  useEffect(() => {
    if (value !== lastValue.current) {
      setUnit(pickDurationUnit(value));
      lastValue.current = value;
    }
  }, [value]);
  const factor = DURATION_UNITS.find((u) => u.key === unit)!.factor;
  const commit = (d: number | null) => {
    const next = d == null ? 0 : Math.round(d * factor);
    lastValue.current = next;
    onChange(next);
  };
  return (
    <div className="flex items-center gap-2">
      <NumericTextInput
        value={value / factor}
        onCommit={commit}
        className="w-24 px-3 py-2 rounded-lg bg-background border border-border text-sm focus:ring-2 focus:ring-primary focus:outline-none"
      />
      <select
        value={unit}
        onChange={(e) => setUnit(e.target.value as DurationUnit)}
        className="px-3 py-2 rounded-lg bg-background border border-border text-sm focus:ring-2 focus:ring-primary focus:outline-none cursor-pointer"
      >
        {DURATION_UNITS.map((u) => (
          <option key={u.key} value={u.key}>
            {u.label}
          </option>
        ))}
      </select>
    </div>
  );
}

const SPEED_UNITS = [
  { key: 'kb', label: 'KB/s', factor: 1 },
  { key: 'mb', label: 'MB/s', factor: 1024 },
  { key: 'gb', label: 'GB/s', factor: 1024 * 1024 },
] as const;
type SpeedUnit = (typeof SPEED_UNITS)[number]['key'];

function pickSpeedUnit(kbps: number): SpeedUnit {
  if (kbps > 0 && kbps % (1024 * 1024) === 0) return 'gb';
  if (kbps > 0 && kbps % 1024 === 0) return 'mb';
  return 'kb';
}

// A number field paired with a KB/s, MB/s or GB/s unit dropdown. Stores KiB/s, 0 = unlimited.
function SpeedPicker({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [unit, setUnit] = useState<SpeedUnit>(() => pickSpeedUnit(value));
  const lastValue = useRef(value);
  // Re-pick the unit only on external value changes (e.g. settings loading), not
  // while the user is typing, so a manual unit choice is preserved.
  useEffect(() => {
    if (value !== lastValue.current) {
      setUnit(pickSpeedUnit(value));
      lastValue.current = value;
    }
  }, [value]);
  const factor = SPEED_UNITS.find((u) => u.key === unit)!.factor;
  const commit = (d: number | null) => {
    const next = d == null ? 0 : Math.round(d * factor);
    lastValue.current = next;
    onChange(next);
  };
  return (
    <div className="flex items-center gap-2">
      <NumericTextInput
        value={value === 0 ? null : value / factor}
        onCommit={commit}
        placeholder="Unlimited"
        className="w-28 px-3 py-2 rounded-lg bg-background border border-border text-sm focus:ring-2 focus:ring-primary focus:outline-none"
      />
      <select
        value={unit}
        onChange={(e) => setUnit(e.target.value as SpeedUnit)}
        className="px-3 py-2 rounded-lg bg-background border border-border text-sm focus:ring-2 focus:ring-primary focus:outline-none cursor-pointer"
      >
        {SPEED_UNITS.map((u) => (
          <option key={u.key} value={u.key}>
            {u.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function to12h(h: number): string {
  const hour = ((h % 24) + 24) % 24;
  const period = hour < 12 ? 'AM' : 'PM';
  const display = hour % 12 === 0 ? 12 : hour % 12;
  return `${display}:00 ${period}`;
}

// A dual-handle range slider over a 24-hour timeline. The handles are placed
// with the same math as the highlighted band, so the drag point sits exactly
// under each handle. The band is the off-peak window and wraps past midnight
// when the start hour is after the end hour. Handles are keyboard operable.
function HourRangeSlider({
  start,
  end,
  onChange,
}: {
  start: number;
  end: number;
  onChange: (start: number, end: number) => void;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef<'start' | 'end' | null>(null);
  const [active, setActive] = useState<'start' | 'end' | null>(null);
  const pct = (h: number) => (h / 24) * 100;
  const wrap = start > end;

  const nudge = (which: 'start' | 'end') => (e: React.KeyboardEvent) => {
    let delta = 0;
    if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') delta = -1;
    else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') delta = 1;
    else if (e.key === 'Home') delta = -24;
    else if (e.key === 'End') delta = 24;
    else return;
    e.preventDefault();
    const clamp = (h: number) => Math.max(0, Math.min(24, h));
    if (which === 'start') onChange(clamp(start + delta), end);
    else onChange(start, clamp(end + delta));
  };

  const hourFromClientX = (clientX: number) => {
    const el = trackRef.current;
    if (!el) return 0;
    const rect = el.getBoundingClientRect();
    const ratio = (clientX - rect.left) / rect.width;
    return Math.max(0, Math.min(24, Math.round(ratio * 24)));
  };

  // Takes the handle as an argument rather than returning a closure, so the ref
  // write is clearly inside an event handler rather than during render.
  const beginDrag = (which: 'start' | 'end', e: React.PointerEvent) => {
    e.preventDefault();
    dragging.current = which;
    setActive(which);
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const moveDrag = (e: React.PointerEvent) => {
    if (!dragging.current) return;
    const h = hourFromClientX(e.clientX);
    if (dragging.current === 'start') onChange(h, end);
    else onChange(start, h);
  };
  const endDrag = (e: React.PointerEvent) => {
    dragging.current = null;
    setActive(null);
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      // pointer was already released
    }
  };

  // The active handle sits on top while dragging. When the two handles coincide,
  // the start handle is raised so it remains grabbable instead of being covered.
  const startZ = active === 'start' ? 3 : start >= end ? 2 : 1;
  const endZ = active === 'end' ? 3 : 1;

  const barBase: React.CSSProperties = {
    position: 'absolute',
    top: '50%',
    transform: 'translateY(-50%)',
    height: '6px',
    borderRadius: '9999px',
  };
  const handle = (h: number, zIndex: number): React.CSSProperties => ({
    position: 'absolute',
    left: `${pct(h)}%`,
    top: '50%',
    transform: 'translate(-50%, -50%)',
    height: '18px',
    width: '18px',
    borderRadius: '9999px',
    background: 'var(--color-primary)',
    border: '2px solid var(--color-background)',
    boxShadow: '0 0 0 1px var(--color-border)',
    cursor: 'grab',
    touchAction: 'none',
    zIndex,
  });

  return (
    <div>
      <div ref={trackRef} style={{ position: 'relative', height: '24px' }}>
        <div style={{ ...barBase, left: 0, right: 0, background: 'var(--color-muted)' }} />
        {wrap ? (
          <>
            <div style={{ ...barBase, left: `${pct(start)}%`, right: 0, background: 'var(--color-primary)' }} />
            <div style={{ ...barBase, left: 0, width: `${pct(end)}%`, background: 'var(--color-primary)' }} />
          </>
        ) : (
          <div
            style={{
              ...barBase,
              left: `${pct(start)}%`,
              width: `${pct(end) - pct(start)}%`,
              background: 'var(--color-primary)',
            }}
          />
        )}
        <div
          role="slider"
          tabIndex={0}
          aria-label="Off-peak start hour"
          aria-valuenow={start}
          aria-valuemin={0}
          aria-valuemax={24}
          aria-valuetext={to12h(start)}
          className="focus:outline-none focus:ring-2 focus:ring-primary"
          style={handle(start, startZ)}
          onPointerDown={(e) => beginDrag('start', e)}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
          onKeyDown={nudge('start')}
        />
        <div
          role="slider"
          tabIndex={0}
          aria-label="Off-peak end hour"
          aria-valuenow={end}
          aria-valuemin={0}
          aria-valuemax={24}
          aria-valuetext={to12h(end)}
          className="focus:outline-none focus:ring-2 focus:ring-primary"
          style={handle(end, endZ)}
          onPointerDown={(e) => beginDrag('end', e)}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
          onKeyDown={nudge('end')}
        />
      </div>
      <div className="flex justify-between mt-2 text-xs text-muted-foreground">
        <span>12 AM</span>
        <span>6 AM</span>
        <span>12 PM</span>
        <span>6 PM</span>
        <span>12 AM</span>
      </div>
      <div className="mt-3 text-sm">
        <span className="font-medium">{to12h(start)}</span>
        <span className="text-muted-foreground"> to </span>
        <span className="font-medium">{to12h(end)}</span>
        {wrap && <span className="text-muted-foreground"> (overnight)</span>}
        {start === end && <span className="text-muted-foreground"> (all day)</span>}
      </div>
    </div>
  );
}

// A drag bar for a limit that can also be left unset to inherit the client default.
// value is stored in base units (minutes for durations); the bar works in display units.
function LimitSlider({
  value,
  onChange,
  min,
  max,
  step,
  divisor = 1,
  enableDisplay,
  suffix,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
  min: number;
  max: number;
  step?: number;
  divisor?: number;
  enableDisplay: number;
  suffix: string;
}) {
  const active = value != null;
  const display = active ? (value as number) / divisor : enableDisplay;
  const commit = (d: number) => onChange(divisor === 1 ? d : Math.round(d * divisor));

  // Local text lets decimals like "2." type through without the value snapping.
  const [text, setText] = useState('');
  const [editing, setEditing] = useState(false);
  const shown = editing ? text : String(+display.toFixed(2));

  if (!active) {
    return (
      <div className="flex items-center gap-4">
        <span className="text-sm text-muted-foreground flex-1">
          Using the client&apos;s own global limit.
        </span>
        <button
          type="button"
          onClick={() => commit(enableDisplay)}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-muted text-muted-foreground hover:bg-muted/70 cursor-pointer shrink-0"
        >
          Set a limit
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-4">
      <input
        type="range"
        min={min}
        max={max}
        step={step ?? 1}
        value={Math.min(Math.max(display, min), max)}
        onChange={(e) => {
          setEditing(false);
          commit(parseFloat(e.target.value));
        }}
        className="flex-1 accent-primary cursor-pointer"
      />
      <div className="flex items-center gap-1.5 shrink-0">
        <input
          type="text"
          inputMode="decimal"
          value={shown}
          onFocus={() => {
            setText(String(+display.toFixed(2)));
            setEditing(true);
          }}
          onBlur={() => setEditing(false)}
          onChange={(e) => {
            setText(e.target.value);
            const raw = e.target.value.trim();
            if (raw === '') return;
            const n = Number(raw);
            if (Number.isFinite(n)) commit(n);
          }}
          className="w-20 px-3 py-2 rounded-lg bg-background border border-border text-sm focus:ring-2 focus:ring-primary focus:outline-none text-right"
        />
        <span className="text-xs text-muted-foreground">{suffix}</span>
      </div>
      <button
        type="button"
        onClick={() => onChange(null)}
        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-muted text-muted-foreground hover:bg-muted/70 cursor-pointer shrink-0"
      >
        Use default
      </button>
    </div>
  );
}

// The batch of settings persisted by one Save. Used to detect unsaved changes.
type SettingsForm = {
  seedRatio: number | null;
  seedTime: number | null;
  inactiveTime: number | null;
  seedAction: 'pause' | 'remove' | 'remove_delete';
  allowOverride: boolean;
  automation: AutomationSettings;
};

export default function DownloadSettingsPage() {
  const { hasPermission } = usePermissions();
  const canManage = hasPermission('system.downloads');

  const [section, setSection] = useState<SectionKey>('seeding');
  const [seedRatio, setSeedRatio] = useState<number | null>(null);
  const [seedTime, setSeedTime] = useState<number | null>(null);
  const [inactiveTime, setInactiveTime] = useState<number | null>(null);
  const [seedAction, setSeedAction] = useState<'pause' | 'remove' | 'remove_delete'>('pause');
  const [allowOverride, setAllowOverride] = useState(true);
  const [automation, setAutomation] = useState<AutomationSettings>(DEFAULT_AUTOMATION);
  const [gluetunKey, setGluetunKey] = useState('');
  const [rules, setRules] = useState<IndexerSeedRule[]>([]);
  const [showAddRule, setShowAddRule] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [ruleError, setRuleError] = useState<string | null>(null);
  const [newRule, setNewRule] = useState<IndexerSeedRule>({
    indexer: '',
    min_ratio: 1.0,
    min_seed_minutes: 4320,
    enabled: true,
  });
  const [selectedIface, setSelectedIface] = useState('');
  const [ifaceAddress, setIfaceAddress] = useState('');
  const [testingGluetun, setTestingGluetun] = useState(false);
  const [gluetunTest, setGluetunTest] = useState<{ ok: boolean; message: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const router = useRouter();
  const [baseline, setBaseline] = useState<SettingsForm | null>(null);
  const [pendingNav, setPendingNav] = useState<string | null>(null);
  const [confirmSaveOpen, setConfirmSaveOpen] = useState(false);

  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const notify = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3000);
  };

  const { data: settings } = useQuery({
    queryKey: ['download-settings'],
    queryFn: getDownloadSettings,
    enabled: canManage,
  });

  const { data: ruleData, refetch: refetchRules } = useQuery({
    queryKey: ['indexer-rules'],
    queryFn: listIndexerRules,
    enabled: canManage,
  });

  const { data: interfaces } = useQuery<NetworkInterface[]>({
    queryKey: ['net-interfaces'],
    queryFn: getNetworkInterfaces,
    enabled: canManage && section === 'vpn',
  });

  // Seed the form and baseline from the server once. Guarding against re-runs means
  // a later refetch of download-settings cannot silently overwrite unsaved edits.
  const settingsInitialized = useRef(false);
  useEffect(() => {
    if (!settings || settingsInitialized.current) return;
    settingsInitialized.current = true;
    const merged = { ...DEFAULT_AUTOMATION, ...settings.automation };
    const loaded: SettingsForm = {
      seedRatio: settings.seed_ratio_limit ?? null,
      seedTime: settings.seed_time_limit ?? null,
      inactiveTime: settings.inactive_seed_time_limit ?? null,
      seedAction: settings.seed_action ?? 'pause',
      allowOverride: settings.allow_profile_seed_override ?? true,
      automation: merged,
    };
    setSeedRatio(loaded.seedRatio);
    setSeedTime(loaded.seedTime);
    setInactiveTime(loaded.inactiveTime);
    setSeedAction(loaded.seedAction);
    setAllowOverride(loaded.allowOverride);
    setAutomation(merged);
    setBaseline(loaded);
  }, [settings]);

  // Adopt the loaded rules as they arrive.
  const [seenRuleData, setSeenRuleData] = useState(ruleData);
  if (seenRuleData !== ruleData) {
    setSeenRuleData(ruleData);
    if (ruleData) setRules(ruleData);
  }

  // Default the interface binding to the VPN tunnel once, when the list first
  // loads. qBittorrent shares gluetun's network namespace, so the VPN interface
  // (tun0/wg0) is the correct bind target. Guarded by a ref so choosing "Any
  // interface" (value "") does not immediately snap back to the tunnel.
  const [autoSelectedIface, setAutoSelectedIface] = useState(false);
  if (!autoSelectedIface && interfaces && interfaces.length > 0) {
    setAutoSelectedIface(true);
    const vpnIface = interfaces.find(
      (i) => /^(tun|wg)/i.test(i.value) || /^(tun|wg)/i.test(i.name),
    );
    if (vpnIface) setSelectedIface(vpnIface.value);
  }

  const updateAutomation = (patch: Partial<AutomationSettings>) =>
    setAutomation((a) => ({ ...a, ...patch }));

  const toggleDay = (day: number) => {
    const days = automation.offpeak_days.includes(day)
      ? automation.offpeak_days.filter((d) => d !== day)
      : [...automation.offpeak_days, day].sort((a, b) => a - b);
    updateAutomation({ offpeak_days: days });
  };

  const currentForm: SettingsForm = {
    seedRatio,
    seedTime,
    inactiveTime,
    seedAction,
    allowOverride,
    automation,
  };
  const dirty =
    baseline !== null &&
    (JSON.stringify(currentForm) !== JSON.stringify(baseline) || gluetunKey.trim() !== '');
  const isDestructive = seedAction === 'remove' || seedAction === 'remove_delete';
  const destructiveChanged = isDestructive && (!baseline || baseline.seedAction !== seedAction);

  const discardChanges = () => {
    if (!baseline) return;
    setSeedRatio(baseline.seedRatio);
    setSeedTime(baseline.seedTime);
    setInactiveTime(baseline.inactiveTime);
    setSeedAction(baseline.seedAction);
    setAllowOverride(baseline.allowOverride);
    setAutomation(baseline.automation);
    setGluetunKey('');
  };

  const doSave = async () => {
    setConfirmSaveOpen(false);
    setSaving(true);
    try {
      const payload: DownloadSettingsUpdate = {
        seed_ratio_limit: seedRatio,
        seed_time_limit: seedTime,
        inactive_seed_time_limit: inactiveTime,
        seed_action: seedAction,
        allow_profile_seed_override: allowOverride,
        automation,
      };
      if (gluetunKey.trim()) payload.gluetun_api_key = gluetunKey.trim();
      await updateDownloadSettings(payload);
      setGluetunKey('');
      setBaseline(currentForm);
      notify('Settings saved', 'success');
    } catch {
      notify('Failed to save', 'error');
    } finally {
      setSaving(false);
    }
  };

  const requestSave = () => {
    if (destructiveChanged) setConfirmSaveOpen(true);
    else doSave();
  };

  // Warn before leaving with unsaved changes: browser-level for reloads and tab
  // close, and click interception for in-app links so nothing is lost silently.
  useEffect(() => {
    if (!dirty) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [dirty]);

  useEffect(() => {
    if (!dirty) return;
    const onClick = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) {
        return;
      }
      const target = e.target as HTMLElement;
      const anchor = target.closest?.('a');
      if (!anchor) return;
      const href = anchor.getAttribute('href');
      if (!href || !href.startsWith('/') || anchor.target === '_blank') return;
      e.preventDefault();
      setPendingNav(href);
    };
    document.addEventListener('click', onClick, true);
    return () => document.removeEventListener('click', onClick, true);
  }, [dirty]);

  const openAddRule = () => {
    setNewRule({ indexer: '', min_ratio: 1.0, min_seed_minutes: 4320, enabled: true });
    setEditingId(null);
    setRuleError(null);
    setShowAddRule(true);
  };

  const openEditRule = (rule: IndexerSeedRule) => {
    setNewRule({
      indexer: rule.indexer,
      min_ratio: rule.min_ratio,
      min_seed_minutes: rule.min_seed_minutes,
      enabled: rule.enabled,
    });
    setEditingId(rule.id ?? null);
    setRuleError(null);
    setShowAddRule(true);
  };

  const handleSaveRule = async () => {
    const name = newRule.indexer.trim();
    if (!name) {
      setRuleError('Enter an indexer name.');
      return;
    }
    const clash = rules.find(
      (r) => r.indexer.toLowerCase() === name.toLowerCase() && r.id !== editingId,
    );
    if (clash) {
      setRuleError('A rule for this indexer already exists.');
      return;
    }
    try {
      // Upsert the new/renamed rule first, then drop the old row on a rename. If
      // the delete fails, the worst case is a duplicate rather than a lost rule.
      await upsertIndexerRule({ ...newRule, indexer: name });
      if (editingId != null) {
        const original = rules.find((r) => r.id === editingId);
        if (original && original.indexer.toLowerCase() !== name.toLowerCase()) {
          await deleteIndexerRule(editingId);
        }
      }
      setShowAddRule(false);
      setEditingId(null);
      refetchRules();
      notify('Rule saved', 'success');
    } catch {
      setRuleError('Failed to save rule.');
    }
  };

  const toggleRuleEnabled = async (rule: IndexerSeedRule) => {
    try {
      await upsertIndexerRule({ ...rule, enabled: !rule.enabled });
      refetchRules();
    } catch {
      notify('Failed to update rule', 'error');
    }
  };

  const handleDeleteRule = async (id?: number) => {
    if (!id) return;
    await deleteIndexerRule(id);
    refetchRules();
  };

  const applyBinding = async () => {
    try {
      await setInterfaceBinding(selectedIface, ifaceAddress);
      notify('qBittorrent bound to interface', 'success');
    } catch {
      notify('Failed to bind interface', 'error');
    }
  };

  // Tests the saved gluetun config. The API key is write-only, so new values must
  // be saved before they can be tested.
  const testGluetun = async () => {
    setTestingGluetun(true);
    setGluetunTest(null);
    try {
      const status = await getGluetunStatus();
      if (!status.configured) {
        setGluetunTest({
          ok: false,
          message: 'Gluetun is not configured. Save your VPN settings first, then test.',
        });
      } else if (status.running || status.public_ip) {
        const parts = [status.public_ip, status.country, status.provider].filter(Boolean);
        setGluetunTest({ ok: true, message: `Connected. ${parts.join(' · ') || 'Tunnel is up.'}` });
      } else if (status.reachable) {
        // Reached the control server, but the tunnel itself is not up.
        setGluetunTest({
          ok: false,
          message: `Reached gluetun, but the VPN tunnel is ${status.vpn_status || 'not running'}. Set your VPN provider and credentials in docker-compose.`,
        });
      } else {
        setGluetunTest({
          ok: false,
          message: 'Could not reach the gluetun control server. Check that the gluetun container is running.',
        });
      }
    } catch {
      setGluetunTest({
        ok: false,
        message: 'Could not reach the gluetun control server. Check that the gluetun container is running.',
      });
    } finally {
      setTestingGluetun(false);
    }
  };

  if (!canManage) {
    return (
      <div className="container mx-auto px-6 py-8 max-w-4xl">
        <div className="bg-card rounded-lg border border-border shadow-sm p-12 text-center text-muted-foreground">
          You do not have permission to manage download settings.
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-6 py-8 max-w-4xl">
      {settings && !settings.configured && (
        <div className="bg-amber-500/10 text-amber-600 rounded-lg p-4 text-sm mb-6">
          No enabled qBittorrent client is configured. Configure one in Settings first.
        </div>
      )}

      {/* Section navigation */}
      <div className="flex flex-wrap gap-2 mb-6">
        {SECTIONS.map((s) => (
          <button
            key={s.key}
            onClick={() => setSection(s.key)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all cursor-pointer ${
              section === s.key
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'bg-muted text-muted-foreground hover:bg-muted/70'
            }`}
          >
            <s.icon className="w-4 h-4" />
            {s.label}
          </button>
        ))}
      </div>

      {/* Section content */}
      <div className="space-y-6">
        {section === 'seeding' && (
          <>
            <Card
              title="Global seeding defaults"
              desc="Applied to every torrent on add. Choose Default to inherit the client's own global limit. Media profiles can override these when overrides are allowed."
            >
              <Block label="Ratio limit" hint="Stop seeding once this upload ratio is reached.">
                <LimitSlider
                  value={seedRatio}
                  onChange={setSeedRatio}
                  min={0}
                  max={10}
                  step={0.1}
                  enableDisplay={2}
                  suffix="×"
                />
              </Block>
              <Block label="Seeding time" hint="How long to keep seeding after the download completes.">
                <LimitSlider
                  value={seedTime}
                  onChange={setSeedTime}
                  min={0}
                  max={30}
                  step={1}
                  divisor={1440}
                  enableDisplay={7}
                  suffix="days"
                />
              </Block>
              <Block label="Inactive seeding time" hint="Stop seeding after this long with no upload activity.">
                <LimitSlider
                  value={inactiveTime}
                  onChange={setInactiveTime}
                  min={0}
                  max={30}
                  step={1}
                  divisor={1440}
                  enableDisplay={7}
                  suffix="days"
                />
              </Block>
              <Row label="When a limit is reached" hint="What to do once the ratio or time goal is met.">
                <Segmented
                  value={seedAction}
                  onChange={setSeedAction}
                  options={[
                    { value: 'pause', label: 'Pause' },
                    { value: 'remove', label: 'Remove torrent', danger: true },
                    { value: 'remove_delete', label: 'Remove + files', danger: true },
                  ]}
                />
              </Row>
              {isDestructive && (
                <div className="py-4">
                  <div className="flex items-start gap-2 text-xs text-amber-600 bg-amber-500/10 rounded-lg px-3 py-2.5">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                    <span>
                      {seedAction === 'remove_delete'
                        ? 'Kinora will delete the downloaded files once seeding goals and indexer minimums are met. The hardlinked library copy is retained. This runs automatically.'
                        : 'Kinora will remove torrents from the client once seeding goals and indexer minimums are met. Downloaded files are left in place. This runs automatically.'}
                    </span>
                  </div>
                </div>
              )}
            </Card>

            <Card
              title="Speed limits"
              desc="Global download and upload caps for qBittorrent. The alternative limits apply when off-peak scheduling switches to alternative speed. Leave a field blank for unlimited."
            >
              <Row label="Download limit" hint="Maximum global download rate.">
                <SpeedPicker
                  value={automation.dl_limit_kbps}
                  onChange={(v) => updateAutomation({ dl_limit_kbps: v })}
                />
              </Row>
              <Row label="Upload limit" hint="Maximum global upload rate.">
                <SpeedPicker
                  value={automation.up_limit_kbps}
                  onChange={(v) => updateAutomation({ up_limit_kbps: v })}
                />
              </Row>
              <Row label="Alternative download limit" hint="Used during off-peak alternative-speed mode.">
                <SpeedPicker
                  value={automation.alt_dl_limit_kbps}
                  onChange={(v) => updateAutomation({ alt_dl_limit_kbps: v })}
                />
              </Row>
              <Row label="Alternative upload limit" hint="Used during off-peak alternative-speed mode.">
                <SpeedPicker
                  value={automation.alt_up_limit_kbps}
                  onChange={(v) => updateAutomation({ alt_up_limit_kbps: v })}
                />
              </Row>
            </Card>

            <Card title="Profile overrides">
              <Row
                label="Allow media profiles to override"
                hint="When off, all torrents use these global defaults regardless of profile."
              >
                <Switch checked={allowOverride} onChange={setAllowOverride} />
              </Row>
            </Card>
          </>
        )}

        {section === 'smart' && (
          <>
            <Card title="Active-peer-aware seeding">
              <Row
                label="Pause when no leechers"
                hint="Pause seeding when there are no leechers for a while, resume when peers appear."
              >
                <Switch
                  checked={automation.active_peer_pause_enabled}
                  onChange={(v) => updateAutomation({ active_peer_pause_enabled: v })}
                />
              </Row>
              {automation.active_peer_pause_enabled && (
                <Row label="Pause after no leechers for">
                  <DurationPicker
                    value={automation.active_peer_pause_minutes}
                    onChange={(v) => updateAutomation({ active_peer_pause_minutes: v })}
                  />
                </Row>
              )}
            </Card>

            <Card title="Rare-torrent preservation">
              <Row
                label="Keep seeding scarce content"
                hint="Keep seeding while the swarm has fewer than the threshold of seeds."
              >
                <Switch
                  checked={automation.rare_seed_preserve_enabled}
                  onChange={(v) => updateAutomation({ rare_seed_preserve_enabled: v })}
                />
              </Row>
              {automation.rare_seed_preserve_enabled && (
                <Block label="Preserve while swarm seeds below">
                  <SliderWithInput
                    value={automation.rare_seed_threshold}
                    min={1}
                    max={30}
                    onChange={(v) => updateAutomation({ rare_seed_threshold: v })}
                    suffix="seeds"
                  />
                </Block>
              )}
            </Card>

            <Card title="Off-peak scheduling">
              <Row
                label="Throttle or pause during off-peak hours"
                hint="Pick an off-peak window below. During that window, seeding switches to alternative speed or pauses."
              >
                <Switch
                  checked={automation.offpeak_enabled}
                  onChange={(v) => updateAutomation({ offpeak_enabled: v })}
                />
              </Row>
              {automation.offpeak_enabled && (
                <>
                  <Block label="Off-peak hours" hint="Server timezone (UTC unless TZ is set), not your browser's. The action applies inside this window.">
                    <HourRangeSlider
                      start={automation.offpeak_start_hour}
                      end={automation.offpeak_end_hour}
                      onChange={(s, e) =>
                        updateAutomation({ offpeak_start_hour: s, offpeak_end_hour: e })
                      }
                    />
                  </Block>
                  <Row label="During off-peak hours">
                    <Segmented
                      value={automation.offpeak_action}
                      onChange={(v) => updateAutomation({ offpeak_action: v })}
                      options={[
                        { value: 'alt_speed', label: 'Alternative speed' },
                        { value: 'pause', label: 'Pause seeding' },
                      ]}
                    />
                  </Row>
                  <Block label="Active on days" hint="Leave all off to apply every day.">
                    <div className="flex flex-wrap gap-2">
                      {DAYS.map((label, idx) => (
                        <button
                          key={label}
                          type="button"
                          onClick={() => toggleDay(idx)}
                          className={chipClass(automation.offpeak_days.includes(idx))}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </Block>
                </>
              )}
            </Card>

            <Card title="Seed then clean up">
              <Row
                label="Remove torrents once goals are met"
                hint="After seeding goals and tracker minimums are met, remove torrents. The hardlinked library copy is retained. Profiles can also opt in individually."
              >
                <Switch
                  checked={automation.seed_then_cleanup_enabled}
                  onChange={(v) => updateAutomation({ seed_then_cleanup_enabled: v })}
                />
              </Row>
            </Card>
          </>
        )}

        {section === 'reliability' && (
          <>
            <Card title="Stalled/failed auto-recovery">
              <Row
                label="Blocklist and re-search stalled grabs"
                hint="Detect stalled or errored downloads, blocklist them, and search for the next best release matching the profile."
              >
                <Switch
                  checked={automation.auto_recovery_enabled}
                  onChange={(v) => updateAutomation({ auto_recovery_enabled: v })}
                />
              </Row>
              {automation.auto_recovery_enabled && (
                <Row label="Consider stalled after">
                  <DurationPicker
                    value={automation.stall_timeout_minutes}
                    onChange={(v) => updateAutomation({ stall_timeout_minutes: v })}
                  />
                </Row>
              )}
            </Card>

            <Card title="Disk-space-aware pausing">
              <Row
                label="Pause downloads on low disk"
                hint="Pause new downloads when free space drops below the threshold. Never deletes anything."
              >
                <Switch
                  checked={automation.disk_pause_enabled}
                  onChange={(v) => updateAutomation({ disk_pause_enabled: v })}
                />
              </Row>
              {automation.disk_pause_enabled && (
                <>
                  <Row label="Measure free space in">
                    <Segmented
                      value={automation.disk_min_free_unit}
                      onChange={(v) =>
                        updateAutomation({
                          disk_min_free_unit: v,
                          disk_min_free_gb: v === 'percent' ? 10 : 25,
                        })
                      }
                      options={[
                        { value: 'gb', label: 'Gigabytes' },
                        { value: 'percent', label: 'Percent' },
                      ]}
                    />
                  </Row>
                  <Block label="Minimum free space">
                    {automation.disk_min_free_unit === 'percent' ? (
                      <SliderWithInput
                        value={automation.disk_min_free_gb}
                        min={1}
                        max={50}
                        onChange={(v) => updateAutomation({ disk_min_free_gb: v })}
                        suffix="%"
                      />
                    ) : (
                      <SliderWithInput
                        value={automation.disk_min_free_gb}
                        min={5}
                        max={500}
                        step={5}
                        onChange={(v) => updateAutomation({ disk_min_free_gb: v })}
                        suffix="GB"
                      />
                    )}
                  </Block>
                </>
              )}
            </Card>
          </>
        )}

        {section === 'indexers' && (
          <Card
            title="Per-indexer hit-and-run protection"
            desc="Enforce each private tracker's minimum ratio and seed time. Kinora never stops or removes a torrent before its indexer minimums are met."
          >
            <div className="py-4">
              <div className="flex items-start gap-2 text-xs text-muted-foreground bg-muted rounded-lg px-3 py-2.5">
                <ShieldCheck className="w-4 h-4 shrink-0 mt-0.5" />
                <span>
                  These minimums are a floor that overrides the seeding defaults. Where the seeding
                  defaults set the goal for when to stop or remove a torrent, an indexer rule blocks
                  that action until its ratio and seed time are also met, so a tracker&apos;s
                  hit-and-run policy is never violated.
                </span>
              </div>
            </div>
            <div className="py-4 space-y-2">
              {rules.map((rule) => (
                <div
                  key={rule.id}
                  className="flex items-center gap-3 text-sm bg-background rounded-lg border border-border px-4 py-3"
                >
                  <span className="flex-1 font-medium truncate">{rule.indexer}</span>
                  <span className="text-muted-foreground">ratio {rule.min_ratio}</span>
                  <span className="text-muted-foreground">{(rule.min_seed_minutes / 1440).toFixed(1)} days</span>
                  <Switch checked={rule.enabled} onChange={() => toggleRuleEnabled(rule)} />
                  <button
                    onClick={() => openEditRule(rule)}
                    className="p-1.5 rounded hover:bg-muted cursor-pointer"
                    aria-label="Edit rule"
                  >
                    <Pencil className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDeleteRule(rule.id)}
                    className="p-1.5 rounded hover:bg-destructive/10 hover:text-destructive cursor-pointer"
                    aria-label="Delete rule"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
              {rules.length === 0 && (
                <p className="text-sm text-muted-foreground py-2">No indexer rules yet.</p>
              )}
            </div>
            <div className="py-4">
              <button
                type="button"
                onClick={openAddRule}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 shadow-sm cursor-pointer"
              >
                <Plus className="w-4 h-4" /> Add rule
              </button>
            </div>
          </Card>
        )}

        {section === 'vpn' && (
          <>
            <Card
              title="VPN (gluetun)"
              desc="Read the real VPN public IP and forwarded port, control the tunnel, and protect against leaks. Enabled by default for the bundled gluetun container."
            >
              <Row label="Enable gluetun integration">
                <Switch
                  checked={automation.gluetun_enabled}
                  onChange={(v) => updateAutomation({ gluetun_enabled: v })}
                />
              </Row>
              {automation.gluetun_enabled && (
                <>
                  <Row label="Control server URL">
                    <input
                      value={automation.gluetun_url}
                      onChange={(e) => updateAutomation({ gluetun_url: e.target.value })}
                      placeholder="http://gluetun:8000"
                      className="w-64 px-3 py-2 rounded-lg bg-background border border-border text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                    />
                  </Row>
                  <Row
                    label="API key"
                    hint={settings?.gluetun_api_key_set ? 'Stored securely and never shown. Leave blank to keep the current key.' : 'Only if the control server uses apikey auth.'}
                  >
                    {settings?.gluetun_api_key_set && (
                      <span className="flex items-center gap-1 text-xs text-green-500">
                        <ShieldCheck className="w-3.5 h-3.5" /> Configured
                      </span>
                    )}
                    <input
                      type="password"
                      value={gluetunKey}
                      onChange={(e) => setGluetunKey(e.target.value)}
                      placeholder={settings?.gluetun_api_key_set ? 'Enter a new key to replace' : '••••••'}
                      className="w-64 px-3 py-2 rounded-lg bg-background border border-border text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                    />
                  </Row>
                  <Row
                    label="VPN kill switch"
                    hint="Pause all torrents if the tunnel drops or a leak is detected, resume when healthy."
                  >
                    <Switch
                      checked={automation.vpn_kill_switch_enabled}
                      onChange={(v) => updateAutomation({ vpn_kill_switch_enabled: v })}
                    />
                  </Row>
                  <Row
                    label="Auto-sync forwarded port"
                    hint="Keep qBittorrent's listen port matched to the VPN forwarded port."
                  >
                    <Switch
                      checked={automation.vpn_port_sync_enabled}
                      onChange={(v) => updateAutomation({ vpn_port_sync_enabled: v })}
                    />
                  </Row>
                  <div className="py-4">
                    <button
                      type="button"
                      onClick={testGluetun}
                      disabled={testingGluetun}
                      className="px-4 py-2 rounded-lg bg-muted text-muted-foreground text-sm font-medium hover:bg-muted/70 disabled:opacity-50 cursor-pointer"
                    >
                      {testingGluetun ? 'Testing...' : 'Test connection'}
                    </button>
                    {gluetunTest && (
                      <p className={`text-xs mt-2 ${gluetunTest.ok ? 'text-green-500' : 'text-destructive'}`}>
                        {gluetunTest.message}
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground mt-1">
                      Tests the saved configuration. Save changes first to test new values.
                    </p>
                  </div>
                </>
              )}
            </Card>

            <Card
              title="qBittorrent interface binding"
              desc="Bind qBittorrent to the VPN network interface as a kill switch, so a VPN drop stops torrent traffic. The VPN tunnel is selected by default."
            >
              <Row label="Interface">
                <select
                  value={selectedIface}
                  onChange={(e) => setSelectedIface(e.target.value)}
                  className="px-3 py-2 rounded-lg bg-background border border-border text-sm focus:ring-2 focus:ring-primary focus:outline-none w-64 cursor-pointer"
                >
                  <option value="">Any interface</option>
                  {(interfaces ?? []).map((iface) => (
                    <option key={iface.value} value={iface.value}>
                      {iface.name}
                    </option>
                  ))}
                </select>
              </Row>
              <Row label="Bind address" hint="Optional. Leave blank to bind automatically.">
                <input
                  value={ifaceAddress}
                  onChange={(e) => setIfaceAddress(e.target.value)}
                  placeholder="auto"
                  className="w-40 px-3 py-2 rounded-lg bg-background border border-border text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                />
              </Row>
              <div className="py-4">
                <button
                  type="button"
                  onClick={applyBinding}
                  className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 shadow-sm cursor-pointer"
                >
                  Bind interface
                </button>
              </div>
            </Card>
          </>
        )}

      </div>

      {/* Reserve space so the fixed bar never overlaps the last settings. */}
      {dirty && <div aria-hidden style={{ height: '6rem' }} />}

      {/* Sticky unsaved-changes bar. Edits across every section batch into one save. */}
      {dirty && (
        <div
          className="flex justify-center px-4 pb-4"
          style={{ position: 'fixed', left: 0, right: 0, bottom: 0, zIndex: 40, pointerEvents: 'none' }}
        >
          <div
            className="flex items-center gap-4 bg-card border border-border shadow-xl rounded-lg px-6 py-3"
            style={{ pointerEvents: 'auto' }}
          >
            <span className="text-sm text-muted-foreground">You have unsaved changes.</span>
            <button
              onClick={discardChanges}
              disabled={saving}
              className="px-4 py-2 rounded-lg text-sm font-medium bg-muted text-muted-foreground hover:bg-muted/70 disabled:opacity-50 cursor-pointer"
            >
              Discard
            </button>
            <button
              onClick={requestSave}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 shadow-sm disabled:opacity-50 cursor-pointer"
            >
              <Save className="w-4 h-4" /> {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      )}

      {/* Add indexer rule modal */}
      {showAddRule && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-card text-card-foreground rounded-lg border border-border shadow-xl w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <h3 className="text-base font-semibold">
                {editingId != null ? 'Edit indexer rule' : 'Add indexer rule'}
              </h3>
              <button
                onClick={() => setShowAddRule(false)}
                className="p-1 rounded hover:bg-muted cursor-pointer"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">Indexer</label>
                <input
                  value={newRule.indexer}
                  onChange={(e) => {
                    setNewRule({ ...newRule, indexer: e.target.value });
                    if (ruleError) setRuleError(null);
                  }}
                  placeholder="e.g. Rutracker"
                  className="w-full px-3 py-2.5 rounded-lg bg-background border border-border text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                />
                {ruleError && <p className="text-xs text-destructive mt-1.5">{ruleError}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Minimum ratio</label>
                <div className="flex flex-wrap items-center gap-2">
                  <PresetField
                    value={newRule.min_ratio}
                    presets={RULE_RATIO_PRESETS}
                    onChange={(v) => setNewRule({ ...newRule, min_ratio: v ?? 0 })}
                    unit="ratio"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Minimum seed time</label>
                <div className="flex flex-wrap items-center gap-2">
                  <DurationField
                    value={newRule.min_seed_minutes}
                    presets={SEED_TIME_PRESETS.filter((p) => p.minutes !== null)}
                    onChange={(v) => setNewRule({ ...newRule, min_seed_minutes: v ?? 0 })}
                    customUnit="days"
                    customDivisor={1440}
                  />
                </div>
              </div>
              <div className="flex items-center justify-between pt-2">
                <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
                  <Switch
                    checked={newRule.enabled}
                    onChange={(v) => setNewRule({ ...newRule, enabled: v })}
                  />
                  Enabled
                </label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setShowAddRule(false)}
                    className="px-4 py-2 rounded-lg bg-muted text-muted-foreground text-sm font-medium hover:bg-muted/70 cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveRule}
                    disabled={!newRule.indexer.trim()}
                    className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 shadow-sm disabled:opacity-50 cursor-pointer"
                  >
                    Save rule
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Leave-with-unsaved-changes confirmation */}
      {pendingNav && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-card text-card-foreground rounded-lg border border-border shadow-xl w-full max-w-md p-6 space-y-4">
            <h3 className="text-base font-semibold">Discard unsaved changes?</h3>
            <p className="text-sm text-muted-foreground">
              You have unsaved settings changes. Leaving this page will discard them.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setPendingNav(null)}
                className="px-4 py-2 rounded-lg bg-muted text-muted-foreground text-sm font-medium hover:bg-muted/70 cursor-pointer"
              >
                Stay
              </button>
              <button
                onClick={() => {
                  const href = pendingNav;
                  setPendingNav(null);
                  discardChanges();
                  router.push(href);
                }}
                className="px-4 py-2 rounded-lg bg-destructive text-white text-sm font-medium hover:opacity-90 shadow-sm cursor-pointer"
              >
                Discard and leave
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Destructive seed-action save confirmation */}
      {confirmSaveOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-card text-card-foreground rounded-lg border border-border shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-600" />
              <h3 className="text-base font-semibold">Confirm destructive action</h3>
            </div>
            <p className="text-sm text-muted-foreground">
              {seedAction === 'remove_delete'
                ? 'When seeding goals and indexer minimums are met, Kinora will automatically remove torrents and delete their downloaded files. The hardlinked library copy is retained.'
                : 'When seeding goals and indexer minimums are met, Kinora will automatically remove torrents from the client. Downloaded files are left in place.'}
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setConfirmSaveOpen(false)}
                className="px-4 py-2 rounded-lg bg-muted text-muted-foreground text-sm font-medium hover:bg-muted/70 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={doSave}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 shadow-sm cursor-pointer"
              >
                Confirm and save
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-4 right-4 z-50">
          <div className={`px-4 py-3 rounded-lg shadow-lg text-sm text-white ${toast.type === 'error' ? 'bg-destructive' : 'bg-green-600'}`}>
            {toast.message}
          </div>
        </div>
      )}
    </div>
  );
}
