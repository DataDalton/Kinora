'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Clock, Check, X, Film, Tv, Music, Sparkles, MessageSquare, User, Calendar, XCircle } from 'lucide-react';
import { usePermissions } from '@/contexts/PermissionContext';
import { api } from '@/lib/api';
import { getRequests, approveRequest, denyRequest, cancelRequest, getRequestCounts } from '@/lib/api/requests';
import { MediaRequest, MediaRequestCount } from '@/types/request';
import PageHeader from '@/components/PageHeader';
import Toast from '@/components/Toast';

type StatusFilter = 'all' | 'pending' | 'approved' | 'denied';

interface CurrentUser {
  id: number;
  username: string;
}

export default function RequestsPage() {
  const queryClient = useQueryClient();
  const { canApprove, isAdmin } = usePermissions();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [selectedRequest, setSelectedRequest] = useState<MediaRequest | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [reviewNotes, setReviewNotes] = useState('');
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  // Fetch current user for ownership checks
  const { data: currentUser } = useQuery<CurrentUser>({
    queryKey: ['current-user'],
    queryFn: async () => {
      const response = await api.get('/auth/me');
      return response.data;
    },
  });

  // Fetch request counts with polling
  const { data: counts } = useQuery<MediaRequestCount>({
    queryKey: ['request-counts'],
    queryFn: getRequestCounts,
    refetchInterval: 30000,
  });

  // Fetch requests based on filter
  const { data: requests, isLoading } = useQuery<MediaRequest[]>({
    queryKey: ['requests', statusFilter],
    queryFn: () => getRequests(statusFilter === 'all' ? undefined : statusFilter),
    refetchInterval: 30000,
  });

  const showToast = (message: string, type: 'success' | 'error' | 'info') => {
    setToast(null);
    setTimeout(() => {
      setToast({ message, type });
    }, 0);
  };

  // Approve mutation
  const approveMutation = useMutation({
    mutationFn: ({ id, notes }: { id: number; notes?: string }) => approveRequest(id, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requests'] });
      queryClient.invalidateQueries({ queryKey: ['request-counts'] });
      setShowDetailModal(false);
      setSelectedRequest(null);
      setReviewNotes('');
      showToast('Request approved successfully', 'success');
    },
    onError: (error: any) => {
      const errorMsg = error.response?.data?.detail || 'Failed to approve request';
      showToast(errorMsg, 'error');
    },
  });

  // Deny mutation
  const denyMutation = useMutation({
    mutationFn: ({ id, notes }: { id: number; notes?: string }) => denyRequest(id, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requests'] });
      queryClient.invalidateQueries({ queryKey: ['request-counts'] });
      setShowDetailModal(false);
      setSelectedRequest(null);
      setReviewNotes('');
      showToast('Request denied', 'info');
    },
    onError: (error: any) => {
      const errorMsg = error.response?.data?.detail || 'Failed to deny request';
      showToast(errorMsg, 'error');
    },
  });

  // Cancel mutation
  const cancelMutation = useMutation({
    mutationFn: (id: number) => cancelRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requests'] });
      queryClient.invalidateQueries({ queryKey: ['request-counts'] });
      setShowDetailModal(false);
      setSelectedRequest(null);
      showToast('Request cancelled', 'info');
    },
    onError: (error: any) => {
      const errorMsg = error.response?.data?.detail || 'Failed to cancel request';
      showToast(errorMsg, 'error');
    },
  });

  const getPosterUrl = (path: string | null | undefined) => {
    if (!path) return '/placeholder-poster.svg';
    return `https://image.tmdb.org/t/p/w500${path}`;
  };

  const getMediaTypeIcon = (mediaType: string) => {
    switch (mediaType) {
      case 'movie':
        return <Film className="w-4 h-4" />;
      case 'show':
        return <Tv className="w-4 h-4" />;
      case 'anime':
        return <Sparkles className="w-4 h-4" />;
      case 'album':
        return <Music className="w-4 h-4" />;
      default:
        return <Film className="w-4 h-4" />;
    }
  };

  const getMediaTypeBadge = (mediaType: string) => {
    const colors: Record<string, string> = {
      movie: 'bg-blue-500/20 text-blue-400 border-blue-500/50',
      show: 'bg-purple-500/20 text-purple-400 border-purple-500/50',
      anime: 'bg-pink-500/20 text-pink-400 border-pink-500/50',
      album: 'bg-green-500/20 text-green-400 border-green-500/50',
    };
    const labels: Record<string, string> = {
      movie: 'Movie',
      show: 'Show',
      anime: 'Anime',
      album: 'Album',
    };

    return (
      <span className={`flex items-center gap-1 px-2 py-1 text-xs rounded border font-medium ${colors[mediaType] || colors.movie}`}>
        {getMediaTypeIcon(mediaType)}
        {labels[mediaType] || 'Media'}
      </span>
    );
  };

  const getStatusBadge = (status: string) => {
    const config: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
      pending: {
        color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50',
        icon: <Clock className="w-3 h-3" />,
        label: 'Pending',
      },
      approved: {
        color: 'bg-green-500/20 text-green-400 border-green-500/50',
        icon: <Check className="w-3 h-3" />,
        label: 'Approved',
      },
      denied: {
        color: 'bg-red-500/20 text-red-400 border-red-500/50',
        icon: <X className="w-3 h-3" />,
        label: 'Denied',
      },
      cancelled: {
        color: 'bg-gray-500/20 text-gray-400 border-gray-500/50',
        icon: <XCircle className="w-3 h-3" />,
        label: 'Cancelled',
      },
    };

    const { color, icon, label } = config[status] || config.pending;

    return (
      <span className={`flex items-center gap-1 px-2 py-1 text-xs rounded border font-medium ${color}`}>
        {icon}
        {label}
      </span>
    );
  };

  const getRelativeTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSeconds < 60) return 'Just now';
    if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    return date.toLocaleDateString();
  };

  const canApproveRequest = (request: MediaRequest) => {
    return isAdmin || canApprove(request.mediaType);
  };

  const isOwnRequest = (request: MediaRequest) => {
    return currentUser && request.userId === currentUser.id;
  };

  const handleOpenDetail = (request: MediaRequest) => {
    setSelectedRequest(request);
    setShowDetailModal(true);
    setReviewNotes('');
  };

  const handleApprove = (request: MediaRequest) => {
    approveMutation.mutate({ id: request.id, notes: reviewNotes || undefined });
  };

  const handleDeny = (request: MediaRequest) => {
    denyMutation.mutate({ id: request.id, notes: reviewNotes || undefined });
  };

  const handleCancel = (request: MediaRequest) => {
    cancelMutation.mutate(request.id);
  };

  const filterTabs = [
    { id: 'all' as StatusFilter, label: 'All', count: counts?.total || 0 },
    { id: 'pending' as StatusFilter, label: 'Pending', count: counts?.pending || 0 },
    { id: 'approved' as StatusFilter, label: 'Approved', count: counts?.approved || 0 },
    { id: 'denied' as StatusFilter, label: 'Denied', count: counts?.denied || 0 },
  ];

  return (
    <div className="min-h-screen">
      <PageHeader
        title="Requests"
        description="View and manage media requests"
        gradientFrom="orange-600/10"
        gradientVia="amber-600/10"
        gradientTo="yellow-600/10"
      />

      <div className="container mx-auto px-6 py-8">
        {/* Filter Tabs */}
        <div className="flex gap-2 flex-wrap mb-6">
          {filterTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition cursor-pointer ${
                statusFilter === tab.id
                  ? 'bg-primary text-primary-foreground shadow-lg'
                  : 'bg-card text-foreground hover:bg-accent'
              }`}
            >
              {tab.label}
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                statusFilter === tab.id
                  ? 'bg-primary-foreground/20'
                  : 'bg-muted'
              }`}>
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        {/* Loading State */}
        {isLoading ? (
          <div className="text-center py-12">
            <div className="animate-pulse">Loading requests...</div>
          </div>
        ) : requests && requests.length > 0 ? (
          /* Request Cards Grid */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {requests.map((request) => (
              <div
                key={request.id}
                className="bg-card text-card-foreground rounded-lg shadow border-2 border-border overflow-hidden hover:shadow-lg hover:border-primary/50 transition cursor-pointer"
                onClick={() => handleOpenDetail(request)}
              >
                {/* Poster Section */}
                <div className="relative aspect-[2/3]">
                  <img
                    src={getPosterUrl(request.posterPath)}
                    alt={request.title}
                    className="w-full h-full object-cover"
                  />
                  {/* Status Badge Overlay */}
                  <div className="absolute top-2 right-2">
                    {getStatusBadge(request.status)}
                  </div>
                  {/* Media Type Badge */}
                  <div className="absolute top-2 left-2">
                    {getMediaTypeBadge(request.mediaType)}
                  </div>
                </div>

                {/* Content Section */}
                <div className="p-4 space-y-3">
                  {/* Title and Year */}
                  <div>
                    <h3 className="font-semibold text-sm truncate" title={request.title}>
                      {request.title}
                    </h3>
                    {request.year && (
                      <span className="text-xs text-muted-foreground">{request.year}</span>
                    )}
                  </div>

                  {/* Requester Info */}
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center">
                      <User className="w-3 h-3 text-primary" />
                    </div>
                    <span className="truncate">{request.username}</span>
                  </div>

                  {/* Request Date */}
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Calendar className="w-3 h-3" />
                    {getRelativeTime(request.requestedAt)}
                  </div>

                  {/* Request Notes Preview */}
                  {request.requestNotes && (
                    <div className="flex items-start gap-1 text-xs text-muted-foreground bg-muted/50 p-2 rounded">
                      <MessageSquare className="w-3 h-3 mt-0.5 flex-shrink-0" />
                      <span className="line-clamp-2">{request.requestNotes}</span>
                    </div>
                  )}

                  {/* Action Buttons for Pending Requests */}
                  {request.status === 'pending' && (
                    <div className="flex gap-2 pt-2">
                      {canApproveRequest(request) && (
                        <>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              approveMutation.mutate({ id: request.id });
                            }}
                            disabled={approveMutation.isPending}
                            className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition text-xs font-medium cursor-pointer disabled:opacity-50"
                          >
                            <Check className="w-3 h-3" />
                            Approve
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              denyMutation.mutate({ id: request.id });
                            }}
                            disabled={denyMutation.isPending}
                            className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition text-xs font-medium cursor-pointer disabled:opacity-50"
                          >
                            <X className="w-3 h-3" />
                            Deny
                          </button>
                        </>
                      )}
                      {isOwnRequest(request) && !canApproveRequest(request) && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            cancelMutation.mutate(request.id);
                          }}
                          disabled={cancelMutation.isPending}
                          className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition text-xs font-medium cursor-pointer disabled:opacity-50"
                        >
                          <XCircle className="w-3 h-3" />
                          Cancel
                        </button>
                      )}
                    </div>
                  )}

                  {/* Cancel Button for Own Pending Requests (when user can also approve) */}
                  {request.status === 'pending' && isOwnRequest(request) && canApproveRequest(request) && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        cancelMutation.mutate(request.id);
                      }}
                      disabled={cancelMutation.isPending}
                      className="w-full flex items-center justify-center gap-1 px-3 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition text-xs font-medium cursor-pointer disabled:opacity-50"
                    >
                      <XCircle className="w-3 h-3" />
                      Cancel My Request
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          /* Empty State */
          <div className="text-center py-16 bg-card rounded-lg border border-border">
            <Clock className="w-16 h-16 mx-auto mb-4 text-muted-foreground/50" />
            <h3 className="text-xl font-semibold mb-2">
              {statusFilter === 'pending'
                ? 'No pending requests'
                : statusFilter === 'approved'
                ? 'No approved requests'
                : statusFilter === 'denied'
                ? 'No denied requests'
                : 'No requests found'}
            </h3>
            <p className="text-muted-foreground">
              {statusFilter === 'pending'
                ? 'All caught up! There are no requests waiting for review.'
                : 'Requests will appear here once they are made.'}
            </p>
          </div>
        )}
      </div>

      {/* Request Detail Modal */}
      {showDetailModal && selectedRequest && (
        <div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-50 flex items-center justify-center p-4">
          <div className="bg-background rounded-lg max-w-2xl w-full border border-border shadow-2xl max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-start gap-4 p-6 border-b border-border">
              <img
                src={getPosterUrl(selectedRequest.posterPath)}
                alt={selectedRequest.title}
                className="w-24 h-36 object-cover rounded-lg shadow-md"
              />
              <div className="flex-1">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-2xl font-bold">{selectedRequest.title}</h2>
                    {selectedRequest.year && (
                      <span className="text-muted-foreground">({selectedRequest.year})</span>
                    )}
                  </div>
                  <button
                    onClick={() => setShowDetailModal(false)}
                    className="p-2 hover:bg-accent rounded-lg transition cursor-pointer"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
                <div className="flex gap-2 mt-3">
                  {getMediaTypeBadge(selectedRequest.mediaType)}
                  {getStatusBadge(selectedRequest.status)}
                </div>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-6">
              {/* Overview */}
              {selectedRequest.overview && (
                <div>
                  <h3 className="text-sm font-semibold text-muted-foreground mb-2">Overview</h3>
                  <p className="text-sm leading-relaxed">{selectedRequest.overview}</p>
                </div>
              )}

              {/* Request Info */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-muted/50 p-4 rounded-lg">
                  <h4 className="text-xs font-semibold text-muted-foreground mb-1">Requested By</h4>
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
                      <User className="w-4 h-4 text-primary" />
                    </div>
                    <span className="font-medium">{selectedRequest.username}</span>
                  </div>
                </div>
                <div className="bg-muted/50 p-4 rounded-lg">
                  <h4 className="text-xs font-semibold text-muted-foreground mb-1">Requested On</h4>
                  <div className="font-medium">
                    {new Date(selectedRequest.requestedAt).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    })}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {getRelativeTime(selectedRequest.requestedAt)}
                  </div>
                </div>
              </div>

              {/* Request Notes */}
              {selectedRequest.requestNotes && (
                <div className="bg-muted/50 p-4 rounded-lg">
                  <h4 className="text-xs font-semibold text-muted-foreground mb-2">Request Notes</h4>
                  <p className="text-sm">{selectedRequest.requestNotes}</p>
                </div>
              )}

              {/* Review History (for non-pending requests) */}
              {selectedRequest.status !== 'pending' && selectedRequest.reviewedAt && (
                <div className="bg-muted/50 p-4 rounded-lg">
                  <h4 className="text-xs font-semibold text-muted-foreground mb-2">Review History</h4>
                  <div className="flex items-start gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      selectedRequest.status === 'approved' ? 'bg-green-500/20' : 'bg-red-500/20'
                    }`}>
                      {selectedRequest.status === 'approved' ? (
                        <Check className="w-4 h-4 text-green-400" />
                      ) : (
                        <X className="w-4 h-4 text-red-400" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="font-medium">
                        {selectedRequest.status === 'approved' ? 'Approved' : selectedRequest.status === 'denied' ? 'Denied' : 'Cancelled'} by{' '}
                        <span className="text-primary">{selectedRequest.reviewerUsername || 'Unknown'}</span>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {new Date(selectedRequest.reviewedAt).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </div>
                      {selectedRequest.reviewNotes && (
                        <div className="mt-2 text-sm bg-background p-3 rounded border border-border">
                          {selectedRequest.reviewNotes}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Review Notes Input (for pending requests when user can approve) */}
              {selectedRequest.status === 'pending' && canApproveRequest(selectedRequest) && (
                <div>
                  <label className="block text-sm font-medium mb-2">Review Notes (optional)</label>
                  <textarea
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    placeholder="Add notes about this decision..."
                    className="w-full px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary resize-none"
                    rows={3}
                  />
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="flex gap-3 p-6 border-t border-border">
              {selectedRequest.status === 'pending' && (
                <>
                  {canApproveRequest(selectedRequest) && (
                    <>
                      <button
                        onClick={() => handleApprove(selectedRequest)}
                        disabled={approveMutation.isPending}
                        className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition font-medium cursor-pointer disabled:opacity-50"
                      >
                        <Check className="w-5 h-5" />
                        {approveMutation.isPending ? 'Approving...' : 'Approve Request'}
                      </button>
                      <button
                        onClick={() => handleDeny(selectedRequest)}
                        disabled={denyMutation.isPending}
                        className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition font-medium cursor-pointer disabled:opacity-50"
                      >
                        <X className="w-5 h-5" />
                        {denyMutation.isPending ? 'Denying...' : 'Deny Request'}
                      </button>
                    </>
                  )}
                  {isOwnRequest(selectedRequest) && (
                    <button
                      onClick={() => handleCancel(selectedRequest)}
                      disabled={cancelMutation.isPending}
                      className={`${canApproveRequest(selectedRequest) ? 'w-auto' : 'flex-1'} flex items-center justify-center gap-2 px-6 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition font-medium cursor-pointer disabled:opacity-50`}
                    >
                      <XCircle className="w-5 h-5" />
                      {cancelMutation.isPending ? 'Cancelling...' : 'Cancel Request'}
                    </button>
                  )}
                </>
              )}
              <button
                onClick={() => setShowDetailModal(false)}
                className={`${selectedRequest.status !== 'pending' ? 'flex-1' : ''} px-6 py-3 bg-muted text-foreground rounded-lg hover:opacity-90 transition font-medium cursor-pointer`}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-4 right-4 z-[70]">
          <Toast
            message={toast.message}
            type={toast.type}
            onClose={() => setToast(null)}
          />
        </div>
      )}
    </div>
  );
}
