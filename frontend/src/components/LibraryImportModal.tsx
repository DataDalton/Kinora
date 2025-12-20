'use client';

import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { X, Folder, Upload, Check, AlertCircle, Loader2 } from 'lucide-react';

interface LibraryImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  mediaType: 'movie' | 'show' | 'anime' | 'music';
}

interface ScannedFile {
  file_path: string;
  file_name: string;
  title: string;
  year?: number;
  quality?: string;
  file_size?: number;
}

interface MatchedFile {
  id: number;
  title: string;
  poster_path?: string;
  scanned_file: ScannedFile;
}

export default function LibraryImportModal({ isOpen, onClose, mediaType }: LibraryImportModalProps) {
  const [step, setStep] = useState<'setup' | 'scanning' | 'review' | 'importing' | 'complete'>('setup');
  const [directoryPath, setDirectoryPath] = useState('');
  const [rootFolderPath, setRootFolderPath] = useState('');
  const [copyMode, setCopyMode] = useState<'move' | 'copy'>('move');
  const [recursive, setRecursive] = useState(true);
  const [skipSamples, setSkipSamples] = useState(true);
  const [matchedFiles, setMatchedFiles] = useState<MatchedFile[]>([]);
  const [unmatchedFiles, setUnmatchedFiles] = useState<ScannedFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<Set<number>>(new Set());
  const [importResults, setImportResults] = useState<any>(null);

  const { data: profiles } = useQuery({
    queryKey: ['media-profiles'],
    queryFn: async () => {
      const response = await api.get('/media-profiles');
      return response.data;
    },
  });

  const scanMutation = useMutation({
    mutationFn: async (data: {
      directory_path: string;
      media_type: string;
      recursive: boolean;
      skip_samples: boolean;
    }) => {
      const response = await api.post('/library-import/scan', data);
      return response.data;
    },
    onSuccess: (data) => {
      setMatchedFiles(data.matched_files);
      setUnmatchedFiles(data.unmatched_files);
      // Select all matched files by default
      const allIds = new Set<number>(data.matched_files.map((f: MatchedFile) => f.id));
      setSelectedFiles(allIds);
      setStep('review');
    },
  });

  const importMutation = useMutation({
    mutationFn: async (data: {
      scanned_files: MatchedFile[];
      media_type: string;
      root_folder_path: string;
      copy_mode: string;
      monitored: boolean;
    }) => {
      const response = await api.post('/library-import/import', data);
      return response.data;
    },
    onSuccess: (data) => {
      setImportResults(data);
      setStep('complete');
    },
  });

  const handleScan = () => {
    if (!directoryPath) return;
    setStep('scanning');
    scanMutation.mutate({
      directory_path: directoryPath,
      media_type: mediaType,
      recursive,
      skip_samples: skipSamples,
    });
  };

  const handleImport = () => {
    if (!rootFolderPath || selectedFiles.size === 0) return;

    const filesToImport = matchedFiles.filter((f) => selectedFiles.has(f.id));

    setStep('importing');
    importMutation.mutate({
      scanned_files: filesToImport,
      media_type: mediaType,
      root_folder_path: rootFolderPath,
      copy_mode: copyMode,
      monitored: true,
    });
  };

  const toggleFileSelection = (id: number) => {
    const newSelected = new Set(selectedFiles);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedFiles(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedFiles.size === matchedFiles.length) {
      setSelectedFiles(new Set());
    } else {
      setSelectedFiles(new Set(matchedFiles.map((f) => f.id)));
    }
  };

  const handleClose = () => {
    setStep('setup');
    setDirectoryPath('');
    setRootFolderPath('');
    setMatchedFiles([]);
    setUnmatchedFiles([]);
    setSelectedFiles(new Set());
    setImportResults(null);
    onClose();
  };

  if (!isOpen) return null;

  const mediaTypeLabel = mediaType === 'movie' ? 'Movies' : mediaType === 'show' ? 'TV Shows' : mediaType === 'anime' ? 'Anime' : 'Music';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80" onClick={handleClose}>
      <div
        className="bg-zinc-900 rounded-lg w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-zinc-800">
          <h2 className="text-2xl font-bold">Import {mediaTypeLabel} Library</h2>
          <button
            onClick={handleClose}
            className="text-zinc-400 hover:text-white transition-colors cursor-pointer"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Setup Step */}
          {step === 'setup' && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-2">Source Directory</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={directoryPath}
                    onChange={(e) => setDirectoryPath(e.target.value)}
                    placeholder="/path/to/existing/media"
                    className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-4 py-2 focus:outline-none focus:border-blue-500"
                  />
                  <button className="px-4 py-2 bg-zinc-800 border border-zinc-700 rounded hover:bg-zinc-700 transition-colors cursor-pointer">
                    <Folder size={20} />
                  </button>
                </div>
                <p className="text-sm text-zinc-400 mt-1">Directory containing your existing media files</p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Destination Root Folder</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={rootFolderPath}
                    onChange={(e) => setRootFolderPath(e.target.value)}
                    placeholder="/media/movies"
                    className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-4 py-2 focus:outline-none focus:border-blue-500"
                  />
                  <button className="px-4 py-2 bg-zinc-800 border border-zinc-700 rounded hover:bg-zinc-700 transition-colors cursor-pointer">
                    <Folder size={20} />
                  </button>
                </div>
                <p className="text-sm text-zinc-400 mt-1">Where files will be organized</p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">File Operation</label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      value="move"
                      checked={copyMode === 'move'}
                      onChange={(e) => setCopyMode(e.target.value as 'move')}
                      className="accent-blue-500"
                    />
                    <span>Move (delete original)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      value="copy"
                      checked={copyMode === 'copy'}
                      onChange={(e) => setCopyMode(e.target.value as 'copy')}
                      className="accent-blue-500"
                    />
                    <span>Copy (keep original)</span>
                  </label>
                </div>
              </div>

              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={recursive}
                    onChange={(e) => setRecursive(e.target.checked)}
                    className="accent-blue-500"
                  />
                  <span>Scan subdirectories recursively</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={skipSamples}
                    onChange={(e) => setSkipSamples(e.target.checked)}
                    className="accent-blue-500"
                  />
                  <span>Skip sample and trailer files</span>
                </label>
              </div>
            </div>
          )}

          {/* Scanning Step */}
          {step === 'scanning' && (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 size={48} className="animate-spin text-blue-500 mb-4" />
              <p className="text-lg">Scanning directory for media files...</p>
              <p className="text-sm text-zinc-400 mt-2">This may take a few minutes</p>
            </div>
          )}

          {/* Review Step */}
          {step === 'review' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-lg font-medium">
                    Found {matchedFiles.length} matched files
                  </p>
                  {unmatchedFiles.length > 0 && (
                    <p className="text-sm text-yellow-500">
                      {unmatchedFiles.length} files could not be matched
                    </p>
                  )}
                </div>
                <button
                  onClick={toggleSelectAll}
                  className="text-sm text-blue-400 hover:text-blue-300 cursor-pointer"
                >
                  {selectedFiles.size === matchedFiles.length ? 'Deselect All' : 'Select All'}
                </button>
              </div>

              <div className="space-y-2 max-h-96 overflow-y-auto">
                {matchedFiles.map((file) => (
                  <div
                    key={file.id}
                    className="flex items-center gap-3 p-3 bg-zinc-800 rounded hover:bg-zinc-750 transition-colors cursor-pointer"
                    onClick={() => toggleFileSelection(file.id)}
                  >
                    <input
                      type="checkbox"
                      checked={selectedFiles.has(file.id)}
                      onChange={() => toggleFileSelection(file.id)}
                      className="accent-blue-500"
                    />
                    {file.poster_path && (
                      <img
                        src={`https://image.tmdb.org/t/p/w92${file.poster_path}`}
                        alt={file.title}
                        className="w-12 h-18 object-cover rounded"
                      />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{file.title}</p>
                      <p className="text-sm text-zinc-400 truncate">{file.scanned_file.file_name}</p>
                      {file.scanned_file.quality && (
                        <span className="text-xs text-blue-400">{file.scanned_file.quality}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {unmatchedFiles.length > 0 && (
                <details className="mt-4">
                  <summary className="cursor-pointer text-sm text-zinc-400 hover:text-white">
                    Show unmatched files ({unmatchedFiles.length})
                  </summary>
                  <div className="mt-2 space-y-1">
                    {unmatchedFiles.map((file, idx) => (
                      <div key={idx} className="text-sm text-zinc-500 p-2 bg-zinc-800 rounded">
                        {file.file_name}
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          )}

          {/* Importing Step */}
          {step === 'importing' && (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 size={48} className="animate-spin text-blue-500 mb-4" />
              <p className="text-lg">Importing {selectedFiles.size} files...</p>
              <p className="text-sm text-zinc-400 mt-2">
                {copyMode === 'move' ? 'Moving and organizing files' : 'Copying and organizing files'}
              </p>
            </div>
          )}

          {/* Complete Step */}
          {step === 'complete' && importResults && (
            <div className="space-y-4">
              <div className="flex items-center justify-center py-6">
                <div className="text-center">
                  <Check size={64} className="text-green-500 mx-auto mb-4" />
                  <p className="text-2xl font-bold mb-2">Import Complete!</p>
                  <p className="text-zinc-400">
                    Successfully imported {importResults.success_count} of {importResults.success_count + importResults.failed_count} files
                  </p>
                </div>
              </div>

              {importResults.failed_count > 0 && (
                <div className="bg-red-900/20 border border-red-800 rounded p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertCircle size={20} className="text-red-500" />
                    <p className="font-medium text-red-500">
                      {importResults.failed_count} files failed to import
                    </p>
                  </div>
                  <div className="space-y-1 text-sm">
                    {importResults.failed_items.map((item: any, idx: number) => (
                      <div key={idx} className="text-zinc-400">
                        {item.file}: {item.error}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-zinc-800">
          {step === 'setup' && (
            <>
              <button
                onClick={handleClose}
                className="px-4 py-2 text-zinc-400 hover:text-white transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleScan}
                disabled={!directoryPath || !rootFolderPath}
                className="px-6 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 disabled:text-zinc-500 rounded transition-colors cursor-pointer"
              >
                Scan Directory
              </button>
            </>
          )}

          {step === 'review' && (
            <>
              <button
                onClick={() => setStep('setup')}
                className="px-4 py-2 text-zinc-400 hover:text-white transition-colors cursor-pointer"
              >
                Back
              </button>
              <button
                onClick={handleImport}
                disabled={selectedFiles.size === 0}
                className="px-6 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 disabled:text-zinc-500 rounded transition-colors cursor-pointer"
              >
                Import {selectedFiles.size} Files
              </button>
            </>
          )}

          {step === 'complete' && (
            <button
              onClick={handleClose}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-500 rounded transition-colors cursor-pointer"
            >
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
