export interface MediaRequest {
  id: number;
  userId: number;
  username: string;
  mediaType: 'movie' | 'show' | 'anime' | 'album';
  externalId: number;
  title: string;
  posterPath?: string;
  year?: number;
  overview?: string;
  status: 'pending' | 'approved' | 'denied' | 'cancelled';
  requestNotes?: string;
  requestedAt: string;
  reviewedAt?: string;
  reviewedBy?: number;
  reviewerUsername?: string;
  reviewNotes?: string;
  createdMediaId?: number;
}

export interface MediaRequestCreate {
  mediaType: string;
  externalId: number;
  title: string;
  posterPath?: string;
  year?: number;
  overview?: string;
  requestNotes?: string;
  mediaProfileId?: number;
  rootFolderId?: number;
  autoSearch?: boolean;
}

export interface MediaRequestCount {
  pending: number;
  approved: number;
  denied: number;
  total: number;
}
