"use client";

import { useState, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { User, Shield } from "lucide-react";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import TwoFactorSettings from "@/components/TwoFactorSettings";

type ProfileSection = 'account' | '2fa';

interface UserData {
  id: number;
  username: string;
  email?: string;
  role: string;
  created_at: string;
}

function ProfileContent() {
  const searchParams = useSearchParams();
  const initialSection = searchParams?.get('section') === '2fa' ? '2fa' : 'account';
  const [selectedSection, setSelectedSection] = useState<ProfileSection>(initialSection);

  const { data: user, isLoading } = useQuery<UserData>({
    queryKey: ["current-user"],
    queryFn: async () => {
      const response = await api.get("/auth/me");
      return response.data;
    },
  });

  const sections = [
    { id: 'account' as ProfileSection, label: 'Account', icon: User },
    { id: '2fa' as ProfileSection, label: 'Security', icon: Shield },
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <PageHeader
        title="User Profile"
        description="Manage your account settings and security"
        gradientFrom="indigo-600/10"
        gradientVia="purple-600/10"
        gradientTo="pink-600/10"
      />

      <div className="grid grid-cols-12 gap-6 mt-6">
        <div className="col-span-12 lg:col-span-3">
          <div className="bg-card border border-border rounded-lg p-4">
            <nav className="space-y-1">
              {sections.map((section) => {
                const Icon = section.icon;
                return (
                  <button
                    key={section.id}
                    onClick={() => setSelectedSection(section.id)}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all cursor-pointer ${
                      selectedSection === section.id
                        ? 'bg-primary text-primary-foreground shadow-md'
                        : 'text-foreground/70 hover:text-foreground hover:bg-accent'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    <span className="font-medium">{section.label}</span>
                  </button>
                );
              })}
            </nav>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-9">
          {selectedSection === 'account' && (
            <div className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
                <User className="w-6 h-6" />
                Account Information
              </h2>

              {isLoading ? (
                <div className="text-center py-8 text-muted-foreground">Loading...</div>
              ) : user ? (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-sm font-medium text-muted-foreground mb-2">
                        Username
                      </label>
                      <div className="px-4 py-3 bg-background border border-border rounded-lg">
                        {user.username}
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-muted-foreground mb-2">
                        Role
                      </label>
                      <div className="px-4 py-3 bg-background border border-border rounded-lg">
                        <span className={`inline-flex items-center px-3 py-1 rounded-md text-sm font-medium ${
                          user.role === 'administrator'
                            ? 'bg-primary/20 text-primary border border-primary/30'
                            : 'bg-muted text-muted-foreground border border-border'
                        }`}>
                          {user.role === 'administrator' ? 'Administrator' : 'User'}
                        </span>
                      </div>
                    </div>

                    {user.email && (
                      <div className="md:col-span-2">
                        <label className="block text-sm font-medium text-muted-foreground mb-2">
                          Email
                        </label>
                        <div className="px-4 py-3 bg-background border border-border rounded-lg">
                          {user.email}
                        </div>
                      </div>
                    )}

                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-muted-foreground mb-2">
                        Member Since
                      </label>
                      <div className="px-4 py-3 bg-background border border-border rounded-lg">
                        {new Date(user.created_at).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric',
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  Failed to load user information
                </div>
              )}
            </div>
          )}

          {selectedSection === '2fa' && (
            <div>
              <TwoFactorSettings />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function LoadingFallback() {
  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="animate-pulse">
        <div className="h-8 bg-muted rounded w-48 mb-4"></div>
        <div className="h-4 bg-muted rounded w-64 mb-6"></div>
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-3">
            <div className="bg-card border border-border rounded-lg p-4 h-32"></div>
          </div>
          <div className="col-span-12 lg:col-span-9">
            <div className="bg-card border border-border rounded-lg p-6 h-64"></div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ProfilePage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <ProfileContent />
    </Suspense>
  );
}
