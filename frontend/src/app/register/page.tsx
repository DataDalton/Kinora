'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { UserPlus, Loader2, Moon, Sun, Film, ArrowRight, ArrowLeft, Shield } from 'lucide-react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useTheme } from '@/contexts/ThemeContext';
import TwoFactorSettings from '@/components/TwoFactorSettings';
import HolographicGrid from '@/components/HolographicGrid';

type RegistrationStep = 'credentials' | '2fa';

export default function RegisterPage() {
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();
  const [currentStep, setCurrentStep] = useState<RegistrationStep>('credentials');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const checkRegistrationStatus = async () => {
      try {
        const response = await api.get('/auth/registration-status');
        if (!response.data.enabled) {
          router.push('/login?error=registration_disabled');
          return;
        }
        setChecking(false);
      } catch (error) {
        setChecking(false);
      }
    };
    checkRegistrationStatus();
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }

    setLoading(true);

    try {
      await api.post('/auth/register', {
        username,
        password,
      });

      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);

      const loginResponse = await api.post('/auth/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      const { access_token, refresh_token } = loginResponse.data;

      document.cookie = `access_token=${access_token}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
      document.cookie = `refresh_token=${refresh_token}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;

      setCurrentStep('2fa');
      setLoading(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
      setLoading(false);
    }
  };

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen relative flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 overflow-hidden bg-background">
      {/* Holographic grid background */}
      <HolographicGrid />

      {/* Theme toggle button */}
      <button
        onClick={toggleTheme}
        className="fixed bottom-6 right-6 z-50 p-4 rounded-full bg-gradient-to-br from-[#27272a] to-[#3b82f6] hover:shadow-2xl hover:scale-110 transition-all duration-300 shadow-xl cursor-pointer"
        aria-label="Toggle theme"
      >
        {theme === 'dark' ? (
          <Sun className="w-6 h-6 text-white" />
        ) : (
          <Moon className="w-6 h-6 text-white" />
        )}
      </button>

      {/* Register card */}
      <div className={cn(
        "relative w-full z-10 transition-all",
        currentStep === 'credentials' ? "max-w-md" : "max-w-4xl"
      )}>
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-[#27272a] to-[#3b82f6] mb-6 shadow-2xl">
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
          {/* Step indicators */}
          <div className="flex items-center justify-center mb-8 gap-2">
            <div className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg transition-all",
              currentStep === 'credentials' ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
            )}>
              <UserPlus className="w-4 h-4" />
              <span className="text-sm font-medium">Account</span>
            </div>
            <ArrowRight className="w-4 h-4 text-muted-foreground" />
            <div className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg transition-all",
              currentStep === '2fa' ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
            )}>
              <Shield className="w-4 h-4" />
              <span className="text-sm font-medium">Security (Optional)</span>
            </div>
          </div>

          {currentStep === 'credentials' && (
            <>
              <h2 className="text-2xl font-bold text-foreground mb-6 text-center">
                Create Your Account
              </h2>

              <form className="space-y-6" onSubmit={handleSubmit}>
            {error && (
              <div className="rounded-lg bg-destructive/10 border border-destructive/50 p-4">
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
                  placeholder="Choose a username"
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
                  placeholder="At least 8 characters"
                />
              </div>

              <div>
                <label htmlFor="confirmPassword" className="block text-sm font-semibold text-foreground mb-2">
                  Confirm Password
                </label>
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className={cn(
                    "w-full px-4 py-3 rounded-lg",
                    "bg-background border-2 border-input",
                    "text-foreground placeholder:text-muted-foreground",
                    "focus:outline-none focus:border-primary focus:ring-4 focus:ring-ring/20",
                    "transition-all duration-200"
                  )}
                  placeholder="Confirm your password"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className={cn(
                "w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg",
                "bg-gradient-to-r from-[#27272a] to-[#3b82f6]",
                "text-primary-foreground font-semibold text-base",
                "hover:shadow-lg hover:scale-[1.02]",
                "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
                "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100",
                "transition-all cursor-pointer"
              )}
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Creating account...
                </>
              ) : (
                <>
                  <UserPlus className="w-5 h-5" />
                  Sign up
                </>
              )}
            </button>

                <div className="text-center pt-4">
                  <p className="text-sm text-muted-foreground">
                    Already have an account?{' '}
                    <Link
                      href="/login"
                      className="font-semibold text-primary hover:text-primary/80 transition-colors"
                    >
                      Sign in
                    </Link>
                  </p>
                </div>
              </form>
            </>
          )}

          {currentStep === '2fa' && (
            <div className="space-y-6">
              <div className="text-center mb-6">
                <h2 className="text-2xl font-bold text-foreground mb-2 flex items-center justify-center gap-2">
                  Secure Your Account
                  <span className="text-xs font-medium px-2 py-1 rounded-md bg-primary/10 text-primary border border-primary/20">
                    Optional
                  </span>
                </h2>
                <p className="text-sm text-muted-foreground mb-2">
                  Add an extra layer of security with two-factor authentication
                </p>
                <p className="text-xs text-muted-foreground/70">
                  You can always set this up later from your profile settings
                </p>
              </div>

              <TwoFactorSettings />

              <div className="flex gap-3 pt-6 border-t border-border">
                <button
                  onClick={() => setCurrentStep('credentials')}
                  className="px-6 py-3 bg-muted text-foreground rounded-lg hover:opacity-90 transition flex items-center gap-2 cursor-pointer"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back
                </button>
                <button
                  onClick={() => router.push('/')}
                  className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition flex items-center justify-center gap-2 font-medium cursor-pointer"
                >
                  Skip for now
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
