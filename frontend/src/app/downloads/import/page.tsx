'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Check, X, Wand2 } from 'lucide-react';
import { usePermissions } from '@/contexts/PermissionContext';
import {
  listImportQueue,
  resolveImport,
  dismissImport,
  suggestImportMatches,
} from '@/lib/api/downloads';
import type { ImportQueueItem, ImportSuggestion } from '@/types/downloads';
import { formatBytes } from '../components/format';

function ImportRow({
  item,
  onChanged,
  notify,
}: {
  item: ImportQueueItem;
  onChanged: () => void;
  notify: (m: string, type?: 'success' | 'error') => void;
}) {
  const needsEpisode = item.media_type === 'show' || item.media_type === 'anime';
  const [season, setSeason] = useState<number>(item.season_number ?? 1);
  const [episode, setEpisode] = useState<number>(item.episode_number ?? 1);
  const [mediaId, setMediaId] = useState<number>(item.media_id ?? 0);
  const [busy, setBusy] = useState(false);
  const [suggestions, setSuggestions] = useState<ImportSuggestion[] | null>(null);
  const [loadingSuggest, setLoadingSuggest] = useState(false);

  const run = async (fn: () => Promise<void>, msg: string) => {
    setBusy(true);
    try {
      await fn();
      onChanged();
      notify(msg, 'success');
    } catch (err: unknown) {
      notify(err instanceof Error ? err.message : 'Failed', 'error');
    } finally {
      setBusy(false);
    }
  };

  const loadSuggestions = async () => {
    setLoadingSuggest(true);
    try {
      setSuggestions(await suggestImportMatches(item.id));
    } catch {
      setSuggestions([]);
    } finally {
      setLoadingSuggest(false);
    }
  };

  return (
    <div className="bg-card text-card-foreground rounded-lg shadow p-4">
      <div className="flex justify-between items-start gap-3 mb-2">
        <div className="min-w-0">
          <p className="font-medium text-sm truncate">{item.file_path.split('/').pop()}</p>
          <p className="text-xs text-muted-foreground truncate">{item.torrent_name}</p>
          <div className="flex gap-3 text-xs text-muted-foreground mt-1">
            {item.media_type && <span className="capitalize px-2 py-0.5 bg-muted rounded">{item.media_type}</span>}
            <span>{formatBytes(item.size ?? 0)}</span>
          </div>
        </div>
      </div>
      {item.error_message && <p className="text-xs text-destructive mb-2">{item.error_message}</p>}

      {suggestions !== null && (
        <div className="mb-3">
          <p className="text-xs text-muted-foreground mb-1">Suggested matches</p>
          {suggestions.length === 0 ? (
            <p className="text-xs text-muted-foreground">No matches found in your library.</p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {suggestions.map((s) => (
                <button
                  key={s.media_id}
                  onClick={() => setMediaId(s.media_id)}
                  className={`px-2.5 py-1 rounded-lg text-xs border transition cursor-pointer ${
                    mediaId === s.media_id
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'border-border hover:bg-accent'
                  }`}
                >
                  {s.title} <span className="opacity-60">#{s.media_id}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className="block text-xs font-medium mb-1">Media ID</label>
          <input
            type="number"
            value={mediaId}
            onChange={(e) => setMediaId(parseInt(e.target.value) || 0)}
            className="w-24 px-3 py-2 rounded-lg bg-background border border-border text-sm focus:outline-none"
          />
        </div>
        <button
          onClick={loadSuggestions}
          disabled={loadingSuggest}
          className="flex items-center gap-1 px-3 py-2 rounded-lg border border-border hover:bg-accent text-sm cursor-pointer disabled:opacity-50"
        >
          <Wand2 className="w-4 h-4" /> {loadingSuggest ? 'Finding...' : 'Suggest'}
        </button>
        {needsEpisode && (
          <>
            <div>
              <label className="block text-xs font-medium mb-1">Season</label>
              <input
                type="number"
                value={season}
                onChange={(e) => setSeason(parseInt(e.target.value) || 0)}
                className="w-20 px-3 py-2 rounded-lg bg-background border border-border text-sm focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Episode</label>
              <input
                type="number"
                value={episode}
                onChange={(e) => setEpisode(parseInt(e.target.value) || 0)}
                className="w-20 px-3 py-2 rounded-lg bg-background border border-border text-sm focus:outline-none"
              />
            </div>
          </>
        )}
        <button
          onClick={() =>
            run(
              () =>
                resolveImport(item.id, {
                  media_id: mediaId || undefined,
                  season_number: needsEpisode ? season : undefined,
                  episode_number: needsEpisode ? episode : undefined,
                }),
              'Imported'
            )
          }
          disabled={busy || !mediaId}
          className="flex items-center gap-1 px-3 py-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 text-sm cursor-pointer disabled:opacity-50"
        >
          <Check className="w-4 h-4" /> Import
        </button>
        <button
          onClick={() => run(() => dismissImport(item.id), 'Dismissed')}
          disabled={busy}
          className="flex items-center gap-1 px-3 py-2 rounded-lg border border-border hover:bg-accent text-sm cursor-pointer"
        >
          <X className="w-4 h-4" /> Dismiss
        </button>
      </div>
    </div>
  );
}

export default function ImportQueuePage() {
  const { hasPermission } = usePermissions();
  const canManage = hasPermission('system.downloads');
  const [toasts, setToasts] = useState<{ id: number; message: string; type: 'success' | 'error' }[]>([]);

  const notify = (message: string, type: 'success' | 'error' = 'success') => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, message, type }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500);
  };

  const { data: items, isLoading, refetch } = useQuery({
    queryKey: ['import-queue'],
    queryFn: listImportQueue,
    refetchInterval: 10000,
    enabled: canManage,
  });

  return (
    <div className="container mx-auto px-6 py-8 max-w-3xl">
      <div className="mb-6">
        <h1 className="text-xl font-bold">Import Queue</h1>
        <p className="text-sm text-muted-foreground">
          Manually map files that could not be auto-organized
        </p>
      </div>

      {!canManage ? (
        <div className="bg-card rounded-lg shadow p-12 text-center text-muted-foreground">
          You do not have permission to manage the import queue.
        </div>
      ) : isLoading ? (
        <div className="text-center py-12 text-muted-foreground">Loading...</div>
      ) : !items || items.length === 0 ? (
        <div className="bg-card rounded-lg shadow p-12 text-center">
          <h2 className="text-xl font-bold mb-2">Nothing to import</h2>
          <p className="text-muted-foreground">
            Files that can&apos;t be automatically matched to an episode will appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <ImportRow key={item.id} item={item} onChanged={refetch} notify={notify} />
          ))}
        </div>
      )}

      <div className="fixed bottom-4 right-4 z-[60] space-y-2">
        {toasts.map((toast) => (
          <div key={toast.id} className={`px-4 py-3 rounded-lg shadow-lg text-sm text-white ${toast.type === 'error' ? 'bg-destructive' : 'bg-green-600'}`}>
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  );
}
