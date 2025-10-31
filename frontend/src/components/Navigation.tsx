'use client';

import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';
import { useState, useEffect, useRef } from 'react';
import { Moon, Sun, LogOut, ChevronLeft, ChevronRight, Search, Plus } from 'lucide-react';
import { api } from '@/lib/api';
import { useTheme } from '@/contexts/ThemeContext';
import { useSidebar } from '@/contexts/SidebarContext';

export default function Navigation() {
  const router = useRouter();
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
  const { collapsed, toggleCollapsed } = useSidebar();
  const [user, setUser] = useState<any>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMounted(true);

    const fetchUser = async () => {
      try {
        const response = await api.get('/auth/me');
        setUser(response.data);
      } catch (error) {
        console.error('Failed to fetch user:', error);
      }
    };

    const token = document.cookie.split('; ').find(row => row.startsWith('access_token='));
    if (token) {
      fetchUser();
    }
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    const searchLibrary = async () => {
      if (searchQuery.trim().length < 2) {
        setSearchResults([]);
        setShowDropdown(false);
        return;
      }

      setIsSearching(true);
      try {
        const [moviesRes, showsRes, animeRes] = await Promise.all([
          api.get('/movies').catch(() => ({ data: { movies: [] } })),
          api.get('/shows').catch(() => ({ data: { shows: [] } })),
          api.get('/anime').catch(() => ({ data: { anime: [] } })),
        ]);

        const allItems = [
          ...(moviesRes.data?.movies || []).map((item: any) => ({ ...item, media_type: 'movie' })),
          ...(showsRes.data?.shows || []).map((item: any) => ({ ...item, media_type: 'show' })),
          ...(animeRes.data?.anime || []).map((item: any) => ({ ...item, media_type: 'anime' })),
        ];

        const filtered = allItems.filter((item: any) =>
          item.title?.toLowerCase().includes(searchQuery.toLowerCase())
        ).slice(0, 5);

        setSearchResults(filtered);
        setShowDropdown(true);
      } catch (error) {
        console.error('Search error:', error);
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    };

    const debounce = setTimeout(searchLibrary, 300);
    return () => clearTimeout(debounce);
  }, [searchQuery]);

  const handleLogout = () => {
    document.cookie = 'access_token=; path=/; max-age=0';
    document.cookie = 'refresh_token=; path=/; max-age=0';
    router.push('/login');
  };

  const isActive = (path: string) => pathname === path;

  const navSections = [
    {
      label: 'General',
      links: [
        { href: '/', label: 'Dashboard', icon: '📊' },
        { href: '/activity', label: 'Activity', icon: '📥' },
      ],
    },
    {
      label: 'Media',
      links: [
        { href: '/movies', label: 'Movies', icon: '🎬' },
        { href: '/shows', label: 'TV Shows', icon: '📺' },
        { href: '/anime', label: 'Anime', icon: '🎌' },
      ],
    },
    {
      label: 'Discovery',
      links: [
        { href: '/discover', label: 'Discover', icon: '🔍' },
        { href: '/search', label: 'Search', icon: '➕' },
      ],
    },
    {
      label: 'Management',
      links: [
        { href: '/transcoding', label: 'Transcoding', icon: '⚙️' },
        { href: '/media-profiles', label: 'Media Profiles', icon: '📝' },
        { href: '/settings', label: 'Settings', icon: '🔧' },
      ],
    },
  ];

  if (!mounted) return null;

  const token = document.cookie.split('; ').find(row => row.startsWith('access_token='));
  const isAuthPage = pathname === '/login' || pathname === '/register';
  const isSetupPage = pathname === '/setup';

  if (!token || isAuthPage || isSetupPage) return null;

  return (
    <>
      {/* Desktop Sidebar */}
      <aside className={`hidden md:flex flex-col fixed left-0 top-0 h-screen bg-background border-r-2 border-border transition-all duration-300 ${collapsed ? 'w-20' : 'w-64'}`}>
        {/* Logo and Collapse Button */}
        <div className="flex items-center justify-between p-4 border-b-2 border-border">
          {!collapsed && (
            <Link href="/" className="text-2xl font-bold logo-gradient">
              Nexarr
            </Link>
          )}
          <button
            onClick={toggleCollapsed}
            className="p-2 rounded-lg hover:bg-accent transition ml-auto"
            aria-label="Toggle sidebar"
          >
            {collapsed ? (
              <ChevronRight className="w-5 h-5" />
            ) : (
              <ChevronLeft className="w-5 h-5" />
            )}
          </button>
        </div>

        {/* Global Search */}
        {!collapsed && (
          <div className="px-3 py-2 relative" ref={searchRef}>
            <div className="relative">
              <Search className="w-5 h-5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => searchQuery.length >= 2 && setShowDropdown(true)}
                placeholder="Quick Search..."
                className="w-full pl-10 pr-4 py-3 rounded-lg bg-accent/50 border border-border hover:bg-accent hover:border-primary/30 focus:bg-accent focus:border-primary/30 focus:outline-none transition-all text-sm placeholder:text-muted-foreground"
              />
            </div>

            {showDropdown && (
              <div className="absolute top-full left-3 right-3 mt-2 bg-background border border-border rounded-lg shadow-2xl z-50 max-h-96 overflow-y-auto">
                {isSearching ? (
                  <div className="p-4 text-center text-sm text-muted-foreground">Searching...</div>
                ) : searchResults.length > 0 ? (
                  <>
                    <div className="p-2">
                      {searchResults.map((item) => (
                        <Link
                          key={`${item.media_type}-${item.id}`}
                          href={`/${item.media_type === 'movie' ? 'movies' : item.media_type === 'show' ? 'shows' : 'anime'}/${item.id}`}
                          onClick={() => {
                            setShowDropdown(false);
                            setSearchQuery('');
                          }}
                          className="flex items-center gap-3 p-2 rounded-lg hover:bg-accent transition"
                        >
                          {item.poster_path && (
                            <img
                              src={`https://image.tmdb.org/t/p/w92${item.poster_path}`}
                              alt={item.title}
                              className="w-10 h-14 object-cover rounded"
                            />
                          )}
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm truncate">{item.title}</p>
                            <p className="text-xs text-muted-foreground capitalize">{item.media_type}</p>
                          </div>
                        </Link>
                      ))}
                    </div>
                    <div className="border-t border-border p-2">
                      <button
                        onClick={() => {
                          router.push(`/search?q=${encodeURIComponent(searchQuery)}`);
                          setShowDropdown(false);
                          setSearchQuery('');
                        }}
                        className="w-full flex items-center justify-center gap-2 p-2 rounded-lg hover:bg-accent transition text-sm text-primary"
                      >
                        <Plus className="w-4 h-4" />
                        <span>Add new media</span>
                      </button>
                    </div>
                  </>
                ) : searchQuery.length >= 2 ? (
                  <div className="p-4">
                    <p className="text-sm text-muted-foreground text-center mb-3">No items found in library</p>
                    <button
                      onClick={() => {
                        router.push(`/search?q=${encodeURIComponent(searchQuery)}`);
                        setShowDropdown(false);
                        setSearchQuery('');
                      }}
                      className="w-full flex items-center justify-center gap-2 p-2 rounded-lg hover:bg-accent transition text-sm text-primary"
                    >
                      <Plus className="w-4 h-4" />
                      <span>Search for "{searchQuery}" to add</span>
                    </button>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        )}

        {/* Navigation Links */}
        <nav className="flex-1 overflow-y-auto py-4">
          <div className="space-y-6 px-3">
            {navSections.map((section) => (
              <div key={section.label}>
                {!collapsed && (
                  <h3 className="px-4 mb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {section.label}
                  </h3>
                )}
                <div className="space-y-1">
                  {section.links.map((link) => (
                    <Link
                      key={link.href}
                      href={link.href}
                      className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                        isActive(link.href)
                          ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/50'
                          : 'text-foreground/70 hover:text-foreground hover:bg-accent/70'
                      }`}
                      title={collapsed ? link.label : undefined}
                    >
                      <span className="text-xl">{link.icon}</span>
                      {!collapsed && <span className="font-medium">{link.label}</span>}
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </nav>

        {/* Bottom Section - User and Theme */}
        <div className="border-t-2 border-border p-3 space-y-2">
          <button
            onClick={toggleTheme}
            className="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-accent transition w-full"
            aria-label="Toggle theme"
            title={collapsed ? (theme === 'dark' ? 'Light Mode' : 'Dark Mode') : undefined}
          >
            {theme === 'dark' ? (
              <Sun className="w-5 h-5 text-yellow-400" />
            ) : (
              <Moon className="w-5 h-5 text-muted-foreground" />
            )}
            {!collapsed && (
              <span className="text-sm font-medium">
                {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
              </span>
            )}
          </button>

          {user && !collapsed && (
            <div className="px-3 py-2 text-sm text-muted-foreground">
              {user.username}
            </div>
          )}

          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-destructive/10 text-destructive transition w-full"
            title={collapsed ? 'Logout' : undefined}
          >
            <LogOut className="w-5 h-5" />
            {!collapsed && <span className="text-sm font-medium">Logout</span>}
          </button>
        </div>
      </aside>

      {/* Mobile Top Nav */}
      <nav className="md:hidden bg-background text-card-foreground shadow-lg border-b-2 border-border fixed top-0 left-0 right-0 z-50">
        <div className="flex justify-between items-center h-16 px-4">
          <Link href="/" className="text-xl font-bold logo-gradient">
            Nexarr
          </Link>

          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 rounded-md hover:bg-accent"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {mobileMenuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="border-t-2 border-border bg-background">
            <div className="px-2 pt-2 pb-3 space-y-4 max-h-[calc(100vh-4rem)] overflow-y-auto">
              {navSections.map((section) => (
                <div key={section.label}>
                  <h3 className="px-3 mb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {section.label}
                  </h3>
                  <div className="space-y-1">
                    {section.links.map((link) => (
                      <Link
                        key={link.href}
                        href={link.href}
                        onClick={() => setMobileMenuOpen(false)}
                        className={`flex items-center gap-3 px-3 py-3 rounded-lg transition ${
                          isActive(link.href)
                            ? 'bg-primary text-primary-foreground'
                            : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                        }`}
                      >
                        <span className="text-xl">{link.icon}</span>
                        <span className="font-medium">{link.label}</span>
                      </Link>
                    ))}
                  </div>
                </div>
              ))}
              <div className="pt-4 border-t-2 border-border space-y-1">
                {user && (
                  <div className="px-3 py-2 text-sm text-muted-foreground">
                    {user.username}
                  </div>
                )}
                <button
                  onClick={toggleTheme}
                  className="w-full flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-accent transition"
                >
                  {theme === 'dark' ? (
                    <>
                      <Sun className="w-5 h-5 text-yellow-400" />
                      <span className="font-medium">Light Mode</span>
                    </>
                  ) : (
                    <>
                      <Moon className="w-5 h-5" />
                      <span className="font-medium">Dark Mode</span>
                    </>
                  )}
                </button>
                <button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    handleLogout();
                  }}
                  className="w-full flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-destructive/10 text-destructive"
                >
                  <LogOut className="w-5 h-5" />
                  <span className="font-medium">Logout</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </nav>
    </>
  );
}
