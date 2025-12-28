"use client";

import { useState, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { User, Shield, Eye, EyeOff, Check, X, Loader2, Key } from "lucide-react";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import TwoFactorSettings from "@/components/TwoFactorSettings";

type ProfileSection = 'account' | 'security';

interface UserData {
  id: number;
  username: string;
  email?: string;
  groups?: { id: number; name: string; displayName: string; color?: string }[];
  createdAt: string;
}

function PasswordChangeSection() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const passwordRequirements = [
    { label: 'At least 8 characters', met: newPassword.length >= 8 },
    { label: 'Passwords match', met: newPassword.length > 0 && newPassword === confirmPassword },
  ];

  const allRequirementsMet = passwordRequirements.every(req => req.met);
  const canSubmit = currentPassword.length > 0 && allRequirementsMet && !isSubmitting;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setIsSubmitting(true);
    setMessage(null);

    try {
      await api.post('/auth/change-password', {
        currentPassword,
        newPassword,
      });

      setMessage({ type: 'success', text: 'Password changed successfully' });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to change password',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <Key className="w-6 h-6" />
        Change Password
      </h2>

      <form onSubmit={handleSubmit} className="space-y-6 max-w-md">
        {message && (
          <div
            className={`p-4 rounded-lg ${
              message.type === 'success'
                ? 'bg-green-500/10 border border-green-500/20 text-green-400'
                : 'bg-red-500/10 border border-red-500/20 text-red-400'
            }`}
          >
            {message.text}
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-2">
            Current Password
          </label>
          <div className="relative">
            <input
              type={showCurrentPassword ? 'text' : 'password'}
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full px-4 py-3 bg-background border border-border rounded-lg pr-12 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              placeholder="Enter current password"
            />
            <button
              type="button"
              onClick={() => setShowCurrentPassword(!showCurrentPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
            >
              {showCurrentPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-2">
            New Password
          </label>
          <div className="relative">
            <input
              type={showNewPassword ? 'text' : 'password'}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-4 py-3 bg-background border border-border rounded-lg pr-12 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              placeholder="Enter new password"
            />
            <button
              type="button"
              onClick={() => setShowNewPassword(!showNewPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
            >
              {showNewPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-2">
            Confirm New Password
          </label>
          <div className="relative">
            <input
              type={showConfirmPassword ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-4 py-3 bg-background border border-border rounded-lg pr-12 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              placeholder="Confirm new password"
            />
            <button
              type="button"
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
            >
              {showConfirmPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
        </div>

        <div className="bg-background border border-border rounded-lg p-4">
          <p className="text-sm font-medium text-muted-foreground mb-3">Password Requirements</p>
          <ul className="space-y-2">
            {passwordRequirements.map((req, index) => (
              <li key={index} className="flex items-center gap-2 text-sm">
                {req.met ? (
                  <Check className="w-4 h-4 text-green-500" />
                ) : (
                  <X className="w-4 h-4 text-muted-foreground" />
                )}
                <span className={req.met ? 'text-green-500' : 'text-muted-foreground'}>
                  {req.label}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <button
          type="submit"
          disabled={!canSubmit}
          className="w-full py-3 bg-primary text-primary-foreground rounded-lg font-medium transition-all hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 cursor-pointer"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Changing Password...
            </>
          ) : (
            'Change Password'
          )}
        </button>
      </form>
    </div>
  );
}

function ProfileContent() {
  const searchParams = useSearchParams();
  const initialSection = searchParams?.get('section') === 'security' ? 'security' : 'account';
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
    { id: 'security' as ProfileSection, label: 'Security', icon: Shield },
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
                        Groups
                      </label>
                      <div className="px-4 py-3 bg-background border border-border rounded-lg flex flex-wrap gap-2">
                        {user.groups?.length > 0 ? (
                          user.groups.map((group: { id: number; name: string; displayName: string; color?: string }) => (
                            <span
                              key={group.id}
                              className="inline-flex items-center px-3 py-1 rounded-md text-sm font-medium border"
                              style={{
                                backgroundColor: group.color ? `${group.color}20` : undefined,
                                color: group.color,
                                borderColor: group.color ? `${group.color}50` : undefined,
                              }}
                            >
                              {group.displayName}
                            </span>
                          ))
                        ) : (
                          <span className="inline-flex items-center px-3 py-1 rounded-md text-sm font-medium bg-muted text-muted-foreground border border-border">
                            No groups assigned
                          </span>
                        )}
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
                        {new Date(user.createdAt).toLocaleDateString('en-US', {
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

          {selectedSection === 'security' && (
            <div className="space-y-6">
              <PasswordChangeSection />
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
