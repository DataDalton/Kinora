'use client';

import { ReactNode, useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { SidebarProvider, useSidebar } from '@/contexts/SidebarContext';
import Navigation from '@/components/Navigation';
import { api } from '@/lib/api';

function MainContent({ children }: { children: ReactNode }) {
  const { collapsed } = useSidebar();
  const router = useRouter();
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);
  const [isAuthPage, setIsAuthPage] = useState(false);
  const [isSetupPage, setIsSetupPage] = useState(false);
  const [setupChecked, setSetupChecked] = useState(false);

  useEffect(() => {
    setMounted(true);
    const authPages = ['/login', '/register'];
    const setupPages = ['/setup'];
    setIsAuthPage(authPages.includes(pathname));
    setIsSetupPage(setupPages.includes(pathname));

    // Check setup status only if logged in and not on auth/setup pages
    const checkSetup = async () => {
      if (authPages.includes(pathname) || setupPages.includes(pathname)) {
        setSetupChecked(true);
        return;
      }

      const token = document.cookie.split('; ').find(row => row.startsWith('access_token='));
      if (!token) {
        setSetupChecked(true);
        return;
      }

      try {
        const response = await api.get('/setup/status');
        if (!response.data.is_setup_complete && response.data.user_role === 'administrator') {
          router.push('/setup');
        }
      } catch (error) {
        console.error('Failed to check setup status:', error);
      } finally {
        setSetupChecked(true);
      }
    };

    checkSetup();
  }, [pathname, router]);

  if (!mounted || isAuthPage || isSetupPage || !setupChecked) {
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
