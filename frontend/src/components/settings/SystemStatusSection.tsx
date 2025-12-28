'use client';

import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import PageHeader from '@/components/PageHeader';
import { getSystemStatus, refreshSystemStatus } from '@/lib/api/system-status';
import type {
  ServiceStatus,
  CeleryTaskStatus,
  DownloadClientStatus,
  ExternalApiStatus,
  ServiceStatusLevel,
  TaskStatusLevel,
  DownloadClientStatusLevel,
  ApiStatusLevel,
} from '@/types/system-status';
import {
  Database,
  Server,
  Clock,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertCircle,
  Wifi,
  WifiOff,
  Activity,
  Download,
  Globe,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

// Status color utilities for service status
function getServiceStatusColor(status: ServiceStatusLevel): string {
  switch (status) {
    case 'healthy':
      return 'text-green-500';
    case 'degraded':
      return 'text-yellow-500';
    case 'error':
      return 'text-red-500';
    case 'not_configured':
      return 'text-gray-400';
    default:
      return 'text-gray-400';
  }
}

function getServiceStatusBg(status: ServiceStatusLevel): string {
  switch (status) {
    case 'healthy':
      return 'bg-green-500/10 border-green-500/20';
    case 'degraded':
      return 'bg-yellow-500/10 border-yellow-500/20';
    case 'error':
      return 'bg-red-500/10 border-red-500/20';
    case 'not_configured':
      return 'bg-gray-500/10 border-gray-500/20';
    default:
      return 'bg-gray-500/10 border-gray-500/20';
  }
}

// Status color utilities for task status
function getTaskStatusColor(status: TaskStatusLevel): string {
  switch (status) {
    case 'running':
      return 'text-blue-500';
    case 'idle':
      return 'text-green-500';
    case 'failed':
      return 'text-red-500';
    default:
      return 'text-gray-400';
  }
}

function getTaskStatusBg(status: TaskStatusLevel): string {
  switch (status) {
    case 'running':
      return 'bg-blue-500/10';
    case 'idle':
      return 'bg-green-500/10';
    case 'failed':
      return 'bg-red-500/10';
    default:
      return 'bg-gray-500/10';
  }
}

// Status color utilities for download client status
function getDownloadClientStatusColor(status: DownloadClientStatusLevel): string {
  switch (status) {
    case 'connected':
      return 'text-green-500';
    case 'error':
      return 'text-red-500';
    case 'disabled':
      return 'text-gray-400';
    default:
      return 'text-gray-400';
  }
}

function getDownloadClientStatusBg(status: DownloadClientStatusLevel): string {
  switch (status) {
    case 'connected':
      return 'bg-green-500/10 border-green-500/20';
    case 'error':
      return 'bg-red-500/10 border-red-500/20';
    case 'disabled':
      return 'bg-gray-500/10 border-gray-500/20';
    default:
      return 'bg-gray-500/10 border-gray-500/20';
  }
}

// Status color utilities for external API status
function getApiStatusColor(status: ApiStatusLevel): string {
  switch (status) {
    case 'healthy':
      return 'text-green-500';
    case 'error':
      return 'text-red-500';
    case 'not_configured':
      return 'text-gray-400';
    default:
      return 'text-gray-400';
  }
}

function getApiStatusBg(status: ApiStatusLevel): string {
  switch (status) {
    case 'healthy':
      return 'bg-green-500/10 border-green-500/20';
    case 'error':
      return 'bg-red-500/10 border-red-500/20';
    case 'not_configured':
      return 'bg-gray-500/10 border-gray-500/20';
    default:
      return 'bg-gray-500/10 border-gray-500/20';
  }
}

// Format duration in milliseconds to human-readable string
function formatDuration(ms: number | null): string {
  if (ms === null) return '-';
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}

// Format relative time from ISO string
function formatRelativeTime(isoString: string | null): string {
  if (!isoString) return 'Never';
  try {
    return formatDistanceToNow(new Date(isoString), { addSuffix: true });
  } catch {
    return 'Unknown';
  }
}

// Service status icon component
function ServiceStatusIcon({ status }: { status: ServiceStatusLevel }) {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="w-5 h-5" />;
    case 'degraded':
      return <AlertCircle className="w-5 h-5" />;
    case 'error':
      return <XCircle className="w-5 h-5" />;
    case 'not_configured':
      return <AlertCircle className="w-5 h-5" />;
    default:
      return <Activity className="w-5 h-5" />;
  }
}

// Download client status icon component
function DownloadClientStatusIcon({ status }: { status: DownloadClientStatusLevel }) {
  switch (status) {
    case 'connected':
      return <Wifi className="w-4 h-4" />;
    case 'error':
      return <WifiOff className="w-4 h-4" />;
    case 'disabled':
      return <WifiOff className="w-4 h-4" />;
    default:
      return <Activity className="w-4 h-4" />;
  }
}

