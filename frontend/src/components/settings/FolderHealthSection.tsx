'use client';

import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import PageHeader from '@/components/PageHeader';
import {
  getRootFolders,
  getHealthSummary,
  getDriveStats,
} from '@/lib/api/root-folders';
import type { DriveStats } from '@/types/root-folder';
import {
  HardDrive,
  CheckCircle,
  AlertTriangle,
  AlertCircle,
  RefreshCw,
  FolderOpen,
  Activity,
  Server,
} from 'lucide-react';
import Link from 'next/link';

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return 'Unknown';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

function getHealthStatusColor(status: string): string {
  switch (status) {
    case 'healthy':
      return 'text-green-500';
    case 'warning':
      return 'text-yellow-500';
    case 'error':
      return 'text-red-500';
    default:
      return 'text-gray-400';
  }
}

function getHealthStatusBg(status: string): string {
  switch (status) {
    case 'healthy':
      return 'bg-green-500/10 border-green-500/20';
    case 'warning':
      return 'bg-yellow-500/10 border-yellow-500/20';
    case 'error':
      return 'bg-red-500/10 border-red-500/20';
    default:
      return 'bg-gray-500/10 border-gray-500/20';
  }
}

function getUsageColor(percent: number): string {
  if (percent >= 90) return 'bg-red-500';
  if (percent >= 75) return 'bg-yellow-500';
  return 'bg-green-500';
}

function getUsageTextColor(percent: number): string {
  if (percent >= 90) return 'text-red-500';
  if (percent >= 75) return 'text-yellow-500';
  return 'text-green-500';
}

const mediaTypeColors: Record<string, string> = {
  movies: 'bg-blue-500',
  shows: 'bg-purple-500',
  anime: 'bg-pink-500',
  music: 'bg-green-500',
};

const mediaTypeLabels: Record<string, string> = {
  movies: 'Movies',
  shows: 'TV Shows',
  anime: 'Anime',
  music: 'Music',
};

