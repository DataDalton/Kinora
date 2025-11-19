'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { LogIn, Loader2, Moon, Sun, Film } from 'lucide-react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useTheme } from '@/contexts/ThemeContext';
import HolographicGrid from '@/components/HolographicGrid';

interface OIDCProvider {
  id: number;
  name: string;
  enabled: boolean;
  button_text?: string;
  button_icon?: string;
}

export default function LoginPage() {
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorTrigger, setErrorTrigger] = useState(0);
  const [registrationEnabled, setRegistrationEnabled] = useState(true);
  const [oidcProviders, setOidcProviders] = useState<OIDCProvider[]>([]);
  const [checkingForwardAuth, setCheckingForwardAuth] = useState(true);

  const [requires2FA, setRequires2FA] = useState(false);
  const [totpEnabled, setTotpEnabled] = useState(false);
  const [webauthnEnabled, setWebauthnEnabled] = useState(false);
  const [challenge, setChallenge] = useState('');
  const [totpCode, setTotpCode] = useState('');

  useEffect(() => {
    const checkForwardAuth = async () => {
      try {
        const response = await api.post('/auth/forward-auth');
        const { access_token, refresh_token } = response.data;

        document.cookie = `access_token=${access_token}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
        document.cookie = `refresh_token=${refresh_token}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;

        router.push('/');
        return true;
      } catch (error) {
        return false;
      }
    };

    const checkRegistrationStatus = async () => {
      try {
        const response = await api.get('/auth/registration-status');
        setRegistrationEnabled(response.data.enabled);
      } catch (error) {
        setRegistrationEnabled(true);
      }
    };

    const fetchOIDCProviders = async () => {
      try {
        const response = await api.get('/auth/oidc/providers');
        setOidcProviders(response.data);
      } catch (error) {
        console.error('Failed to fetch OIDC providers:', error);
      }
    };

    const initialize = async () => {
      const forwardAuthSuccess = await checkForwardAuth();
      if (!forwardAuthSuccess) {
        setCheckingForwardAuth(false);
        await Promise.all([checkRegistrationStatus(), fetchOIDCProviders()]);
      }
    };

    initialize();

    const params = new URLSearchParams(window.location.search);
    const errorParam = params.get('error');
    if (errorParam === 'registration_disabled') {
      setError('New user registration is currently disabled. Please contact an administrator.');
      setErrorTrigger(prev => prev + 1);
    }
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);

      const response = await api.post('/auth/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      const data = response.data;

      if (data.requires_2fa) {
        setRequires2FA(true);
        setTotpEnabled(data.totp_enabled);
        setWebauthnEnabled(data.webauthn_enabled);
        setChallenge(data.challenge);
        setLoading(false);
        return;
      }

      if (data.access_token && data.refresh_token) {
        document.cookie = `access_token=${data.access_token}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
        document.cookie = `refresh_token=${data.refresh_token}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;
        router.push('/');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed. Please try again.');
      setErrorTrigger(prev => prev + 1);
    } finally {
      setLoading(false);
    }
  };

  const handleVerify2FA = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await api.post('/auth/verify-2fa', {
        username,
        code: totpCode || undefined,
      });

      const { access_token, refresh_token } = response.data;

      document.cookie = `access_token=${access_token}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
      document.cookie = `refresh_token=${refresh_token}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;

      router.push('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || '2FA verification failed.');
      setErrorTrigger(prev => prev + 1);
    } finally {
      setLoading(false);
    }
  };

  const handleWebAuthnAuth = async () => {
    setLoading(true);
    setError('');

    try {
      const assertion = await navigator.credentials.get({
        publicKey: {
          challenge: Uint8Array.from(atob(challenge), c => c.charCodeAt(0)),
          rpId: 'localhost',
          userVerification: 'preferred',
        },
      });

      const response = await api.post('/auth/verify-2fa', {
        username,
        credential: {
          id: assertion.id,
          rawId: btoa(String.fromCharCode(...new Uint8Array(assertion.rawId))),
          response: {
            clientDataJSON: btoa(String.fromCharCode(...new Uint8Array(assertion.response.clientDataJSON))),
            authenticatorData: btoa(String.fromCharCode(...new Uint8Array(assertion.response.authenticatorData))),
            signature: btoa(String.fromCharCode(...new Uint8Array(assertion.response.signature))),
            userHandle: assertion.response.userHandle ? btoa(String.fromCharCode(...new Uint8Array(assertion.response.userHandle))) : null,
          },
          type: assertion.type,
        },
      });

      const { access_token, refresh_token } = response.data;

      document.cookie = `access_token=${access_token}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
      document.cookie = `refresh_token=${refresh_token}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;

      router.push('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'WebAuthn authentication failed.');
      setErrorTrigger(prev => prev + 1);
    } finally {
      setLoading(false);
    }
  };

  const handleOIDCLogin = async (providerId: number) => {
    try {
      const response = await api.get(`/auth/oidc/authorize/${providerId}`);
      const { authorization_url, state } = response.data;

      window.location.href = `${authorization_url}&provider_id=${providerId}`;
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to initiate OIDC login');
      setErrorTrigger(prev => prev + 1);
    }
  };

  if (checkingForwardAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary mb-4" />
          <p className="text-muted-foreground">Checking authentication...</p>
        </div>
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
        className="fixed bottom-6 right-6 z-50 p-4 rounded-full bg-gradient-to-br from-[#27272a] to-[#3b82f6] hover:shadow-2xl hover:scale-110 transition-all duration-300 shadow-xl"
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
          <h2 className="text-2xl font-bold text-foreground mb-6 text-center">
            {requires2FA ? 'Two-Factor Authentication' : 'Welcome Back'}
          </h2>

          {!requires2FA ? (
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
                  "bg-gradient-to-r from-[#27272a] to-[#3b82f6]",
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

            {oidcProviders.length > 0 && (
              <>
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-border"></div>
                  </div>
                  <div className="relative flex justify-center text-sm">
                    <span className="px-2 bg-card text-muted-foreground">
                      Or continue with
                    </span>
                  </div>
                </div>

                <div className="space-y-3">
                  {oidcProviders.map((provider) => (
                    <button
                      key={provider.id}
                      type="button"
                      onClick={() => handleOIDCLogin(provider.id)}
                      className={cn(
                        "w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg",
                        "bg-background border-2 border-input",
                        "text-foreground font-medium text-base",
                        "hover:bg-accent hover:border-primary",
                        "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
                        "transition-all"
                      )}
                    >
                      {provider.button_icon && (
                        <span className="text-lg">{provider.button_icon}</span>
                      )}
                      {provider.button_text || `Sign in with ${provider.name}`}
                    </button>
                  ))}
                </div>
              </>
            )}

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
        ) : (
          <div className="space-y-6">
            {error && (
              <div
                key={errorTrigger}
                className="rounded-lg bg-destructive/10 border border-destructive/50 p-4 animate-shake"
              >
                <div className="text-sm text-destructive font-medium">{error}</div>
              </div>
            )}

            <p className="text-sm text-muted-foreground text-center">
              Please verify your identity using one of the following methods:
            </p>

            {totpEnabled && (
              <div className="space-y-4">
                <div>
                  <label htmlFor="totp-code" className="block text-sm font-semibold text-foreground mb-2">
                    Authenticator Code
                  </label>
                  <input
                    id="totp-code"
                    name="totp-code"
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={6}
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value.replace(/[^0-9]/g, ''))}
                    className={cn(
                      "w-full px-4 py-3 rounded-lg text-center text-2xl tracking-widest",
                      "bg-background border-2 border-input",
                      "text-foreground placeholder:text-muted-foreground",
                      "focus:outline-none focus:border-primary focus:ring-4 focus:ring-ring/20",
                      "transition-all duration-200"
                    )}
                    placeholder="000000"
                    autoFocus
                  />
                </div>
                <button
                  type="button"
                  onClick={handleVerify2FA}
                  disabled={loading || totpCode.length !== 6}
                  className={cn(
                    "w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg",
                    "bg-gradient-to-r from-[#27272a] to-[#3b82f6]",
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
                      Verifying...
                    </>
                  ) : (
                    <>Verify Code</>
                  )}
                </button>
              </div>
            )}

            {totpEnabled && webauthnEnabled && (
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-border"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-card text-muted-foreground">Or</span>
                </div>
              </div>
            )}

            {webauthnEnabled && (
              <button
                type="button"
                onClick={handleWebAuthnAuth}
                disabled={loading}
                className={cn(
                  "w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg",
                  "bg-background border-2 border-input",
                  "text-foreground font-medium text-base",
                  "hover:bg-accent hover:border-primary",
                  "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                  "transition-all"
                )}
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Authenticating...
                  </>
                ) : (
                  <>Use Security Key</>
                )}
              </button>
            )}

            <button
              type="button"
              onClick={() => {
                setRequires2FA(false);
                setTotpCode('');
                setError('');
              }}
              className="w-full text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Back to login
            </button>
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
