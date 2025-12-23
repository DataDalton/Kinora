'use client';

import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  Tag,
  X,
  Plus,
  ChevronDown,
  Check,
  Palette,
} from 'lucide-react';

interface TagItem {
  id: number;
  name: string;
  color: string | null;
}

interface TagsEditorProps {
  mediaType: 'movie' | 'show' | 'anime' | 'album' | 'artist';
  mediaId: number;
  currentTags?: TagItem[];
  onTagsChange?: (tags: TagItem[]) => void;
}

const defaultColors = [
  '#ef4444', // red
  '#f97316', // orange
  '#eab308', // yellow
  '#22c55e', // green
  '#14b8a6', // teal
  '#3b82f6', // blue
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#6b7280', // gray
];

export default function TagsEditor({
  mediaType,
  mediaId,
  currentTags: initialTags,
  onTagsChange,
}: TagsEditorProps) {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [newTagName, setNewTagName] = useState('');
  const [newTagColor, setNewTagColor] = useState(defaultColors[0]);
  const [searchQuery, setSearchQuery] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const queryClient = useQueryClient();

  const { data: mediaTags, refetch: refetchMediaTags } = useQuery({
    queryKey: ['tags', 'media', mediaType, mediaId],
    queryFn: async () => {
      const response = await api.get(`/tags/media/${mediaType}/${mediaId}`);
      return response.data as TagItem[];
    },
    initialData: initialTags,
  });

  const { data: allTags } = useQuery({
    queryKey: ['tags'],
    queryFn: async () => {
      const response = await api.get('/tags/');
      return response.data as TagItem[];
    },
  });

  const addTagMutation = useMutation({
    mutationFn: async (tagId: number) => {
      const response = await api.post(`/tags/media/${mediaType}/${mediaId}/add/${tagId}`);
      return response.data as TagItem[];
    },
    onSuccess: (newTags) => {
      queryClient.setQueryData(['tags', 'media', mediaType, mediaId], newTags);
      onTagsChange?.(newTags);
    },
  });

  const removeTagMutation = useMutation({
    mutationFn: async (tagId: number) => {
      const response = await api.delete(`/tags/media/${mediaType}/${mediaId}/remove/${tagId}`);
      return response.data as TagItem[];
    },
    onSuccess: (newTags) => {
      queryClient.setQueryData(['tags', 'media', mediaType, mediaId], newTags);
      onTagsChange?.(newTags);
    },
  });

  const createTagMutation = useMutation({
    mutationFn: async ({ name, color }: { name: string; color: string }) => {
      const response = await api.post('/tags/', { name, color });
      return response.data as TagItem;
    },
    onSuccess: (newTag) => {
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      addTagMutation.mutate(newTag.id);
      setIsCreating(false);
      setNewTagName('');
      setNewTagColor(defaultColors[0]);
    },
  });

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
        setIsCreating(false);
        setSearchQuery('');
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (isCreating && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isCreating]);

  const currentTagIds = new Set(mediaTags?.map(t => t.id) || []);
  const availableTags = allTags?.filter(t => !currentTagIds.has(t.id)) || [];
  const filteredTags = availableTags.filter(t =>
    t.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleAddTag = (tagId: number) => {
    addTagMutation.mutate(tagId);
    setIsDropdownOpen(false);
    setSearchQuery('');
  };

  const handleRemoveTag = (tagId: number) => {
    removeTagMutation.mutate(tagId);
  };

  const handleCreateTag = () => {
    if (newTagName.trim()) {
      createTagMutation.mutate({ name: newTagName.trim(), color: newTagColor });
    }
  };

  const getContrastColor = (hexColor: string): string => {
    const hex = hexColor.replace('#', '');
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminance > 0.5 ? '#000000' : '#ffffff';
  };

  return (
    <div className="bg-muted/30 rounded-lg border border-border p-4">
      <div className="flex items-center gap-2 mb-3">
        <Tag className="w-5 h-5 text-muted-foreground" />
        <span className="font-medium">Tags</span>
      </div>

      <div className="flex flex-wrap gap-2 mb-3">
        {mediaTags && mediaTags.length > 0 ? (
          mediaTags.map((tag) => (
            <span
              key={tag.id}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-medium transition group"
              style={{
                backgroundColor: tag.color || '#6b7280',
                color: getContrastColor(tag.color || '#6b7280'),
              }}
            >
              {tag.name}
              <button
                onClick={() => handleRemoveTag(tag.id)}
                disabled={removeTagMutation.isPending}
                className="p-0.5 rounded-full hover:bg-black/20 transition cursor-pointer"
                title="Remove tag"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          ))
        ) : (
          <span className="text-sm text-muted-foreground">No tags assigned</span>
        )}
      </div>

      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setIsDropdownOpen(!isDropdownOpen)}
          className="flex items-center gap-2 px-3 py-1.5 bg-muted hover:bg-muted/80 rounded-lg transition text-sm cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          Add Tag
          <ChevronDown className={`w-4 h-4 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`} />
        </button>

        {isDropdownOpen && (
          <div className="absolute z-10 mt-2 w-64 bg-background rounded-lg border border-border shadow-xl">
            {!isCreating ? (
              <>
                <div className="p-2">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search tags..."
                    className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>

                <div className="max-h-48 overflow-y-auto">
                  {filteredTags.length > 0 ? (
                    filteredTags.map((tag) => (
                      <button
                        key={tag.id}
                        onClick={() => handleAddTag(tag.id)}
                        disabled={addTagMutation.isPending}
                        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-muted transition text-left text-sm cursor-pointer"
                      >
                        <span
                          className="w-3 h-3 rounded-full flex-shrink-0"
                          style={{ backgroundColor: tag.color || '#6b7280' }}
                        />
                        <span className="truncate">{tag.name}</span>
                      </button>
                    ))
                  ) : (
                    <div className="px-3 py-2 text-sm text-muted-foreground">
                      {searchQuery ? 'No matching tags' : 'No available tags'}
                    </div>
                  )}
                </div>

                <div className="border-t border-border p-2">
                  <button
                    onClick={() => {
                      setIsCreating(true);
                      setNewTagName(searchQuery);
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 hover:bg-muted rounded-lg transition text-sm text-primary cursor-pointer"
                  >
                    <Plus className="w-4 h-4" />
                    Create new tag
                    {searchQuery && ` "${searchQuery}"`}
                  </button>
                </div>
              </>
            ) : (
              <div className="p-3 space-y-3">
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1">
                    Tag Name
                  </label>
                  <input
                    ref={inputRef}
                    type="text"
                    value={newTagName}
                    onChange={(e) => setNewTagName(e.target.value)}
                    placeholder="Enter tag name..."
                    className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && newTagName.trim()) {
                        handleCreateTag();
                      } else if (e.key === 'Escape') {
                        setIsCreating(false);
                        setNewTagName('');
                      }
                    }}
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1">
                    <Palette className="w-3 h-3 inline mr-1" />
                    Color
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {defaultColors.map((color) => (
                      <button
                        key={color}
                        onClick={() => setNewTagColor(color)}
                        className={`w-6 h-6 rounded-full transition-transform cursor-pointer ${
                          newTagColor === color ? 'scale-110 ring-2 ring-offset-2 ring-offset-background ring-primary' : ''
                        }`}
                        style={{ backgroundColor: color }}
                      >
                        {newTagColor === color && (
                          <Check className="w-4 h-4 mx-auto" style={{ color: getContrastColor(color) }} />
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
                  <button
                    onClick={() => {
                      setIsCreating(false);
                      setNewTagName('');
                    }}
                    className="px-3 py-1.5 text-sm hover:bg-muted rounded-lg transition cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreateTag}
                    disabled={!newTagName.trim() || createTagMutation.isPending}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/90 transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {createTagMutation.isPending ? (
                      <div className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <Plus className="w-4 h-4" />
                    )}
                    Create
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
