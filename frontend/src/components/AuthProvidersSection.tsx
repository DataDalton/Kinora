"use client";

import { useState, useEffect } from "react";
import { Loader2, Link as LinkIcon, Unlink, Shield, CheckCircle } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface AuthProvider {
  id: number;
  user_id: number;
  provider_type: string;
  provider_name: string;
  provider_subject: string;
  provider_username?: string;
  linked_at: string;
  last_used_at: string;
}

export default function AuthProvidersSection() {
  const [providers, setProviders] = useState<AuthProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unlinkingId, setUnlinkingId] = useState<number | null>(null);

  useEffect(() => {
    fetchProviders();
  }, []);

  const fetchProviders = async () => {
    try {
      setLoading(true);
      const response = await api.get("/auth/me/auth-providers");
      setProviders(response.data);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load auth providers");
    } finally {
      setLoading(false);
    }
  };

  const handleUnlink = async (providerId: number) => {
    if (!confirm("Are you sure you want to unlink this authentication provider?")) {
      return;
    }

    try {
      setUnlinkingId(providerId);
      await api.delete(`/auth/me/auth-providers/${providerId}`);
      setProviders(providers.filter((p) => p.id !== providerId));
    } catch (err: any) {
      alert(
        err.response?.data?.detail ||
          "Failed to unlink provider. Make sure you have at least one authentication method."
      );
    } finally {
      setUnlinkingId(null);
    }
  };

  const getProviderDisplayName = (provider: AuthProvider) => {
    if (provider.provider_type === "forward_auth") {
      return `${provider.provider_name} (Forward Auth)`;
    }
    if (provider.provider_type === "oidc") {
      return `${provider.provider_name} (OIDC)`;
    }
    return provider.provider_name;
  };

  const getProviderIcon = (provider: AuthProvider) => {
    if (provider.provider_type === "forward_auth") {
      return <Shield className="w-5 h-5" />;
    }
    return <LinkIcon className="w-5 h-5" />;
  };

  if (loading) {
    return (
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-bold text-foreground mb-4">
          Linked Authentication Providers
        </h2>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <h2 className="text-xl font-bold text-foreground mb-2">
        Linked Authentication Providers
      </h2>
      <p className="text-sm text-muted-foreground mb-6">
        Manage authentication methods linked to your account
      </p>

      {error && (
        <div className="mb-4 p-4 bg-destructive/10 border border-destructive/50 rounded-lg">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      )}

      {providers.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          <p className="text-sm">No external authentication providers linked</p>
          <p className="text-xs mt-2">
            You are currently using local username/password authentication
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {providers.map((provider) => (
            <div
              key={provider.id}
              className={cn(
                "flex items-center justify-between p-4 rounded-lg",
                "bg-background border border-input",
                "transition-all"
              )}
            >
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-primary/10 text-primary">
                  {getProviderIcon(provider)}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-foreground">
                      {getProviderDisplayName(provider)}
                    </h3>
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  </div>
                  {provider.provider_username && (
                    <p className="text-sm text-muted-foreground">
                      {provider.provider_username}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground mt-1">
                    Last used:{" "}
                    {new Date(provider.last_used_at).toLocaleDateString()}
                  </p>
                </div>
              </div>

              <button
                onClick={() => handleUnlink(provider.id)}
                disabled={unlinkingId === provider.id}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-lg",
                  "bg-destructive/10 hover:bg-destructive/20 text-destructive",
                  "font-medium text-sm transition-all",
                  "cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                )}
              >
                {unlinkingId === provider.id ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Unlinking...
                  </>
                ) : (
                  <>
                    <Unlink className="w-4 h-4" />
                    Unlink
                  </>
                )}
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="mt-6 p-4 bg-muted/30 border border-border rounded-lg">
        <p className="text-xs text-muted-foreground">
          <strong>Note:</strong> You must have at least one authentication method
          (local password or linked provider) to access your account. If you unlink
          all external providers, make sure you have a password set.
        </p>
      </div>
    </div>
  );
}
