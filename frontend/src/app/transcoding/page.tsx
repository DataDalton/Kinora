'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  Trash2,
  Plus,
  Settings,
  Cpu,
  Clock,
  FileVideo,
  CheckCircle,
  XCircle,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Edit,
} from 'lucide-react';
import PageHeader from '@/components/PageHeader';

interface HardwareDevice {
  id: number;
  deviceType: string;
  deviceIndex: number;
  deviceName: string;
  deviceUuid?: string;
  memoryTotal?: number;
  isAvailable: boolean;
}

interface TranscodingProfile {
  id: number;
  name: string;
  description?: string;
  container: string;
  videoCodec: string;
  videoQualityMode: string;
  videoQualityValue: number;
  videoPreset?: string;
  audioCodec: string;
  audioBitrate?: number;
  resolution: string;
  hardwareAccelType?: string;
  hardwareAccelDevice?: number;
  isSystem: boolean;
}

interface TranscodingJob {
  id: number;
  userId: number;
  mediaTitle?: string;
  inputPath: string;
  outputPath?: string;
  outputAction: string;
  status: string;
  progress: number;
  currentFrame?: number;
  totalFrames?: number;
  fps?: number;
  speed?: string;
  bitrate?: string;
  fileSizeInput?: number;
  fileSizeOutput?: number;
  errorMessage?: string;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  profileId?: number;
  hardwareAccelType?: string;
  hardwareAccelDevice?: number;
}

interface TranscodingRule {
  id: number;
  name: string;
  enabled: boolean;
  priority: number;
  triggerType: string;
  conditions: any;
  profileId: number;
  outputAction: string;
  useMediaProfileNaming: boolean;
  mediaTypes: string[];
}

