'use client';

import { ReactNode, useState, useEffect } from 'react';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { SidebarProvider, useSidebar } from '@/contexts/SidebarContext';
import Navigation from '@/components/Navigation';

function MainContent({ children }: { children: ReactNode }) {
  const { collapsed } = useSidebar();
  const [mounted, setMounted] = useState(false);
  const [isAuthPage, setIsAuthPage] = useState(false);

  useEffect(() => {
    setMounted(true);
    setIsAuthPage(window.location.pathname === '/login' || window.location.pathname === '/register');
  }, []);

  if (!mounted || isAuthPage) {
    return <main className="flex-1">{children}</main>;
  }

  return (
    <main className={`flex-1 transition-all duration-300 mt-16 md:mt-0 ${collapsed ? 'md:ml-20' : 'md:ml-64'}`}>
      {children}
    </main>
  );
}

export function ClientLayout({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <SidebarProvider>
        <div className="flex min-h-screen">
          <Navigation />
          <MainContent>{children}</MainContent>
        </div>
      </SidebarProvider>
    </ThemeProvider>
  );
}
