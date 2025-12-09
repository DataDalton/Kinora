'use client';

import { SectionProps } from '../types';

const INDEXERS_BY_TYPE = {
  movies: ['1337x', 'YTS'],
  shows: ['1337x'],
  anime: ['Nyaa'],
  music: ['Rutracker'],
};

export default function Indexers({ formData, setFormData, hasAttemptedSubmit }: SectionProps) {
  return (
    <div className="space-y-6">
      <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
        <h4 className="font-semibold text-sm mb-2">Indexer Configuration</h4>
        <p className="text-xs text-muted-foreground">
          Configure indexer priority separately for movies, TV shows, anime, and music. Higher priority = searched first.
        </p>
      </div>

      <div className={`space-y-6 p-4 rounded-lg border-2 ${
        hasAttemptedSubmit &&
        formData.movie_indexers.length === 0 &&
        formData.show_indexers.length === 0 &&
        formData.anime_indexers.length === 0
          ? 'border-destructive bg-destructive/5'
          : 'border-transparent'
      }`}>
        {/* Movie Indexers */}
        <div>
          <label className="block text-sm font-semibold mb-2">Movie Indexers</label>
          <p className="text-xs text-muted-foreground mb-2">Indexers for movie searches</p>
          <div className="flex flex-wrap gap-2 p-3 bg-muted/50 rounded-lg border border-border">
            {INDEXERS_BY_TYPE.movies.map((indexer) => {
              const index = formData.movie_indexers.indexOf(indexer);
              const isSelected = index !== -1;
              return (
                <button
                  key={indexer}
                  type="button"
                  onClick={() => {
                    if (isSelected) {
                      setFormData({
                        ...formData,
                        movie_indexers: formData.movie_indexers.filter(i => i !== indexer)
                      });
                    } else {
                      setFormData({
                        ...formData,
                        movie_indexers: [...formData.movie_indexers, indexer]
                      });
                    }
                  }}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-primary/20 border-2 border-primary'
                      : 'bg-background border border-border hover:border-primary/50'
                  }`}
                >
                  {isSelected && <span className="text-xs text-muted-foreground">#{index + 1}</span>}
                  <span>{indexer}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* TV Show Indexers */}
        <div>
          <label className="block text-sm font-semibold mb-2">TV Show Indexers</label>
          <p className="text-xs text-muted-foreground mb-2">Indexers for TV show searches</p>
          <div className="flex flex-wrap gap-2 p-3 bg-muted/50 rounded-lg border border-border">
            {INDEXERS_BY_TYPE.shows.map((indexer) => {
              const index = formData.show_indexers.indexOf(indexer);
              const isSelected = index !== -1;
              return (
                <button
                  key={indexer}
                  type="button"
                  onClick={() => {
                    if (isSelected) {
                      setFormData({
                        ...formData,
                        show_indexers: formData.show_indexers.filter(i => i !== indexer)
                      });
                    } else {
                      setFormData({
                        ...formData,
                        show_indexers: [...formData.show_indexers, indexer]
                      });
                    }
                  }}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-primary/20 border-2 border-primary'
                      : 'bg-background border border-border hover:border-primary/50'
                  }`}
                >
                  {isSelected && <span className="text-xs text-muted-foreground">#{index + 1}</span>}
                  <span>{indexer}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Anime Indexers */}
        <div>
          <label className="block text-sm font-semibold mb-2">Anime Indexers</label>
          <p className="text-xs text-muted-foreground mb-2">Indexers for anime searches</p>
          <div className="flex flex-wrap gap-2 p-3 bg-muted/50 rounded-lg border border-border">
            {INDEXERS_BY_TYPE.anime.map((indexer) => {
              const index = formData.anime_indexers.indexOf(indexer);
              const isSelected = index !== -1;
              return (
                <button
                  key={indexer}
                  type="button"
                  onClick={() => {
                    if (isSelected) {
                      setFormData({
                        ...formData,
                        anime_indexers: formData.anime_indexers.filter(i => i !== indexer)
                      });
                    } else {
                      setFormData({
                        ...formData,
                        anime_indexers: [...formData.anime_indexers, indexer]
                      });
                    }
                  }}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-primary/20 border-2 border-primary'
                      : 'bg-background border border-border hover:border-primary/50'
                  }`}
                >
                  {isSelected && <span className="text-xs text-muted-foreground">#{index + 1}</span>}
                  <span>{indexer}</span>
                  {indexer === 'Nyaa' && <span className="ml-1 px-1.5 py-0.5 text-xs bg-purple-500/20 text-purple-400 rounded">Anime Only</span>}
                </button>
              );
            })}
          </div>
        </div>

        {/* Music Indexers */}
        <div>
          <label className="block text-sm font-semibold mb-2">Music Indexers</label>
          <p className="text-xs text-muted-foreground mb-2">Indexers for music searches</p>
          <div className="flex flex-wrap gap-2 p-3 bg-muted/50 rounded-lg border border-border">
            {INDEXERS_BY_TYPE.music.map((indexer) => {
              const index = formData.music_indexers.indexOf(indexer);
              const isSelected = index !== -1;
              return (
                <button
                  key={indexer}
                  type="button"
                  onClick={() => {
                    if (isSelected) {
                      setFormData({
                        ...formData,
                        music_indexers: formData.music_indexers.filter(i => i !== indexer)
                      });
                    } else {
                      setFormData({
                        ...formData,
                        music_indexers: [...formData.music_indexers, indexer]
                      });
                    }
                  }}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-primary/20 border-2 border-primary'
                      : 'bg-background border border-border hover:border-primary/50'
                  }`}
                >
                  {isSelected && <span className="text-xs text-muted-foreground">#{index + 1}</span>}
                  <span>{indexer}</span>
                  <span className="ml-1 px-1.5 py-0.5 text-xs bg-pink-500/20 text-pink-400 rounded">Music</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-semibold mb-2">Search Timeout (seconds)</label>
          <input
            type="number"
            value={formData.search_timeout}
            onChange={(e) => setFormData({ ...formData, search_timeout: parseInt(e.target.value) || 30 })}
            className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
            min="5"
            max="300"
          />
          <p className="text-xs text-muted-foreground mt-1">How long to wait for indexer response</p>
        </div>

        <div>
          <label className="block text-sm font-semibold mb-2">Max Retries</label>
          <input
            type="number"
            value={formData.max_retries}
            onChange={(e) => setFormData({ ...formData, max_retries: parseInt(e.target.value) || 3 })}
            className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
            min="0"
            max="10"
          />
          <p className="text-xs text-muted-foreground mt-1">Retry attempts on failure</p>
        </div>

        <div>
          <label className="block text-sm font-semibold mb-2">Max Results</label>
          <input
            type="number"
            value={formData.max_results}
            onChange={(e) => setFormData({ ...formData, max_results: parseInt(e.target.value) || 100 })}
            className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
            min="10"
            max="1000"
          />
          <p className="text-xs text-muted-foreground mt-1">Maximum search results per indexer</p>
        </div>
      </div>
    </div>
  );
}
