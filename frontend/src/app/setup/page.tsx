'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { Check, ChevronRight, Server, Key, Folder, Loader2, FolderOpen } from 'lucide-react';

interface SetupStatus {
  is_setup_complete: boolean;
  has_download_client: boolean;
  has_tmdb_key: boolean;
  has_root_folders: boolean;
  user_role: string;
}

type SetupStep = 'qbittorrent' | 'tmdb' | 'folders' | 'complete';

export default function SetupPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [currentStep, setCurrentStep] = useState<SetupStep>('qbittorrent');
  const [isRedirecting, setIsRedirecting] = useState(false);

  const [qbittorrentData, setQBittorrentData] = useState({
    name: 'qBittorrent',
    host: 'localhost',
    port: 8080,
    username: 'admin',
    password: '',
    use_ssl: false,
  });

  const [tmdbData, setTmdbData] = useState({
    api_key: '',
  });

  const [foldersData, setFoldersData] = useState({
    movies_root: '',
    shows_root: '',
    anime_root: '',
  });

  const [showBrowser, setShowBrowser] = useState(false);
  const [browserField, setBrowserField] = useState<'movies_root' | 'shows_root' | 'anime_root' | null>(null);
  const [currentBrowserPath, setCurrentBrowserPath] = useState('/');
  const [manualPath, setManualPath] = useState('/');
  const [isWindows] = useState(() => navigator.platform.toLowerCase().includes('win'));

  // Fetch setup status
  const { data: setupStatus, isLoading: statusLoading } = useQuery<SetupStatus>({
    queryKey: ['setup-status'],
    queryFn: async () => {
      const response = await api.get('/setup/status');
      return response.data;
    },
  });

  // Fetch directory contents for browser
  const { data: browserData, isLoading: browserLoading, error: browserError, refetch: refetchBrowser } = useQuery({
    queryKey: ['browse-directory', currentBrowserPath],
    queryFn: async () => {
      const response = await api.get(`/setup/browse-directory?path=${encodeURIComponent(currentBrowserPath)}`);
      return response.data;
    },
    enabled: showBrowser,
    retry: 1,
  });

  // Sync manual path input with actual browser path
  useEffect(() => {
    if (browserData?.current_path) {
      setManualPath(browserData.current_path);
    }
  }, [browserData]);

  // Redirect if not administrator
  useEffect(() => {
    if (setupStatus && setupStatus.user_role !== 'administrator') {
      setIsRedirecting(true);
      router.push('/');
    }
  }, [setupStatus, router]);

  // Redirect if setup is already complete
  useEffect(() => {
    if (setupStatus?.is_setup_complete && currentStep !== 'complete') {
      setIsRedirecting(true);
      router.push('/');
    }
  }, [setupStatus?.is_setup_complete, currentStep, router]);

  // Configure qBittorrent
  const qbittorrentMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post('/setup/qbittorrent', qbittorrentData);
      return response.data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['setup-status'] });
      setCurrentStep('tmdb');
    },
  });

  // Configure TMDB
  const tmdbMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post('/setup/tmdb', tmdbData);
      return response.data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['setup-status'] });
      setCurrentStep('folders');
    },
  });

  // Configure folders
  const foldersMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post('/setup/root-folders', foldersData);
      return response.data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['setup-status'] });
      setCurrentStep('complete');
    },
  });

  // Complete setup
  const completeMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post('/setup/complete');
      return response.data;
    },
    onSuccess: () => {
      // Invalidate setup status to ensure it's marked as complete
      queryClient.invalidateQueries({ queryKey: ['setup-status'] });
      // Navigate to dashboard
      router.push('/');
    },
  });

  const openBrowser = (field: 'movies_root' | 'shows_root' | 'anime_root') => {
    setBrowserField(field);
    // Start at root - on Windows this will show drive list, on Unix shows /
    setCurrentBrowserPath('/');
    setManualPath('/');
    setShowBrowser(true);
  };

  const navigateToManualPath = () => {
    setCurrentBrowserPath(manualPath);
  };

  const selectFolder = (path: string) => {
    if (browserField) {
      setFoldersData({ ...foldersData, [browserField]: path });
      setShowBrowser(false);
      setBrowserField(null);
    }
  };

  const steps = [
    { id: 'qbittorrent', name: 'Download Client', icon: Server, completed: setupStatus?.has_download_client },
    { id: 'tmdb', name: 'TMDB API', icon: Key, completed: setupStatus?.has_tmdb_key },
    { id: 'folders', name: 'Root Folders', icon: Folder, completed: setupStatus?.has_root_folders },
  ];

  if (statusLoading || isRedirecting) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="flex">
        {/* Left Navigation */}
        <div className="w-64 bg-card border-r border-border p-6 min-h-screen">
          <h2 className="text-xl font-bold mb-6">Initial Setup</h2>
          <nav className="space-y-2">
            {steps.map((step, idx) => {
              const StepIcon = step.icon;
              const isActive = currentStep === step.id;
              const isCompleted = step.completed;

              return (
                <button
                  key={step.id}
                  onClick={() => setCurrentStep(step.id as SetupStep)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors cursor-pointer ${
                    isActive
                      ? 'bg-primary text-primary-foreground'
                      : isCompleted
                      ? 'bg-green-500/10 text-green-500'
                      : 'hover:bg-accent'
                  }`}
                >
                  <div className="flex-shrink-0">
                    {isCompleted ? (
                      <Check className="w-5 h-5" />
                    ) : (
                      <StepIcon className="w-5 h-5" />
                    )}
                  </div>
                  <span className="flex-1 text-left text-sm font-medium">{step.name}</span>
                  {isActive && <ChevronRight className="w-4 h-4" />}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Main Content */}
        <div className="flex-1 p-8">
          <div className="max-w-2xl mx-auto">
            {/* qBittorrent Setup */}
            {currentStep === 'qbittorrent' && (
              <div>
                <h1 className="text-3xl font-bold mb-2">Configure Download Client</h1>
                <p className="text-muted-foreground mb-6">
                  Connect to qBittorrent to download media files
                </p>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Display Name</label>
                    <input
                      type="text"
                      value={qbittorrentData.name}
                      onChange={(e) => setQBittorrentData({ ...qbittorrentData, name: e.target.value })}
                      className="w-full px-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:border-primary"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium mb-2">Host</label>
                      <input
                        type="text"
                        value={qbittorrentData.host}
                        onChange={(e) => setQBittorrentData({ ...qbittorrentData, host: e.target.value })}
                        placeholder="localhost"
                        className="w-full px-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:border-primary"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium mb-2">Port</label>
                      <input
                        type="number"
                        value={qbittorrentData.port}
                        onChange={(e) => setQBittorrentData({ ...qbittorrentData, port: parseInt(e.target.value) })}
                        className="w-full px-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:border-primary"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium mb-2">Username</label>
                      <input
                        type="text"
                        value={qbittorrentData.username}
                        onChange={(e) => setQBittorrentData({ ...qbittorrentData, username: e.target.value })}
                        className="w-full px-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:border-primary"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium mb-2">Password</label>
                      <input
                        type="password"
                        value={qbittorrentData.password}
                        onChange={(e) => setQBittorrentData({ ...qbittorrentData, password: e.target.value })}
                        className="w-full px-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:border-primary"
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <label htmlFor="use_ssl" className="text-sm font-medium">Use SSL (HTTPS)</label>
                    <button
                      type="button"
                      id="use_ssl"
                      onClick={() => setQBittorrentData({ ...qbittorrentData, use_ssl: !qbittorrentData.use_ssl })}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors cursor-pointer ${
                        qbittorrentData.use_ssl ? 'bg-primary' : 'bg-muted'
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          qbittorrentData.use_ssl ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>

                  {qbittorrentMutation.isError && (
                    <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg text-red-500 text-sm">
                      {(qbittorrentMutation.error as any)?.response?.data?.detail || 'Failed to connect to qBittorrent'}
                    </div>
                  )}

                  <button
                    onClick={() => qbittorrentMutation.mutate()}
                    disabled={qbittorrentMutation.isPending || !qbittorrentData.password}
                    className="w-full px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed font-medium flex items-center justify-center gap-2"
                  >
                    {qbittorrentMutation.isPending ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        Testing Connection...
                      </>
                    ) : (
                      'Test & Continue'
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* TMDB Setup */}
            {currentStep === 'tmdb' && (
              <div>
                <h1 className="text-3xl font-bold mb-2">Configure TMDB API</h1>
                <p className="text-muted-foreground mb-6">
                  TMDB API key is required to fetch movie and TV show metadata
                </p>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">TMDB API Key (v3)</label>
                    <input
                      type="text"
                      value={tmdbData.api_key}
                      onChange={(e) => setTmdbData({ api_key: e.target.value })}
                      placeholder="Enter your TMDB API key"
                      className="w-full px-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:border-primary font-mono text-sm"
                    />
                    <p className="text-xs text-muted-foreground mt-2">
                      Don't have an API key?{' '}
                      <a
                        href="https://www.themoviedb.org/settings/api"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        Get one from TMDB
                      </a>
                    </p>
                  </div>

                  {tmdbMutation.isError && (
                    <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg text-red-500 text-sm">
                      {(tmdbMutation.error as any)?.response?.data?.detail || 'Invalid TMDB API key'}
                    </div>
                  )}

                  <div className="flex gap-3">
                    <button
                      onClick={() => setCurrentStep('qbittorrent')}
                      className="px-6 py-3 bg-card border border-border rounded-lg hover:bg-accent font-medium cursor-pointer"
                    >
                      Back
                    </button>
                    <button
                      onClick={() => tmdbMutation.mutate()}
                      disabled={tmdbMutation.isPending || tmdbData.api_key.length < 32}
                      className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed font-medium flex items-center justify-center gap-2"
                    >
                      {tmdbMutation.isPending ? (
                        <>
                          <Loader2 className="w-5 h-5 animate-spin" />
                          Validating...
                        </>
                      ) : (
                        'Validate & Continue'
                      )}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Folders Setup */}
            {currentStep === 'folders' && (
              <div>
                <h1 className="text-3xl font-bold mb-2">Configure Root Folders</h1>
                <p className="text-muted-foreground mb-6">
                  Set where your media files will be organized
                </p>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Movies Root Folder</label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={foldersData.movies_root}
                        onChange={(e) => setFoldersData({ ...foldersData, movies_root: e.target.value })}
                        placeholder={isWindows ? "C:\\Media\\Movies" : "/media/movies"}
                        className="flex-1 px-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:border-primary font-mono text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => openBrowser('movies_root')}
                        className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition flex items-center gap-2 cursor-pointer"
                      >
                        <FolderOpen className="w-4 h-4" />
                        Browse
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2">TV Shows Root Folder</label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={foldersData.shows_root}
                        onChange={(e) => setFoldersData({ ...foldersData, shows_root: e.target.value })}
                        placeholder={isWindows ? "C:\\Media\\Shows" : "/media/shows"}
                        className="flex-1 px-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:border-primary font-mono text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => openBrowser('shows_root')}
                        className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition flex items-center gap-2 cursor-pointer"
                      >
                        <FolderOpen className="w-4 h-4" />
                        Browse
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2">Anime Root Folder</label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={foldersData.anime_root}
                        onChange={(e) => setFoldersData({ ...foldersData, anime_root: e.target.value })}
                        placeholder={isWindows ? "C:\\Media\\Anime" : "/media/anime"}
                        className="flex-1 px-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:border-primary font-mono text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => openBrowser('anime_root')}
                        className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition flex items-center gap-2 cursor-pointer"
                      >
                        <FolderOpen className="w-4 h-4" />
                        Browse
                      </button>
                    </div>
                  </div>

                  {foldersMutation.isError && (
                    <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg text-red-500 text-sm">
                      {(foldersMutation.error as any)?.response?.data?.detail || 'Failed to configure folders'}
                    </div>
                  )}

                  <div className="flex gap-3">
                    <button
                      onClick={() => setCurrentStep('tmdb')}
                      className="px-6 py-3 bg-card border border-border rounded-lg hover:bg-accent font-medium cursor-pointer"
                    >
                      Back
                    </button>
                    <button
                      onClick={() => foldersMutation.mutate()}
                      disabled={foldersMutation.isPending}
                      className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed font-medium flex items-center justify-center gap-2"
                    >
                      {foldersMutation.isPending ? (
                        <>
                          <Loader2 className="w-5 h-5 animate-spin" />
                          Configuring...
                        </>
                      ) : (
                        'Configure & Continue'
                      )}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Complete */}
            {currentStep === 'complete' && (
              <div className="text-center py-12">
                <div className="w-20 h-20 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
                  <Check className="w-10 h-10 text-green-500" />
                </div>
                <h1 className="text-3xl font-bold mb-2">Setup Complete!</h1>
                <p className="text-muted-foreground mb-8">
                  Your Nexarr instance is now configured and ready to use
                </p>

                <button
                  onClick={() => completeMutation.mutate()}
                  disabled={completeMutation.isPending}
                  className="px-8 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 font-medium flex items-center justify-center gap-2 mx-auto cursor-pointer"
                >
                  {completeMutation.isPending ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Finalizing...
                    </>
                  ) : (
                    'Go to Nexarr'
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* File Browser Modal */}
      {showBrowser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-background border border-border rounded-lg w-full max-w-2xl max-h-[80vh] flex flex-col">
            <div className="p-4 border-b border-border flex items-center justify-between">
              <h3 className="text-lg font-semibold">Select Folder</h3>
              <button
                onClick={() => setShowBrowser(false)}
                className="p-2 hover:bg-accent rounded-lg transition cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={manualPath}
                  onChange={(e) => setManualPath(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && navigateToManualPath()}
                  placeholder="Enter path..."
                  className="flex-1 px-3 py-2 bg-card border border-border rounded-lg font-mono text-sm focus:outline-none focus:border-primary"
                />
                <button
                  onClick={navigateToManualPath}
                  className="px-4 py-2 bg-accent text-foreground rounded-lg hover:bg-accent/80 transition whitespace-nowrap cursor-pointer"
                >
                  Go
                </button>
                <button
                  onClick={() => selectFolder(browserData?.current_path || currentBrowserPath)}
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition whitespace-nowrap cursor-pointer"
                >
                  Select Current
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              {browserLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-primary" />
                </div>
              ) : browserError ? (
                <div className="flex flex-col items-center justify-center py-8 gap-4">
                  <div className="text-red-500 text-sm text-center">
                    {(browserError as any)?.response?.data?.detail || 'Failed to browse directory'}
                  </div>
                  <button
                    onClick={() => refetchBrowser()}
                    className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition text-sm cursor-pointer"
                  >
                    Retry
                  </button>
                </div>
              ) : (
                <div className="space-y-1">
                  {/* Parent directory link */}
                  {browserData?.parent_path !== null && browserData?.parent_path !== undefined && (
                    <button
                      onClick={() => setCurrentBrowserPath(browserData.parent_path)}
                      className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-accent transition text-left border-b border-border cursor-pointer"
                    >
                      <Folder className="w-5 h-5 text-muted-foreground shrink-0" />
                      <span className="font-mono text-muted-foreground">..</span>
                    </button>
                  )}

                  {/* Directory listing */}
                  {browserData?.items?.filter((item: any) => item.is_directory).map((item: any) => (
                    <button
                      key={item.path}
                      onClick={() => setCurrentBrowserPath(item.path)}
                      className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-accent transition text-left cursor-pointer"
                    >
                      <Folder className="w-5 h-5 text-primary shrink-0" />
                      <span className="truncate">{item.name}</span>
                    </button>
                  ))}

                  {/* Empty directory message */}
                  {browserData?.items?.filter((item: any) => item.is_directory).length === 0 &&
                   browserData?.parent_path === null && (
                    <div className="text-center py-8 text-muted-foreground text-sm">
                      No subdirectories found
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
