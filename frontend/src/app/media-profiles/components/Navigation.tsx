'use client';

import {
  User,
  Film,
  Tv,
  Sparkles,
  Music2,
  Search,
  FolderOutput,
  Languages,
  FileSearch,
  Award,
  FileText,
  Settings,
  Filter,
  Clock,
  Server,
  Files,
} from 'lucide-react';
import { NavigationGroup } from './types';

interface NavigationTab {
  id: string;
  label: string;
}

interface NavigationItem {
  id: NavigationGroup;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  tabs: NavigationTab[];
}

interface NavigationProps {
  activeGroup: NavigationGroup;
  activeTab: string;
  onGroupChange: (group: NavigationGroup) => void;
  onTabChange: (tab: string) => void;
}

const navigationStructure: NavigationItem[] = [
  {
    id: 'profile',
    label: 'Profile',
    icon: User,
    tabs: [
      { id: 'general', label: 'General' },
      { id: 'languages', label: 'Languages' },
    ],
  },
  {
    id: 'movies',
    label: 'Movies',
    icon: Film,
    tabs: [
      { id: 'indexers', label: 'Indexers' },
      { id: 'quality', label: 'Quality' },
      { id: 'naming', label: 'Naming' },
    ],
  },
  {
    id: 'tvshows',
    label: 'TV Shows',
    icon: Tv,
    tabs: [
      { id: 'indexers', label: 'Indexers' },
      { id: 'quality', label: 'Quality' },
      { id: 'naming', label: 'Naming' },
      { id: 'options', label: 'Options' },
    ],
  },
  {
    id: 'anime',
    label: 'Anime',
    icon: Sparkles,
    tabs: [
      { id: 'indexers', label: 'Indexers' },
      { id: 'quality', label: 'Quality' },
      { id: 'naming', label: 'Naming' },
      { id: 'options', label: 'Options' },
    ],
  },
  {
    id: 'music',
    label: 'Music',
    icon: Music2,
    tabs: [
      { id: 'indexers', label: 'Indexers' },
      { id: 'quality', label: 'Quality' },
      { id: 'naming', label: 'Naming' },
    ],
  },
  {
    id: 'search',
    label: 'Search & Filters',
    icon: Search,
    tabs: [
      { id: 'sorting', label: 'Sorting' },
      { id: 'filters', label: 'Filters' },
      { id: 'timing', label: 'Timing' },
    ],
  },
  {
    id: 'fileoutput',
    label: 'File Output',
    icon: FolderOutput,
    tabs: [
      { id: 'server', label: 'Server' },
      { id: 'files', label: 'Files' },
    ],
  },
];

export default function Navigation({
  activeGroup,
  activeTab,
  onGroupChange,
  onTabChange,
}: NavigationProps) {
  const activeNavItem = navigationStructure.find((item) => item.id === activeGroup);

  return (
    <div className="flex h-full">
      {/* Sidebar with main groups */}
      <div className="w-56 bg-muted/30 border-r border-border overflow-y-auto">
        <div className="p-2 space-y-1">
          {navigationStructure.map((item) => {
            const Icon = item.icon;
            const isActive = activeGroup === item.id;

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  onGroupChange(item.id);
                  if (item.tabs.length > 0) {
                    onTabChange(item.tabs[0].id);
                  }
                }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all cursor-pointer ${
                  isActive
                    ? 'bg-primary text-primary-foreground font-medium shadow-sm'
                    : 'text-foreground hover:bg-muted/50'
                }`}
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                <span className="text-sm truncate">{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Tabs for the selected group */}
      {activeNavItem && activeNavItem.tabs.length > 0 && (
        <div className="w-48 bg-muted/10 border-r border-border overflow-y-auto">
          <div className="p-2 space-y-1">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-3 py-2">
              {activeNavItem.label}
            </h3>
            {activeNavItem.tabs.map((tab) => {
              const isActive = activeTab === tab.id;

              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => onTabChange(tab.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg transition-colors text-sm cursor-pointer ${
                    isActive
                      ? 'bg-primary/10 text-primary font-medium border-l-2 border-primary'
                      : 'text-foreground hover:bg-muted/50'
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export type { NavigationProps };