// Core service card component
function CoreServiceCard({
  service,
  icon,
  title,
}: {
  service: ServiceStatus;
  icon: React.ReactNode;
  title: string;
}) {
  return (
    <div className={`bg-card border rounded-lg p-4 ${getServiceStatusBg(service.status)}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg">{icon}</div>
          <div>
            <h3 className="font-semibold">{title}</h3>
            <p className="text-sm text-muted-foreground">{service.name}</p>
          </div>
        </div>
        <div className={`flex items-center gap-2 ${getServiceStatusColor(service.status)}`}>
          <ServiceStatusIcon status={service.status} />
          <span className="text-sm font-medium capitalize">{service.status}</span>
        </div>
      </div>
      {service.latencyMs !== null && (
        <div className="text-xs text-muted-foreground">Latency: {service.latencyMs}ms</div>
      )}
      {service.message && (
        <div className="text-xs text-muted-foreground mt-1">{service.message}</div>
      )}
    </div>
  );
}

// Download client card component
function DownloadClientCard({ client }: { client: DownloadClientStatus }) {
  return (
    <div className={`bg-card border rounded-lg p-4 ${getDownloadClientStatusBg(client.status)}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg">
            <Download className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h3 className="font-semibold">{client.name}</h3>
            <p className="text-xs text-muted-foreground">{client.clientType}</p>
          </div>
        </div>
        <div className={`flex items-center gap-2 ${getDownloadClientStatusColor(client.status)}`}>
          <DownloadClientStatusIcon status={client.status} />
          <span className="text-sm font-medium capitalize">{client.status}</span>
        </div>
      </div>
      {client.version && (
        <div className="text-xs text-muted-foreground mt-2">Version: {client.version}</div>
      )}
      {client.message && (
        <div className="text-xs text-muted-foreground mt-1">{client.message}</div>
      )}
    </div>
  );
}

// External API card component
function ExternalApiCard({ name, api }: { name: string; api: ExternalApiStatus }) {
  return (
    <div className={`bg-card border rounded-lg p-4 ${getApiStatusBg(api.status)}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg">
            <Globe className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h3 className="font-semibold">{api.name || name}</h3>
          </div>
        </div>
        <div className={`flex items-center gap-2 ${getApiStatusColor(api.status)}`}>
          {api.status === 'healthy' && <CheckCircle className="w-4 h-4" />}
          {api.status === 'error' && <XCircle className="w-4 h-4" />}
          {api.status === 'not_configured' && <Activity className="w-4 h-4" />}
          <span className="text-sm font-medium capitalize">
            {api.status === 'not_configured' ? 'Not Configured' : api.status}
          </span>
        </div>
      </div>
      {api.lastChecked && (
        <div className="text-xs text-muted-foreground mt-2">
          Last checked: {formatRelativeTime(api.lastChecked)}
        </div>
      )}
      {api.message && (
        <div className="text-xs text-muted-foreground mt-1">{api.message}</div>
      )}
    </div>
  );
}

// Celery tasks table component
function CeleryTasksTable({ tasks }: { tasks: CeleryTaskStatus[] }) {
  if (tasks.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">No scheduled tasks configured</div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      <table className="w-full">
        <thead className="bg-muted">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
              Task
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
              Schedule
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
              Last Run
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
              Duration
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
              Next Run
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
              Status
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {tasks.map((task) => (
            <tr key={task.taskName} className="hover:bg-muted/30">
              <td className="px-4 py-3 whitespace-nowrap">
                <div className="font-medium">{task.displayName}</div>
                <div className="text-xs text-muted-foreground">{task.taskName}</div>
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm">{task.schedule}</td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-muted-foreground">
                {formatRelativeTime(task.lastRunTime)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-muted-foreground">
                {formatDuration(task.lastDurationMs)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-muted-foreground">
                {formatRelativeTime(task.nextRunTime)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap">
                <span
                  className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${getTaskStatusBg(task.status)} ${getTaskStatusColor(task.status)}`}
                >
                  {task.status === 'running' && <Activity className="w-3 h-3 animate-pulse" />}
                  {task.status === 'idle' && <CheckCircle className="w-3 h-3" />}
                  {task.status === 'failed' && <XCircle className="w-3 h-3" />}
                  {task.status === 'unknown' && <AlertCircle className="w-3 h-3" />}
                  <span className="capitalize">{task.status}</span>
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Loading skeleton component
function LoadingSkeleton() {
  return (
    <div className="space-y-8 animate-pulse">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-card border border-border rounded-lg p-4 h-24" />
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-card border border-border rounded-lg p-4 h-20" />
        ))}
      </div>
      <div className="bg-card border border-border rounded-lg h-64" />
    </div>
  );
}