export default function TranscodingPage() {
  const [selectedTab, setSelectedTab] = useState<'jobs' | 'profiles' | 'rules'>('jobs');
  const [showJobModal, setShowJobModal] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showRuleModal, setShowRuleModal] = useState(false);
  const [editingProfile, setEditingProfile] = useState<TranscodingProfile | null>(null);
  const [editingRule, setEditingRule] = useState<TranscodingRule | null>(null);
  const [expandedJobs, setExpandedJobs] = useState<Set<number>>(new Set());
  const [deleteConfirm, setDeleteConfirm] = useState<{
    type: 'profile' | 'rule';
    id: number;
    name: string;
  } | null>(null);

  const queryClient = useQueryClient();

  // Fetch hardware devices
  const { data: hardwareDevices } = useQuery<HardwareDevice[]>({
    queryKey: ['hardware-devices'],
    queryFn: async () => {
      const response = await api.get('/transcoding/hardware');
      return response.data;
    },
  });

  // Fetch transcoding jobs. Polls fast only while a job is queued or processing,
  // otherwise drops to a slow idle poll.
  const { data: jobs, isLoading: jobsLoading } = useQuery<TranscodingJob[]>({
    queryKey: ['transcoding-jobs'],
    queryFn: async () => {
      const response = await api.get('/transcoding/jobs');
      return response.data;
    },
    refetchInterval: (query) => {
      const currentJobs = query.state.data;
      const hasActiveJobs = Array.isArray(currentJobs)
        && currentJobs.some((job) => job.status === 'queued' || job.status === 'processing');
      return hasActiveJobs ? 2000 : 30000;
    },
  });

  // Fetch transcoding profiles
  const { data: profiles, isLoading: profilesLoading } = useQuery<TranscodingProfile[]>({
    queryKey: ['transcoding-profiles'],
    queryFn: async () => {
      const response = await api.get('/transcoding/profiles');
      return response.data;
    },
  });

  // Fetch transcoding rules
  const { data: rules, isLoading: rulesLoading } = useQuery<TranscodingRule[]>({
    queryKey: ['transcoding-rules'],
    queryFn: async () => {
      const response = await api.get('/transcoding/rules');
      return response.data;
    },
  });

  // Cancel job mutation
  const cancelJobMutation = useMutation({
    mutationFn: async (jobId: number) => {
      await api.delete(`/transcoding/jobs/${jobId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transcoding-jobs'] });
    },
  });

  // Delete profile mutation
  const deleteProfileMutation = useMutation({
    mutationFn: async (profileId: number) => {
      await api.delete(`/transcoding/profiles/${profileId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transcoding-profiles'] });
    },
  });

  // Delete rule mutation
  const deleteRuleMutation = useMutation({
    mutationFn: async (ruleId: number) => {
      await api.delete(`/transcoding/rules/${ruleId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transcoding-rules'] });
    },
  });

  // Toggle rule enabled
  const toggleRuleMutation = useMutation({
    mutationFn: async ({ ruleId, enabled }: { ruleId: number; enabled: boolean }) => {
      await api.put(`/transcoding/rules/${ruleId}`, { enabled });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transcoding-rules'] });
    },
  });

  // Detect hardware
  const detectHardwareMutation = useMutation({
    mutationFn: async () => {
      await api.post('/transcoding/hardware/detect');
    },
    onSuccess: () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['hardware-devices'] });
      }, 2000);
    },
  });

  // Auto-detect hardware on page load
  useEffect(() => {
    detectHardwareMutation.mutate();
  }, []);

  const toggleJobExpansion = (jobId: number) => {
    setExpandedJobs((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(jobId)) {
        newSet.delete(jobId);
      } else {
        newSet.add(jobId);
      }
      return newSet;
    });
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'N/A';
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 1) return `${gb.toFixed(2)} GB`;
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(2)} MB`;
  };

  const formatDuration = (start?: string, end?: string) => {
    if (!start) return 'N/A';
    const startTime = new Date(start);
    const endTime = end ? new Date(end) : new Date();
    const diff = endTime.getTime() - startTime.getTime();
    const minutes = Math.floor(diff / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);
    return `${minutes}m ${seconds}s`;
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'processing':
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'queued':
        return <Clock className="w-5 h-5 text-yellow-500" />;
      case 'cancelled':
        return <XCircle className="w-5 h-5 text-gray-500" />;
      default:
        return <AlertCircle className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'failed':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      case 'processing':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'queued':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
      case 'cancelled':
        return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200';
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200';
    }
  };

  return (
    <div className="min-h-screen">
      <PageHeader
        title="Media Transcoding"
        description="Manage video transcoding jobs, profiles, and automatic rules"
        gradientFrom="orange-600/10"
        gradientVia="amber-600/10"
        gradientTo="yellow-600/10"
      />

      <div className="container mx-auto p-6 max-w-7xl">

      {/* Tabs */}
      <div className="flex space-x-1 mb-6 border-b border-border">
        <button
          className={`px-6 py-3 font-medium transition-all cursor-pointer ${
            selectedTab === 'jobs'
              ? 'border-b-2 border-primary text-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setSelectedTab('jobs')}
        >
          Jobs Queue
        </button>
        <button
          className={`px-6 py-3 font-medium transition-all cursor-pointer ${
            selectedTab === 'profiles'
              ? 'border-b-2 border-primary text-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setSelectedTab('profiles')}
        >
          Profiles
        </button>
        <button
          className={`px-6 py-3 font-medium transition-all cursor-pointer ${
            selectedTab === 'rules'
              ? 'border-b-2 border-primary text-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setSelectedTab('rules')}
        >
          Automatic Rules
        </button>
      </div>

      {/* Jobs Tab */}
      {selectedTab === 'jobs' && (
        <div>
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-2">
              <FileVideo className="w-5 h-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                {jobs?.length || 0} total jobs
              </span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => detectHardwareMutation.mutate()}
                disabled={detectHardwareMutation.isPending}
                className="px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition flex items-center gap-2 cursor-pointer disabled:cursor-not-allowed"
              >
                {detectHardwareMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Cpu className="w-4 h-4" />
                )}
                Detect Hardware
              </button>
              <button
                onClick={() => setShowJobModal(true)}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition flex items-center gap-2 cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                New Transcoding Job
              </button>
            </div>
          </div>

          {/* Hardware Info */}
          {hardwareDevices && hardwareDevices.length > 0 && (
            <div className="mb-4 p-4 bg-accent/50 rounded-lg border border-border">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Cpu className="w-4 h-4" />
                Available Hardware Acceleration
              </h3>

              {/* CPU Section */}
              {hardwareDevices.some(d => d.deviceType === 'cpu') && (
                <div className="mb-3">
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">CPUs</h4>
                  <ul className="space-y-1">
                    {hardwareDevices
                      .filter(d => d.deviceType === 'cpu')
                      .map((device) => (
                        <li key={device.id} className="text-sm flex items-center gap-2 pl-2">
                          <span className="text-green-500">●</span>
                          <span>{device.deviceName || 'CPU (Software Encoding)'}</span>
                        </li>
                      ))}
                  </ul>
                </div>
              )}

              {/* GPUs Section */}
              {hardwareDevices.some(d => d.deviceType !== 'cpu') && (
                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">GPUs</h4>
                  <ul className="space-y-1">
                    {hardwareDevices
                      .filter(d => d.deviceType !== 'cpu')
                      .map((device) => (
                        <li key={device.id} className="text-sm flex items-center gap-2 pl-2">
                          <span className="text-green-500">●</span>
                          <span className="font-medium">GPU {device.deviceIndex}:</span>
                          <span>{device.deviceName}</span>
                          {device.memoryTotal && (
                            <span className="text-muted-foreground text-xs">
                              ({Math.round(device.memoryTotal / (1024 * 1024 * 1024))}GB)
                            </span>
                          )}
                        </li>
                      ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Jobs List */}
          {jobsLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          ) : jobs && jobs.length > 0 ? (
            <div className="space-y-4">
              {jobs.map((job) => (
                <div
                  key={job.id}
                  className="border border-border rounded-lg bg-card overflow-hidden"
                >
                  <div className="p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          {getStatusIcon(job.status)}
                          <h3 className="font-semibold">
                            {job.mediaTitle || 'Untitled'}
                          </h3>
                          <span
                            className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(
                              job.status
                            )}`}
                          >
                            {job.status}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground truncate">
                          {job.inputPath}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => toggleJobExpansion(job.id)}
                          className="p-2 hover:bg-accent rounded transition cursor-pointer"
                          title="Show details"
                        >
                          {expandedJobs.has(job.id) ? (
                            <ChevronUp className="w-4 h-4" />
                          ) : (
                            <ChevronDown className="w-4 h-4" />
                          )}
                        </button>
                        {['pending', 'queued', 'processing'].includes(job.status) && (
                          <button
                            onClick={() => cancelJobMutation.mutate(job.id)}
                            disabled={cancelJobMutation.isPending}
                            className="p-2 hover:bg-destructive/10 text-destructive rounded transition cursor-pointer"
                            title="Cancel job"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Progress Bar */}
                    {job.status === 'processing' && (
                      <div className="mt-3">
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-muted-foreground">
                            {job.progress?.toFixed(1)}%
                          </span>
                          <span className="text-muted-foreground">
                            {job.fps?.toFixed(1)} fps | {job.speed || 'N/A'}
                          </span>
                        </div>
                        <div className="w-full bg-secondary rounded-full h-2 overflow-hidden">
                          <div
                            className="bg-primary h-2 rounded-full transition-all duration-300"
                            style={{ width: `${job.progress || 0}%` }}
                          />
                        </div>
                        {job.currentFrame && job.totalFrames && (
                          <div className="text-xs text-muted-foreground mt-1">
                            Frame {job.currentFrame.toLocaleString()} /{' '}
                            {job.totalFrames.toLocaleString()}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Expanded Details */}
                    {expandedJobs.has(job.id) && (
                      <div className="mt-4 pt-4 border-t border-border space-y-2 text-sm">
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <span className="text-muted-foreground">Output Action:</span>
                            <span className="ml-2 font-medium">{job.outputAction}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">File Size:</span>
                            <span className="ml-2 font-medium">
                              {formatFileSize(job.fileSizeInput)}
                              {job.fileSizeOutput && (
                                <> → {formatFileSize(job.fileSizeOutput)}</>
                              )}
                            </span>
                          </div>
                          {job.hardwareAccelType && (
                            <div>
                              <span className="text-muted-foreground">Hardware:</span>
                              <span className="ml-2 font-medium">
                                {job.hardwareAccelType?.toUpperCase() || 'UNKNOWN'}
                                {job.hardwareAccelDevice !== null &&
                                  ` [${job.hardwareAccelDevice}]`}
                              </span>
                            </div>
                          )}
                          <div>
                            <span className="text-muted-foreground">Duration:</span>
                            <span className="ml-2 font-medium">
                              {formatDuration(job.startedAt, job.completedAt)}
                            </span>
                          </div>
                        </div>
                        {job.outputPath && (
                          <div>
                            <span className="text-muted-foreground">Output Path:</span>
                            <p className="text-xs mt-1 break-all">{job.outputPath}</p>
                          </div>
                        )}
                        {job.errorMessage && (
                          <div className="p-2 bg-destructive/10 text-destructive rounded text-xs">
                            <strong>Error:</strong> {job.errorMessage}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <FileVideo className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No transcoding jobs yet</h3>
              <p className="text-muted-foreground mb-4">
                Create a new transcoding job to get started
              </p>
              <button
                onClick={() => setShowJobModal(true)}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition cursor-pointer"
              >
                Create First Job
              </button>
            </div>
          )}
        </div>
      )}

      {/* Profiles Tab */}
      {selectedTab === 'profiles' && (
        <div>
          <div className="flex justify-between items-center mb-4">
            <span className="text-sm text-muted-foreground">
              {profiles?.length || 0} profiles
            </span>
            <button
              onClick={() => {
                setEditingProfile(null);
                setShowProfileModal(true);
              }}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              New Profile
            </button>
          </div>

          {profilesLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          ) : profiles && profiles.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {profiles.map((profile) => (
                <div
                  key={profile.id}
                  className="border border-border rounded-lg p-4 bg-card hover:border-primary/50 transition"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h3 className="font-semibold">{profile.name}</h3>
                      {profile.description && (
                        <p className="text-xs text-muted-foreground mt-1">
                          {profile.description}
                        </p>
                      )}
                    </div>
                    {profile.isSystem && (
                      <span className="px-2 py-1 bg-secondary text-secondary-foreground text-xs rounded">
                        System
                      </span>
                    )}
                  </div>

                  <div className="space-y-1 text-sm mt-3">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Codec:</span>
                      <span className="font-medium">{profile.videoCodec}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Quality:</span>
                      <span className="font-medium">
                        {profile.videoQualityMode} {profile.videoQualityValue}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Container:</span>
                      <span className="font-medium">{profile.container}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Resolution:</span>
                      <span className="font-medium">{profile.resolution}</span>
                    </div>
                    {profile.hardwareAccelType && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Hardware:</span>
                        <span className="font-medium">
                          {profile.hardwareAccelType?.toUpperCase() || 'UNKNOWN'}
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2 mt-4">
                    <button
                      onClick={() => {
                        setEditingProfile(profile);
                        setShowProfileModal(true);
                      }}
                      className="flex-1 px-3 py-2 bg-secondary text-secondary-foreground rounded hover:bg-secondary/80 transition text-sm flex items-center justify-center gap-2"
                    >
                      <Edit className="w-3 h-3" />
                      Edit
                    </button>
                    {!profile.isSystem && (
                      <button
                        onClick={() => {
                          setDeleteConfirm({
                            type: 'profile',
                            id: profile.id,
                            name: profile.name,
                          });
                        }}
                        disabled={deleteProfileMutation.isPending}
                        className="px-3 py-2 bg-destructive/10 text-destructive rounded hover:bg-destructive/20 transition text-sm cursor-pointer"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <Settings className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No profiles yet</h3>
              <p className="text-muted-foreground mb-4">
                Create a transcoding profile to get started
              </p>
              <button
                onClick={() => setShowProfileModal(true)}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition cursor-pointer"
              >
                Create First Profile
              </button>
            </div>
          )}
        </div>
      )}

      {/* Rules Tab */}
      {selectedTab === 'rules' && (
        <div>
          <div className="flex justify-between items-center mb-4">
            <span className="text-sm text-muted-foreground">
              {rules?.length || 0} rules
            </span>
            <button
              onClick={() => {
                setEditingRule(null);
                setShowRuleModal(true);
              }}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              New Rule
            </button>
          </div>

          {rulesLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          ) : rules && rules.length > 0 ? (
            <div className="space-y-3">
              {rules.map((rule) => (
                <div
                  key={rule.id}
                  className={`border border-border rounded-lg p-4 bg-card ${
                    rule.enabled ? '' : 'opacity-60'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold">{rule.name}</h3>
                        <span className="px-2 py-1 bg-secondary text-secondary-foreground text-xs rounded">
                          Priority {rule.priority}
                        </span>
                        <span className="px-2 py-1 bg-accent text-accent-foreground text-xs rounded">
                          {rule.triggerType}
                        </span>
                      </div>
                      <div className="text-sm text-muted-foreground space-y-1">
                        <div>
                          <strong>Media Types:</strong> {rule.mediaTypes.join(', ')}
                        </div>
                        <div>
                          <strong>Output:</strong> {rule.outputAction}
                          {rule.useMediaProfileNaming && ' (use profile naming)'}
                        </div>
                        {rule.conditions && Object.keys(rule.conditions).length > 0 && (
                          <div>
                            <strong>Conditions:</strong>{' '}
                            {JSON.stringify(rule.conditions)}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() =>
                          toggleRuleMutation.mutate({
                            ruleId: rule.id,
                            enabled: !rule.enabled,
                          })
                        }
                        disabled={toggleRuleMutation.isPending}
                        className={`px-3 py-1 rounded text-sm font-medium transition ${
                          rule.enabled
                            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 hover:bg-green-200'
                            : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200 hover:bg-gray-200'
                        }`}
                      >
                        {rule.enabled ? 'Enabled' : 'Disabled'}
                      </button>
                      <button
                        onClick={() => {
                          setEditingRule(rule);
                          setShowRuleModal(true);
                        }}
                        className="p-2 hover:bg-accent rounded transition cursor-pointer"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => {
                          setDeleteConfirm({
                            type: 'rule',
                            id: rule.id,
                            name: rule.name,
                          });
                        }}
                        disabled={deleteRuleMutation.isPending}
                        className="p-2 hover:bg-destructive/10 text-destructive rounded transition cursor-pointer"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <AlertCircle className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No rules yet</h3>
              <p className="text-muted-foreground mb-4">
                Create automatic transcoding rules to process media on download
              </p>
              <button
                onClick={() => setShowRuleModal(true)}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition cursor-pointer"
              >
                Create First Rule
              </button>
            </div>
          )}
        </div>
      )}

      {/* Modals will be added in separate components */}
      {showJobModal && (
        <JobCreationModal
          onClose={() => setShowJobModal(false)}
          profiles={profiles || []}
          hardwareDevices={hardwareDevices || []}
          onSuccess={() => {
            setShowJobModal(false);
            queryClient.invalidateQueries({ queryKey: ['transcoding-jobs'] });
          }}
        />
      )}

      {showProfileModal && (
        <ProfileModal
          onClose={() => {
            setShowProfileModal(false);
            setEditingProfile(null);
          }}
          profile={editingProfile}
          onSuccess={() => {
            setShowProfileModal(false);
            setEditingProfile(null);
            queryClient.invalidateQueries({ queryKey: ['transcoding-profiles'] });
          }}
        />
      )}

      {showRuleModal && (
        <RuleModal
          onClose={() => {
            setShowRuleModal(false);
            setEditingRule(null);
          }}
          rule={editingRule}
          profiles={profiles || []}
          onSuccess={() => {
            setShowRuleModal(false);
            setEditingRule(null);
            queryClient.invalidateQueries({ queryKey: ['transcoding-rules'] });
          }}
        />
      )}

      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-card rounded-lg max-w-md w-full border border-border">
            <div className="p-6">
              <h2 className="text-xl font-bold mb-2">Confirm Deletion</h2>
              <p className="text-muted-foreground mb-6">
                Are you sure you want to delete "{deleteConfirm.name}"? This action cannot be undone.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => setDeleteConfirm(null)}
                  className="flex-1 px-4 py-2 border border-border rounded-lg hover:bg-accent transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    if (deleteConfirm.type === 'profile') {
                      deleteProfileMutation.mutate(deleteConfirm.id);
                    } else {
                      deleteRuleMutation.mutate(deleteConfirm.id);
                    }
                    setDeleteConfirm(null);
                  }}
                  className="flex-1 px-4 py-2 bg-destructive text-destructive-foreground rounded-lg hover:bg-destructive/90 transition cursor-pointer"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}

// Job Creation Modal Component
function JobCreationModal({
  onClose,
  profiles,
  hardwareDevices,
  onSuccess,
}: {
  onClose: () => void;
  profiles: TranscodingProfile[];
  hardwareDevices: HardwareDevice[];
  onSuccess: () => void;
}) {
  const [inputPath, setInputPath] = useState('');
  const [profileId, setProfileId] = useState<number | ''>('');
  const [outputAction, setOutputAction] = useState('replace');
  const [hardwareAccelType, setHardwareAccelType] = useState<string>('');
  const [hardwareAccelDevice, setHardwareAccelDevice] = useState<number | ''>('');

  const createJobMutation = useMutation({
    mutationFn: async (data: any) => {
      await api.post('/transcoding/jobs', data);
    },
    onSuccess,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputPath || !profileId) return;

    createJobMutation.mutate({
      inputPath,
      profileId,
      outputAction,
      hardwareAccelType: hardwareAccelType || null,
      hardwareAccelDevice:
        hardwareAccelDevice !== '' ? hardwareAccelDevice : null,
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto border border-border">
        <div className="p-6 border-b border-border">
          <h2 className="text-2xl font-bold">Create Transcoding Job</h2>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Input File Path <span className="text-destructive">*</span>
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={inputPath}
                onChange={(e) => setInputPath(e.target.value)}
                placeholder="/media/movies/Movie.mkv"
                className="flex-1 px-3 py-2 border border-border rounded-lg bg-background"
                required
              />
              <button
                type="button"
                onClick={() => {
                  const input = document.createElement('input');
                  input.type = 'file';
                  input.accept = 'video/*,audio/*,.mkv,.mp4,.avi,.mov,.wmv,.flv,.webm,.m4v';
                  input.onchange = (e) => {
                    const file = (e.target as HTMLInputElement).files?.[0];
                    if (file) {
                      // In Electron/desktop apps, file.path exists. In browsers, use webkitRelativePath or name
                      const filePath = (file as any).path || file.webkitRelativePath || file.name;
                      setInputPath(filePath);
                    }
                  };
                  input.click();
                }}
                className="px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition cursor-pointer whitespace-nowrap"
              >
                Browse...
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Transcoding Profile <span className="text-destructive">*</span>
            </label>
            <select
              value={profileId}
              onChange={(e) => setProfileId(Number(e.target.value))}
              className="w-full px-3 py-2 border border-border rounded-lg bg-background"
              required
            >
              <option value="">Select a profile</option>
              {profiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name} ({profile.videoCodec} - {profile.resolution})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Output Action</label>
            <select
              value={outputAction}
              onChange={(e) => setOutputAction(e.target.value)}
              className="w-full px-3 py-2 border border-border rounded-lg bg-background"
            >
              <option value="replace">Replace original file</option>
              <option value="new_file">Create new file</option>
            </select>
            <p className="text-xs text-muted-foreground mt-1">
              {outputAction === 'replace'
                ? 'The transcoded file will replace the original'
                : 'A new file will be created alongside the original'}
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Hardware Device
            </label>
            <select
              value={hardwareAccelDevice !== '' ? `${hardwareAccelType}-${hardwareAccelDevice}` : ''}
              onChange={(e) => {
                if (!e.target.value) {
                  setHardwareAccelType('');
                  setHardwareAccelDevice('');
                } else {
                  const [type, index] = e.target.value.split('-');
                  setHardwareAccelType(type);
                  setHardwareAccelDevice(Number(index));
                }
              }}
              className="w-full px-3 py-2 border border-border rounded-lg bg-background"
            >
              <option value="">Select device</option>

              {/* CPU Devices */}
              {hardwareDevices.filter(d => d.deviceType === 'cpu').length > 0 && (
                <optgroup label="CPUs">
                  {hardwareDevices
                    .filter(d => d.deviceType === 'cpu')
                    .map((device) => (
                      <option key={device.id} value={`${device.deviceType}-${device.deviceIndex}`}>
                        {device.deviceName}
                      </option>
                    ))}
                </optgroup>
              )}

              {/* GPU Devices */}
              {hardwareDevices.filter(d => d.deviceType !== 'cpu').length > 0 && (
                <optgroup label="GPUs">
                  {hardwareDevices
                    .filter(d => d.deviceType !== 'cpu')
                    .map((device) => (
                      <option key={device.id} value={`${device.deviceType}-${device.deviceIndex}`}>
                        GPU {device.deviceIndex}: {device.deviceName}
                        {device.memoryTotal ? ` (${Math.round(device.memoryTotal / (1024 * 1024 * 1024))}GB)` : ''}
                      </option>
                    ))}
                </optgroup>
              )}
            </select>
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-border rounded-lg hover:bg-accent transition cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createJobMutation.isPending}
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
            >
              {createJobMutation.isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Creating...
                </span>
              ) : (
                'Create Job'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Profile Modal - Simplified (full implementation would be larger)
function ProfileModal({
  onClose,
  profile,
  onSuccess,
}: {
  onClose: () => void;
  profile: TranscodingProfile | null;
  onSuccess: () => void;
}) {
  const [formData, setFormData] = useState({
    name: profile?.name || '',
    description: profile?.description || '',
    container: profile?.container || 'mkv',
    videoCodec: profile?.videoCodec || 'libx265',
    videoQualityMode: profile?.videoQualityMode || 'crf',
    videoQualityValue: profile?.videoQualityValue?.toString() || '23',
    audioCodec: profile?.audioCodec || 'aac',
    resolution: profile?.resolution || 'original',
  });

  const qualityValueNum = formData.videoQualityValue === '' ? NaN : parseInt(formData.videoQualityValue, 10);
  const isQualityValueValid =
    formData.videoQualityValue === '' ||
    formData.videoQualityMode === 'lossless' ||
    (formData.videoQualityMode === 'crf' && !isNaN(qualityValueNum) && qualityValueNum >= 0 && qualityValueNum <= 51) ||
    (formData.videoQualityMode === 'bitrate' && !isNaN(qualityValueNum) && qualityValueNum >= 100 && qualityValueNum <= 100000);

  const createProfileMutation = useMutation({
    mutationFn: async (data: any) => {
      if (profile) {
        await api.put(`/transcoding/profiles/${profile.id}`, data);
      } else {
        await api.post('/transcoding/profiles', data);
      }
    },
    onSuccess,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isQualityValueValid) return;

    createProfileMutation.mutate({
      name: formData.name,
      description: formData.description,
      container: formData.container,
      video_codec: formData.videoCodec,
      video_quality_mode: formData.videoQualityMode,
      video_quality_value: parseInt(formData.videoQualityValue, 10) || 23,
      audio_codec: formData.audioCodec,
      resolution: formData.resolution,
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto border border-border">
        <div className="p-6 border-b border-border">
          <h2 className="text-2xl font-bold">
            {profile ? 'Edit' : 'Create'} Transcoding Profile
          </h2>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Profile Name <span className="text-destructive">*</span>
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="My Transcoding Profile"
              className="w-full px-3 py-2 border border-border rounded-lg bg-background"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              placeholder="Profile description"
              className="w-full px-3 py-2 border border-border rounded-lg bg-background"
              rows={2}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Video Codec</label>
              <select
                value={formData.videoCodec}
                onChange={(e) =>
                  setFormData({ ...formData, videoCodec: e.target.value })
                }
                className="w-full px-3 py-2 border border-border rounded-lg bg-background"
              >
                <option value="libx264">H.264 (libx264)</option>
                <option value="libx265">H.265 (libx265)</option>
                <option value="libaom-av1">AV1</option>
                <option value="libvpx-vp9">VP9</option>
              </select>
              <p className="text-xs text-muted-foreground mt-1">
                H.265 provides better compression than H.264. AV1 is the newest codec with best compression.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Container</label>
              <select
                value={formData.container}
                onChange={(e) =>
                  setFormData({ ...formData, container: e.target.value })
                }
                className="w-full px-3 py-2 border border-border rounded-lg bg-background"
              >
                <option value="mkv">MKV</option>
                <option value="mp4">MP4</option>
                <option value="webm">WebM</option>
              </select>
              <p className="text-xs text-muted-foreground mt-1">
                MKV supports all codecs and features. MP4 is more compatible but limited.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Quality Mode</label>
              <select
                value={formData.videoQualityMode}
                onChange={(e) =>
                  setFormData({ ...formData, videoQualityMode: e.target.value })
                }
                className="w-full px-3 py-2 border border-border rounded-lg bg-background"
              >
                <option value="crf">CRF (Constant Rate Factor)</option>
                <option value="bitrate">Bitrate</option>
                <option value="lossless">Lossless</option>
              </select>
              <p className="text-xs text-muted-foreground mt-1">
                CRF maintains consistent quality (recommended). Bitrate targets specific file size. Lossless preserves original quality.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Quality Value</label>
              <input
                type="number"
                value={formData.videoQualityValue}
                onChange={(e) => {
                  setFormData({
                    ...formData,
                    videoQualityValue: e.target.value,
                  });
                }}
                disabled={formData.videoQualityMode === 'lossless'}
                min={formData.videoQualityMode === 'crf' ? 0 : 100}
                max={formData.videoQualityMode === 'crf' ? 51 : 100000}
                step="1"
                className={`w-full px-3 py-2 border rounded-lg bg-background disabled:opacity-50 disabled:cursor-not-allowed ${
                  !isQualityValueValid && formData.videoQualityValue !== '' && formData.videoQualityMode !== 'lossless'
                    ? 'border-red-500'
                    : 'border-border'
                }`}
              />
              <p className={`text-xs mt-1 ${
                !isQualityValueValid && formData.videoQualityValue !== '' && formData.videoQualityMode !== 'lossless'
                  ? 'text-red-500'
                  : 'text-muted-foreground'
              }`}>
                {!isQualityValueValid && formData.videoQualityValue !== '' && formData.videoQualityMode !== 'lossless'
                  ? formData.videoQualityMode === 'crf'
                    ? 'Value must be between 0-51'
                    : formData.videoQualityMode === 'bitrate'
                    ? 'Value must be between 100-100000'
                    : ''
                  : formData.videoQualityMode === 'crf'
                  ? 'Range: 0-51 (lower = better quality, larger file). 0 = lossless, 18 = high quality, 23 = default balanced, 28 = lower quality, 51 = worst quality'
                  : formData.videoQualityMode === 'bitrate'
                  ? 'Target bitrate in kbps (e.g., 2500 for 1080p medium quality, 5000 for 1080p high quality, 8000+ for 4K)'
                  : 'Not used in lossless mode'}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Audio Codec</label>
              <select
                value={formData.audioCodec}
                onChange={(e) =>
                  setFormData({ ...formData, audioCodec: e.target.value })
                }
                className="w-full px-3 py-2 border border-border rounded-lg bg-background"
              >
                <option value="aac">AAC</option>
                <option value="opus">Opus</option>
                <option value="flac">FLAC</option>
                <option value="copy">Copy (no re-encode)</option>
              </select>
              <p className="text-xs text-muted-foreground mt-1">
                AAC is widely compatible. Opus has best quality/size ratio. FLAC is lossless. Copy keeps original audio.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Resolution</label>
              <select
                value={formData.resolution}
                onChange={(e) =>
                  setFormData({ ...formData, resolution: e.target.value })
                }
                className="w-full px-3 py-2 border border-border rounded-lg bg-background"
              >
                <option value="original">Original</option>
                <option value="2160p">4K (2160p)</option>
                <option value="1080p">1080p</option>
                <option value="720p">720p</option>
                <option value="480p">480p</option>
              </select>
              <p className="text-xs text-muted-foreground mt-1">
                Downscale video to reduce file size. Original keeps source resolution.
              </p>
            </div>
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-border rounded-lg hover:bg-accent transition cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createProfileMutation.isPending || !isQualityValueValid}
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
            >
              {createProfileMutation.isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Saving...
                </span>
              ) : (
                'Save Profile'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Rule Modal - Simplified
function RuleModal({
  onClose,
  rule,
  profiles,
  onSuccess,
}: {
  onClose: () => void;
  rule: TranscodingRule | null;
  profiles: TranscodingProfile[];
  onSuccess: () => void;
}) {
  const [formData, setFormData] = useState({
    name: rule?.name || '',
    enabled: rule?.enabled ?? true,
    priority: rule?.priority || 0,
    triggerType: rule?.triggerType || 'on_download',
    profileId: rule?.profileId || '',
    outputAction: rule?.outputAction || 'replace',
    mediaTypes: rule?.mediaTypes || ['movie', 'show', 'anime'],
  });

  const createRuleMutation = useMutation({
    mutationFn: async (data: any) => {
      if (rule) {
        await api.put(`/transcoding/rules/${rule.id}`, data);
      } else {
        await api.post('/transcoding/rules', {
          ...data,
          conditions: {},
          useMediaProfileNaming: true,
        });
      }
    },
    onSuccess,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createRuleMutation.mutate(formData);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto border border-border">
        <div className="p-6 border-b border-border">
          <h2 className="text-2xl font-bold">
            {rule ? 'Edit' : 'Create'} Transcoding Rule
          </h2>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Rule Name <span className="text-destructive">*</span>
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="Auto transcode large files"
              className="w-full px-3 py-2 border border-border rounded-lg bg-background"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Trigger</label>
              <select
                value={formData.triggerType}
                onChange={(e) =>
                  setFormData({ ...formData, triggerType: e.target.value })
                }
                className="w-full px-3 py-2 border border-border rounded-lg bg-background"
              >
                <option value="on_download">On Download</option>
                <option value="on_import">On Import</option>
                <option value="scheduled">Scheduled</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Priority</label>
              <input
                type="number"
                value={formData.priority}
                onChange={(e) =>
                  setFormData({ ...formData, priority: Number(e.target.value) })
                }
                className="w-full px-3 py-2 border border-border rounded-lg bg-background"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Profile <span className="text-destructive">*</span>
            </label>
            <select
              value={formData.profileId}
              onChange={(e) =>
                setFormData({ ...formData, profileId: Number(e.target.value) })
              }
              className="w-full px-3 py-2 border border-border rounded-lg bg-background"
              required
            >
              <option value="">Select a profile</option>
              {profiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Output Action</label>
            <select
              value={formData.outputAction}
              onChange={(e) =>
                setFormData({ ...formData, outputAction: e.target.value })
              }
              className="w-full px-3 py-2 border border-border rounded-lg bg-background"
            >
              <option value="replace">Replace original</option>
              <option value="new_file">Create new file</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Media Types</label>
            <div className="flex flex-wrap gap-2">
              {['movie', 'show', 'anime'].map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => {
                    if (formData.mediaTypes.includes(type)) {
                      setFormData({
                        ...formData,
                        mediaTypes: formData.mediaTypes.filter((t) => t !== type),
                      });
                    } else {
                      setFormData({
                        ...formData,
                        mediaTypes: [...formData.mediaTypes, type],
                      });
                    }
                  }}
                  className={`px-4 py-2 rounded-full border-2 transition cursor-pointer capitalize ${
                    formData.mediaTypes.includes(type)
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-background border-border hover:border-primary/50'
                  }`}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-border rounded-lg hover:bg-accent transition cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createRuleMutation.isPending}
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
            >
              {createRuleMutation.isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Saving...
                </span>
              ) : (
                'Save Rule'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
