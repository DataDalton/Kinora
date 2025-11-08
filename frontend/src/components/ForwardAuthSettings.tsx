"use client";

import { useState, useEffect } from "react";
import { Loader2, Shield, Plus, X, Info } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function ForwardAuthSettings() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [trustedProxies, setTrustedProxies] = useState<string[]>([]);
  const [newProxy, setNewProxy] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const defaultRanges = [
    "127.0.0.1/32",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
  ];

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const response = await api.get("/settings/forward_auth_trusted_proxies");
      const value = response.data?.value;

      if (value) {
        try {
          const parsed = JSON.parse(value);
          setTrustedProxies(Array.isArray(parsed) ? parsed : []);
        } catch {
          setTrustedProxies([]);
        }
      } else {
        setTrustedProxies([]);
      }
    } catch (err: any) {
      if (err.response?.status === 404) {
        setTrustedProxies([]);
      } else {
        setError("Failed to load forward auth settings");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);

      const value = trustedProxies.length > 0
        ? JSON.stringify(trustedProxies)
        : null;

      if (value) {
        await api.put("/settings/forward_auth_trusted_proxies", { value });
      } else {
        try {
          await api.delete("/settings/forward_auth_trusted_proxies");
        } catch (err: any) {
          if (err.response?.status !== 404) {
            throw err;
          }
        }
      }

      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleAddProxy = () => {
    if (!newProxy.trim()) return;

    if (trustedProxies.includes(newProxy.trim())) {
      setError("This IP/range is already in the list");
      return;
    }

    setTrustedProxies([...trustedProxies, newProxy.trim()]);
    setNewProxy("");
    setError(null);
  };

  const handleRemoveProxy = (index: number) => {
    setTrustedProxies(trustedProxies.filter((_, i) => i !== index));
  };

  const handleReset = () => {
    setTrustedProxies([]);
    setError(null);
  };

  if (loading) {
    return (
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
        </div>
      </div>
    );
  }

  const usingDefaults = trustedProxies.length === 0;

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 bg-primary/10 rounded-lg">
          <Shield className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-foreground">
            Forward Auth Settings
          </h2>
          <p className="text-sm text-muted-foreground">
            Configure trusted proxy IPs for Authelia/Authentik forward authentication
          </p>
        </div>
      </div>

      <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900 rounded-lg">
        <div className="flex gap-2">
          <Info className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-blue-900 dark:text-blue-100">
            <p className="font-semibold mb-1">How Forward Auth Works:</p>
            <p className="mb-2">
              When Authelia or Authentik is configured as a reverse proxy in front of Nexarr,
              authentication headers are automatically forwarded. Nexarr will only accept these
              headers from trusted proxy IP addresses.
            </p>
            <p className="font-semibold mb-1">Default Trusted Ranges (used when list is empty):</p>
            <ul className="list-disc list-inside space-y-1 font-mono text-xs">
              {defaultRanges.map((range) => (
                <li key={range}>{range}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-destructive/10 border border-destructive/50 rounded-lg">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      )}

      {success && (
        <div className="mb-4 p-4 bg-green-100 dark:bg-green-900/30 border border-green-500 rounded-lg">
          <p className="text-sm text-green-800 dark:text-green-200">
            Settings saved successfully!
          </p>
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">
            Trusted Proxy IPs/Ranges
            {usingDefaults && (
              <span className="ml-2 text-xs text-muted-foreground">
                (Using defaults)
              </span>
            )}
          </label>

          <div className="flex gap-2 mb-3">
            <input
              type="text"
              value={newProxy}
              onChange={(e) => setNewProxy(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleAddProxy()}
              placeholder="e.g., 172.18.0.1 or 10.0.0.0/8"
              className="flex-1 px-4 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
            />
            <button
              onClick={handleAddProxy}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition flex items-center gap-2 cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              Add
            </button>
          </div>

          {trustedProxies.length > 0 ? (
            <div className="space-y-2">
              {trustedProxies.map((proxy, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-3 bg-background border border-border rounded-lg"
                >
                  <code className="text-sm font-mono">{proxy}</code>
                  <button
                    onClick={() => handleRemoveProxy(index)}
                    className="p-1 hover:bg-destructive/10 text-destructive rounded transition cursor-pointer"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-4 bg-muted/30 border border-border rounded-lg text-center">
              <p className="text-sm text-muted-foreground">
                No custom proxies configured. Using default private IP ranges.
              </p>
            </div>
          )}
        </div>

        <div className="flex gap-3 pt-4">
          <button
            onClick={handleSave}
            disabled={saving}
            className={cn(
              "px-6 py-2 bg-primary text-primary-foreground rounded-lg transition",
              "hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
            )}
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin inline mr-2" />
                Saving...
              </>
            ) : (
              "Save Settings"
            )}
          </button>

          {trustedProxies.length > 0 && (
            <button
              onClick={handleReset}
              disabled={saving}
              className="px-6 py-2 bg-muted text-foreground rounded-lg hover:opacity-90 transition cursor-pointer"
            >
              Reset to Defaults
            </button>
          )}
        </div>
      </div>

      <div className="mt-6 p-4 bg-muted/30 border border-border rounded-lg">
        <p className="text-xs text-muted-foreground">
          <strong>Security Note:</strong> Only add IP addresses that you trust. These IPs can
          authenticate users to your system via headers. Common values include your Docker
          network gateway (e.g., 172.18.0.1) or your reverse proxy's IP address.
        </p>
      </div>
    </div>
  );
}
