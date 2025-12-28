"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import api from "@/lib/api";

function OIDCCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(true);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        const code = searchParams.get("code");
        const state = searchParams.get("state");
        const providerId = searchParams.get("provider_id");

        if (!code || !state || !providerId) {
          setError("Missing required parameters from OIDC provider");
          setIsProcessing(false);
          return;
        }

        const response = await api.post("/auth/oidc/callback", {
          provider_id: parseInt(providerId),
          code,
          state,
        });

        const { access_token, refresh_token } = response.data;

        document.cookie = `access_token=${access_token}; path=/; max-age=${7 * 24 * 60 * 60}; SameSite=Lax`;
        document.cookie = `refresh_token=${refresh_token}; path=/; max-age=${30 * 24 * 60 * 60}; SameSite=Lax`;

        window.dispatchEvent(new Event('auth:login'));
        router.push("/");
      } catch (err: any) {
        console.error("OIDC callback error:", err);
        setError(
          err.response?.data?.detail || "Failed to complete OIDC authentication"
        );
        setIsProcessing(false);
      }
    };

    handleCallback();
  }, [searchParams, router]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="max-w-md w-full bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 p-8">
          <h1 className="text-2xl font-bold text-white mb-4">
            Authentication Failed
          </h1>
          <p className="text-red-400 mb-6">{error}</p>
          <button
            onClick={() => router.push("/login")}
            className="w-full py-3 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors cursor-pointer"
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="max-w-md w-full bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 p-8">
        <div className="flex flex-col items-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mb-4"></div>
          <h2 className="text-xl font-semibold text-white mb-2">
            {isProcessing ? "Completing authentication..." : "Redirecting..."}
          </h2>
          <p className="text-gray-400 text-center">Please wait</p>
        </div>
      </div>
    </div>
  );
}

function LoadingFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="max-w-md w-full bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 p-8">
        <div className="flex flex-col items-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mb-4"></div>
          <h2 className="text-xl font-semibold text-white mb-2">Loading...</h2>
          <p className="text-gray-400 text-center">Please wait</p>
        </div>
      </div>
    </div>
  );
}

export default function OIDCCallbackPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <OIDCCallbackContent />
    </Suspense>
  );
}