export default function SystemStatusSection() {
  const queryClient = useQueryClient();
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Fetch system status
  const {
    data: systemStatus,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['system-status'],
    queryFn: getSystemStatus,
    refetchInterval: autoRefresh ? 30000 : false,
  });

  // Update last refresh time when data changes
  useEffect(() => {
    if (systemStatus) {
      setLastRefresh(new Date());
    }
  }, [systemStatus]);

  // Manual refresh handler
  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    try {
      await refreshSystemStatus();
      await queryClient.invalidateQueries({ queryKey: ['system-status'] });
      setLastRefresh(new Date());
    } catch (err) {
      console.error('Failed to refresh system status:', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="System Status"
        description="Monitor core services, background tasks, and external integrations"
        gradientFrom="violet-600/10"
        gradientVia="purple-600/10"
        gradientTo="indigo-600/10"
      />

      <div className="p-8">
        <div className="max-w-7xl mx-auto">
          {/* Controls */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-4">
              <button
                onClick={handleManualRefresh}
                disabled={isLoading || isRefreshing}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 transition cursor-pointer"
              >
                <RefreshCw
                  className={`w-4 h-4 ${isLoading || isRefreshing ? 'animate-spin' : ''}`}
                />
                Refresh
              </button>
              <button
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition cursor-pointer ${
                  autoRefresh
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                }`}
              >
                <Clock className={`w-4 h-4 ${autoRefresh ? 'animate-pulse' : ''}`} />
                Auto-refresh {autoRefresh ? 'On' : 'Off'}
              </button>
            </div>
            <div className="text-sm text-muted-foreground">
              Last updated: {lastRefresh.toLocaleTimeString()}
              {systemStatus?.version && (
                <span className="ml-4">Version: {systemStatus.version}</span>
              )}
            </div>
          </div>

          {/* Error state */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 mb-6">
              <div className="flex items-center gap-2 text-red-500">
                <XCircle className="w-5 h-5" />
                <span className="font-medium">Failed to load system status</span>
              </div>
              <p className="text-sm text-muted-foreground mt-1">
                {error instanceof Error ? error.message : 'An unknown error occurred'}
              </p>
            </div>
          )}

          {/* Loading state */}
          {isLoading && !systemStatus && <LoadingSkeleton />}

          {/* Content */}
          {systemStatus && (
            <div className="space-y-8">
              {/* Core Services */}
              <section>
                <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                  <Server className="w-5 h-5" />
                  Core Services
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <CoreServiceCard
                    service={systemStatus.database}
                    icon={<Database className="w-5 h-5 text-primary" />}
                    title="Database"
                  />
                  {systemStatus.pgBouncer.status !== 'not_configured' && (
                    <CoreServiceCard
                      service={systemStatus.pgBouncer}
                      icon={<Database className="w-5 h-5 text-primary" />}
                      title="Connection Pool"
                    />
                  )}
                  <CoreServiceCard
                    service={systemStatus.cache}
                    icon={<Server className="w-5 h-5 text-primary" />}
                    title="Cache"
                  />
                  <CoreServiceCard
                    service={systemStatus.celery}
                    icon={<Activity className="w-5 h-5 text-primary" />}
                    title="Task Queue"
                  />
                </div>
              </section>

              {/* Queue Status */}
              {systemStatus.queues.length > 0 && (
                <section>
                  <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                    <Activity className="w-5 h-5" />
                    Queue Status
                  </h2>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {systemStatus.queues.map((queue) => (
                      <div
                        key={queue.name}
                        className="bg-card border border-border rounded-lg p-4"
                      >
                        <div className="flex items-center justify-between">
                          <h3 className="font-semibold">{queue.name}</h3>
                          <span className="text-2xl font-bold">{queue.depth}</span>
                        </div>
                        <div className="text-sm text-muted-foreground mt-1">
                          {queue.workerCount} worker{queue.workerCount !== 1 ? 's' : ''}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Download Clients */}
              <section>
                <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                  <Download className="w-5 h-5" />
                  Download Clients
                </h2>
                {systemStatus.downloadClients.length === 0 ? (
                  <div className="text-center py-8 bg-card border border-border rounded-lg text-muted-foreground">
                    No download clients configured
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {systemStatus.downloadClients.map((client) => (
                      <DownloadClientCard key={client.id} client={client} />
                    ))}
                  </div>
                )}
              </section>

              {/* External APIs */}
              <section>
                <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                  <Globe className="w-5 h-5" />
                  External APIs
                </h2>
                {Object.keys(systemStatus.externalApis).length === 0 ? (
                  <div className="text-center py-8 bg-card border border-border rounded-lg text-muted-foreground">
                    No external APIs configured
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {Object.entries(systemStatus.externalApis).map(([key, api]) => (
                      <ExternalApiCard key={key} name={key} api={api} />
                    ))}
                  </div>
                )}
              </section>

              {/* Celery Tasks */}
              <section>
                <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                  <Clock className="w-5 h-5" />
                  Scheduled Tasks
                </h2>
                <CeleryTasksTable tasks={systemStatus.celeryTasks} />
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
