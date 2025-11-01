'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Search, Plus, Upload } from 'lucide-react';
import Link from 'next/link';
import LibraryImportModal from '@/components/LibraryImportModal';
import PageHeader from '@/components/PageHeader';

interface Show {
  id: number;
  title: string;
  original_title: string;
  overview: string;
  poster_path: string | null;
  release_date: string;
  rating: number;
  status: string;
  monitored: boolean;
  number_of_seasons: number;
  number_of_episodes: number;
}

export default function ShowsPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showImportModal, setShowImportModal] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['shows', page, statusFilter],
    queryFn: async () => {
      const params: any = { page, limit: 20 };
      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }
      const response = await api.get('/shows', { params });
      return response.data;
    },
  });

  const getPosterUrl = (path: string | null) => {
    if (!path) return '/placeholder-poster.jpg';
    return `https://image.tmdb.org/t/p/w500${path}`;
  };

  const getStatusBadge = (status: string) => {
    if (status === 'downloading') {
      return <span className="px-2 py-1 text-xs rounded bg-blue-500/20 text-blue-400 border border-blue-500/50 font-medium">Downloading</span>;
    }
    if (status === 'wanted') {
      return <span className="px-2 py-1 text-xs rounded bg-yellow-500/20 text-yellow-400 border border-yellow-500/50 font-medium">Wanted</span>;
    }
    return <span className="px-2 py-1 text-xs rounded bg-gray-500/20 text-gray-400 border border-gray-500/50 font-medium">{status}</span>;
  };

  const filteredShows = data?.shows?.filter((show: Show) =>
    show.title.toLowerCase().includes(searchQuery.toLowerCase())
  ) || [];

  return (
    <div className="min-h-screen">
      <PageHeader
        title="TV Shows"
        description="Manage and track your TV show collection"
        gradientFrom="green-600/10"
        gradientVia="teal-600/10"
        gradientTo="cyan-600/10"
      />

      {/* Content Section */}
      <div className="container mx-auto px-6 py-8">
        {/* Search and Actions Bar */}
        <div className="flex flex-col md:flex-row gap-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search your TV show library..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-12 pr-4 py-3 bg-card border-2 border-border rounded-lg focus:outline-none focus:border-primary transition-colors"
            />
          </div>
          <button
            onClick={() => setShowImportModal(true)}
            className="flex items-center gap-2 px-6 py-3 bg-card border-2 border-border text-foreground rounded-lg hover:bg-accent transition font-medium whitespace-nowrap cursor-pointer"
          >
            <Upload className="w-5 h-5" />
            Import Library
          </button>
          <Link
            href="/search?type=show"
            className="flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium whitespace-nowrap"
          >
            <Plus className="w-5 h-5" />
            Add New Show
          </Link>
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-2 flex-wrap mb-8">
          <button
            onClick={() => setStatusFilter('all')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition cursor-pointer ${
              statusFilter === 'all'
                ? 'bg-primary text-primary-foreground shadow-lg'
                : 'bg-card text-foreground hover:bg-accent'
            }`}
          >
            All
            {data?.shows && <span className="text-xs opacity-75">({data.shows.length})</span>}
          </button>
          <button
            onClick={() => setStatusFilter('wanted')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition cursor-pointer ${
              statusFilter === 'wanted'
                ? 'bg-primary text-primary-foreground shadow-lg'
                : 'bg-card text-foreground hover:bg-accent'
            }`}
          >
            Wanted
          </button>
          <button
            onClick={() => setStatusFilter('downloading')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition cursor-pointer ${
              statusFilter === 'downloading'
                ? 'bg-primary text-primary-foreground shadow-lg'
                : 'bg-card text-foreground hover:bg-accent'
            }`}
          >
            Downloading
          </button>
        </div>

        {isLoading ? (
          <div className="text-center py-12">Loading shows...</div>
        ) : filteredShows.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No TV shows found matching your search.</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
              {filteredShows.map((show: Show) => (
                <div key={show.id} className="bg-card text-card-foreground rounded-lg shadow border-2 border-border overflow-hidden hover:shadow-lg hover:border-primary/50 transition">
                  <div className="relative aspect-[2/3]">
                    <img
                      src={getPosterUrl(show.poster_path)}
                      alt={show.title}
                      className="w-full h-full object-cover"
                    />
                    {show.monitored && (
                      <div className="absolute top-2 right-2 bg-primary text-primary-foreground p-1 rounded">
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
                          <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd"/>
                        </svg>
                      </div>
                    )}
                  </div>
                  <div className="p-3">
                    <h3 className="font-semibold text-sm truncate" title={show.title}>
                      {show.title}
                    </h3>
                    <div className="flex justify-between items-center mt-2">
                      <span className="text-xs text-muted-foreground">
                        {show.number_of_seasons} Season{show.number_of_seasons !== 1 ? 's' : ''}
                      </span>
                      {getStatusBadge(show.status)}
                    </div>
                    {show.rating && (
                      <div className="mt-2 flex items-center text-xs">
                        <svg className="w-4 h-4 text-yellow-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
                        </svg>
                        {show.rating.toFixed(1)}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-8 flex justify-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-4 py-2 bg-card border border-border text-foreground rounded-lg disabled:opacity-50 hover:bg-accent transition cursor-pointer"
              >
                Previous
              </button>
              <span className="px-4 py-2 text-muted-foreground">Page {page}</span>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={!data?.shows || data.shows.length < 20}
                className="px-4 py-2 bg-card border border-border text-foreground rounded-lg disabled:opacity-50 hover:bg-accent transition cursor-pointer"
              >
                Next
              </button>
            </div>
          </>
        )}
      </div>

      {/* Library Import Modal */}
      <LibraryImportModal
        isOpen={showImportModal}
        onClose={() => setShowImportModal(false)}
        mediaType="show"
      />
    </div>
  );
}
