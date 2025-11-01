'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { LogIn, Loader2, Moon, Sun, Film } from 'lucide-react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useTheme } from '@/contexts/ThemeContext';

export default function LoginPage() {
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorTrigger, setErrorTrigger] = useState(0);
  const [registrationEnabled, setRegistrationEnabled] = useState(true);

  useEffect(() => {
    const checkRegistrationStatus = async () => {
      try {
        const response = await api.get('/auth/registration-status');
        setRegistrationEnabled(response.data.enabled);
      } catch (error) {
        setRegistrationEnabled(true);
      }
    };
    checkRegistrationStatus();

    const params = new URLSearchParams(window.location.search);
    const errorParam = params.get('error');
    if (errorParam === 'registration_disabled') {
      setError('New user registration is currently disabled. Please contact an administrator.');
      setErrorTrigger(prev => prev + 1);
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);

      const response = await api.post('/auth/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      const { access_token, refresh_token } = response.data;

      document.cookie = `access_token=${access_token}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
      document.cookie = `refresh_token=${refresh_token}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;

      router.push('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed. Please try again.');
      setErrorTrigger(prev => prev + 1);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 overflow-hidden bg-background">
      {/* Animated background gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary via-transparent to-purple-600 opacity-10 dark:opacity-20" />

      {/* Animated floating shapes */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary rounded-full mix-blend-multiply dark:mix-blend-screen filter blur-3xl opacity-20 animate-blob" />
        <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply dark:mix-blend-screen filter blur-3xl opacity-20 animate-blob animation-delay-2000" />
        <div className="absolute bottom-1/4 left-1/3 w-96 h-96 bg-pink-500 rounded-full mix-blend-multiply dark:mix-blend-screen filter blur-3xl opacity-20 animate-blob animation-delay-4000" />
      </div>

      {/* Theme toggle button */}
      <button
        onClick={toggleTheme}
        className="fixed bottom-6 right-6 z-50 p-4 rounded-full bg-gradient-to-br from-primary to-purple-600 hover:shadow-2xl hover:scale-110 transition-all duration-300 shadow-xl"
        aria-label="Toggle theme"
      >
        {theme === 'dark' ? (
          <Sun className="w-6 h-6 text-white" />
        ) : (
          <Moon className="w-6 h-6 text-white" />
        )}
      </button>

      {/* Login card */}
      <div className="relative w-full max-w-md z-10">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-primary to-purple-600 mb-6 shadow-2xl">
            <Film className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-6xl font-bold logo-gradient mb-3">
            Nexarr
          </h1>
          <p className="text-lg text-muted-foreground font-medium">
            Unified Media Management
          </p>
        </div>

        <div className="bg-card border border-border rounded-2xl shadow-2xl p-8 backdrop-blur-sm">
          <h2 className="text-2xl font-bold text-foreground mb-6 text-center">
            Welcome Back
          </h2>

          <form className="space-y-6" onSubmit={handleSubmit}>
            {error && (
              <div
                key={errorTrigger}
                className="rounded-lg bg-destructive/10 border border-destructive/50 p-4 animate-shake"
              >
                <div className="text-sm text-destructive font-medium">{error}</div>
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label htmlFor="username" className="block text-sm font-semibold text-foreground mb-2">
                  Username
                </label>
                <input
                  id="username"
                  name="username"
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className={cn(
                    "w-full px-4 py-3 rounded-lg",
                    "bg-background border-2 border-input",
                    "text-foreground placeholder:text-muted-foreground",
                    "focus:outline-none focus:border-primary focus:ring-4 focus:ring-ring/20",
                    "transition-all duration-200"
                  )}
                  placeholder="Enter your username"
                />
              </div>
              <div>
                <label htmlFor="password" className="block text-sm font-semibold text-foreground mb-2">
                  Password
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={cn(
                    "w-full px-4 py-3 rounded-lg",
                    "bg-background border-2 border-input",
                    "text-foreground placeholder:text-muted-foreground",
                    "focus:outline-none focus:border-primary focus:ring-4 focus:ring-ring/20",
                    "transition-all duration-200"
                  )}
                  placeholder="Enter your password"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className={cn(
                "w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg",
                "bg-gradient-to-r from-primary to-purple-600",
                "text-primary-foreground font-semibold text-base",
                "hover:shadow-lg hover:scale-[1.02]",
                "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
                "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100",
                "transition-all"
              )}
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Signing in...
                </>
              ) : (
                <>
                  <LogIn className="w-5 h-5" />
                  Sign in
                </>
              )}
            </button>

            {registrationEnabled && (
              <div className="text-center pt-4">
                <p className="text-sm text-muted-foreground">
                  Don&apos;t have an account?{' '}
                  <Link
                    href="/register"
                    className="font-semibold text-primary hover:text-primary/80 transition-colors"
                  >
                    Sign up
                  </Link>
                </p>
              </div>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