export default function FolderHealthSection() {
  const queryClient = useQueryClient();
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  // Queries
  const { data: healthSummary, isLoading: summaryLoading } = useQuery({
    queryKey: ['health-summary'],
    queryFn: getHealthSummary,
    refetchInterval: autoRefresh ? 60000 : false,
  });

  const { data: driveStats = [], isLoading: drivesLoading } = useQuery({
    queryKey: ['drive-stats'],
    queryFn: getDriveStats,
    refetchInterval: autoRefresh ? 60000 : false,
  });

  const { data: allFolders = [], isLoading: foldersLoading } = useQuery({
    queryKey: ['root-folders-all'],
    queryFn: () => getRootFolders(),
    refetchInterval: autoRefresh ? 60000 : false,
  });

  // Auto-refresh effect
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        queryClient.invalidateQueries({ queryKey: ['health-summary'] });
        queryClient.invalidateQueries({ queryKey: ['drive-stats'] });
        queryClient.invalidateQueries({ queryKey: ['root-folders-all'] });
        setLastRefresh(new Date());
      }, 60000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, queryClient]);

  const handleManualRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['health-summary'] });
    queryClient.invalidateQueries({ queryKey: ['drive-stats'] });
    queryClient.invalidateQueries({ queryKey: ['root-folders-all'] });
    setLastRefresh(new Date());
  };

  const isLoading = summaryLoading || drivesLoading || foldersLoading;

  return (
    <div>
      <PageHeader
        title="System Health"
        description="Monitor storage health, disk space, and folder status"
        gradientFrom="emerald-600/10"
        gradientVia="teal-600/10"
        gradientTo="cyan-600/10"
      />

      <div className="p-8">
        <div className="max-w-7xl mx-auto">
          {/* Controls */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-4">
              <button
                onClick={handleManualRefresh}
                disabled={isLoading}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 transition cursor-pointer"
              >
                <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
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
                <Activity className={`w-4 h-4 ${autoRefresh ? 'animate-pulse' : ''}`} />
                Auto-refresh {autoRefresh ? 'On' : 'Off'}
              </button>
            </div>
            <div className="text-sm text-muted-foreground">
              Last updated: {lastRefresh.toLocaleTimeString()}
            </div>
          </div>

          {/* Overview Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <FolderOpen className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <div className="text-2xl font-bold">{healthSummary?.totalFolders ?? '-'}</div>
                  <div className="text-sm text-muted-foreground">Total Folders</div>
                </div>
              </div>
            </div>

            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-500/10 rounded-lg">
                  <CheckCircle className="w-6 h-6 text-green-500" />
                </div>
                <div>
                  <div className="text-2xl font-bold text-green-500">
                    {healthSummary?.healthyCount ?? '-'}
                  </div>
                  <div className="text-sm text-muted-foreground">Healthy</div>
                </div>
              </div>
            </div>

            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-yellow-500/10 rounded-lg">
                  <AlertTriangle className="w-6 h-6 text-yellow-500" />
                </div>
                <div>
                  <div className="text-2xl font-bold text-yellow-500">
                    {healthSummary?.warningCount ?? '-'}
                  </div>
                  <div className="text-sm text-muted-foreground">Warnings</div>
                </div>
              </div>
            </div>

            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-red-500/10 rounded-lg">
                  <AlertCircle className="w-6 h-6 text-red-500" />
                </div>
                <div>
                  <div className="text-2xl font-bold text-red-500">
                    {healthSummary?.errorCount ?? '-'}
                  </div>
                  <div className="text-sm text-muted-foreground">Errors</div>
                </div>
              </div>
            </div>

            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gray-500/10 rounded-lg">
                  <Activity className="w-6 h-6 text-gray-500" />
                </div>
                <div>
                  <div className="text-2xl font-bold text-gray-500">
                    {healthSummary?.unknownCount ?? '-'}
                  </div>
                  <div className="text-sm text-muted-foreground">Unknown</div>
                </div>
              </div>
            </div>
          </div>

          {/* Drive Statistics */}
          <div className="mb-8">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Server className="w-5 h-5" />
              Drive Statistics
            </h2>
            {drivesLoading ? (
              <div className="text-center py-8 text-muted-foreground">Loading drive stats...</div>
            ) : driveStats.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">No drive data available</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {driveStats.map((drive) => (
                  <div key={drive.drive} className="bg-card border border-border rounded-lg p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <HardDrive className="w-8 h-8 text-muted-foreground" />
                      <div>
                        <div className="font-bold text-lg">{drive.drive}</div>
                        <div className="text-sm text-muted-foreground">
                          {drive.folderCount} folder{drive.folderCount !== 1 ? 's' : ''}
                        </div>
                      </div>
                    </div>

                    {/* Usage Bar */}
                    <div className="mb-3">
                      <div className="flex justify-between text-sm mb-1">
                        <span className={getUsageTextColor(drive.usedPercent)}>
                          {drive.usedPercent.toFixed(1)}% used
                        </span>
                        <span className="text-muted-foreground">
                          {formatBytes(drive.freeBytes)} free
                        </span>
                      </div>
                      <div className="h-3 bg-muted rounded-full overflow-hidden">
                        <div
                          className={`h-full ${getUsageColor(drive.usedPercent)} transition-all`}
                          style={{ width: `${drive.usedPercent}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-xs text-muted-foreground mt-1">
                        <span>{formatBytes(drive.usedBytes)} used</span>
                        <span>{formatBytes(drive.totalBytes)} total</span>
                      </div>
                    </div>

                    {/* Folders on this drive */}
                    {drive.folders.length > 0 && (
                      <div className="border-t border-border pt-3 mt-3">
                        <div className="text-xs text-muted-foreground mb-2">Folders:</div>
                        <div className="space-y-1">
                          {drive.folders.slice(0, 5).map((folder) => (
                            <div key={folder.id} className="flex items-center gap-2 text-sm">
                              <span
                                className={`w-2 h-2 rounded-full ${
                                  mediaTypeColors[folder.mediaType] || 'bg-gray-500'
                                }`}
                              />
                              <span className="truncate flex-1">{folder.name}</span>
                              <span className={getHealthStatusColor(folder.healthStatus)}>
                                {folder.healthStatus === 'healthy' && <CheckCircle className="w-3 h-3" />}
                                {folder.healthStatus === 'warning' && <AlertTriangle className="w-3 h-3" />}
                                {folder.healthStatus === 'error' && <AlertCircle className="w-3 h-3" />}
                              </span>
                            </div>
                          ))}
                          {drive.folders.length > 5 && (
                            <div className="text-xs text-muted-foreground">
                              +{drive.folders.length - 5} more
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Folder Health Table */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <FolderOpen className="w-5 h-5" />
                All Folders
              </h2>
            </div>

            {foldersLoading ? (
              <div className="text-center py-8 text-muted-foreground">Loading folders...</div>
            ) : allFolders.length === 0 ? (
              <div className="text-center py-12 bg-card border border-border rounded-lg">
                <FolderOpen className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground mb-4">No folders configured</p>
              </div>
            ) : (
              <div className="bg-card border border-border rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-muted">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
                        Name
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
                        Type
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
                        Path
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
                        Status
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
                        Free Space
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
                        Usage
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
                        Last Check
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {allFolders.map((folder) => (
                      <tr
                        key={folder.id}
                        className={`hover:bg-muted/30 ${getHealthStatusBg(folder.healthStatus)}`}
                      >
                        <td className="px-4 py-3 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{folder.name}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span
                            className={`px-2 py-1 rounded text-xs text-white ${
                              mediaTypeColors[folder.mediaType] || 'bg-gray-500'
                            }`}
                          >
                            {mediaTypeLabels[folder.mediaType] || folder.mediaType}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <code className="text-xs bg-muted px-2 py-1 rounded max-w-xs truncate block">
                            {folder.rootPath}
                          </code>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <span className={getHealthStatusColor(folder.healthStatus)}>
                              {folder.healthStatus === 'healthy' && <CheckCircle className="w-4 h-4" />}
                              {folder.healthStatus === 'warning' && <AlertTriangle className="w-4 h-4" />}
                              {folder.healthStatus === 'error' && <AlertCircle className="w-4 h-4" />}
                              {folder.healthStatus === 'unknown' && <Activity className="w-4 h-4" />}
                            </span>
                            <span className="text-sm capitalize">{folder.healthStatus}</span>
                          </div>
                          {folder.healthMessage && folder.healthStatus !== 'healthy' && (
                            <div className="text-xs text-muted-foreground mt-1 max-w-xs truncate">
                              {folder.healthMessage}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className={getUsageTextColor(folder.usedPercent || 0)}>
                            {formatBytes(folder.freeSpaceBytes)}
                          </span>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-2 bg-muted rounded-full overflow-hidden">
                              <div
                                className={`h-full ${getUsageColor(folder.usedPercent || 0)}`}
                                style={{ width: `${folder.usedPercent || 0}%` }}
                              />
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {folder.usedPercent?.toFixed(0) || 0}%
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-muted-foreground">
                          {folder.lastHealthCheck
                            ? new Date(folder.lastHealthCheck).toLocaleString()
                            : 'Never'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
