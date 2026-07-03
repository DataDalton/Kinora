"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Edit, Trash2, Globe } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface OIDCProvider {
	id: number;
	name: string;
	provider_url: string;
	client_id: string;
	client_secret: string;
	redirect_uri: string;
	scopes: string;
	enabled: boolean;
	button_text?: string;
}

export default function OIDCProvidersManagement() {
	const queryClient = useQueryClient();
	const [showModal, setShowModal] = useState(false);
	const [editingProvider, setEditingProvider] = useState<OIDCProvider | null>(
		null,
	);
	const [formData, setFormData] = useState<Partial<OIDCProvider>>({
		name: "",
		provider_url: "",
		client_id: "",
		client_secret: "",
		redirect_uri: `${window.location.origin}/auth/oidc/callback`,
		scopes: "openid profile",
		enabled: true,
		button_text: "",
	});

	const { data: providers, isLoading } = useQuery<OIDCProvider[]>({
		queryKey: ["oidc-providers-admin"],
		queryFn: async () => {
			const response = await api.get("/auth/oidc/providers");
			return response.data;
		},
	});

	const createMutation = useMutation({
		mutationFn: async (data: Partial<OIDCProvider>) => {
			const response = await api.post("/auth/oidc/providers", data);
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: ["oidc-providers-admin"],
			});
			setShowModal(false);
			resetForm();
		},
	});

	const updateMutation = useMutation({
		mutationFn: async ({
			id,
			data,
		}: {
			id: number;
			data: Partial<OIDCProvider>;
		}) => {
			const response = await api.put(`/auth/oidc/providers/${id}`, data);
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: ["oidc-providers-admin"],
			});
			setShowModal(false);
			setEditingProvider(null);
			resetForm();
		},
	});

	const deleteMutation = useMutation({
		mutationFn: async (id: number) => {
			await api.delete(`/auth/oidc/providers/${id}`);
		},
		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: ["oidc-providers-admin"],
			});
		},
	});

	const resetForm = () => {
		setFormData({
			name: "",
			provider_url: "",
			client_id: "",
			client_secret: "",
			redirect_uri: `${window.location.origin}/auth/oidc/callback`,
			scopes: "openid profile",
			enabled: true,
			button_text: "",
		});
	};

	const handleEdit = (provider: OIDCProvider) => {
		setEditingProvider(provider);
		setFormData(provider);
		setShowModal(true);
	};

	const handleDelete = (id: number) => {
		if (confirm("Are you sure you want to delete this OIDC provider?")) {
			deleteMutation.mutate(id);
		}
	};

	const handleSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		if (editingProvider) {
			updateMutation.mutate({ id: editingProvider.id, data: formData });
		} else {
			createMutation.mutate(formData);
		}
	};

	if (isLoading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Loader2 className="w-8 h-8 animate-spin text-primary" />
			</div>
		);
	}

	return (
		<div>
			<div className="flex justify-between items-center mb-6">
				<div>
					<h2 className="text-xl font-bold">OIDC/SSO Providers</h2>
					<p className="text-sm text-muted-foreground mt-1">
						Configure OAuth2/OIDC providers for single sign-on
					</p>
				</div>
				<button
					onClick={() => {
						setEditingProvider(null);
						resetForm();
						setShowModal(true);
					}}
					className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition cursor-pointer"
				>
					<Plus className="w-4 h-4" />
					Add Provider
				</button>
			</div>

			{providers && providers.length > 0 ? (
				<div className="space-y-4">
					{providers.map((provider) => (
						<div
							key={provider.id}
							className="bg-card border border-border rounded-lg p-6"
						>
							<div className="flex justify-between items-start">
								<div className="flex-1">
									<div className="flex items-center gap-3 mb-3">
										<div className="p-2 bg-primary/10 rounded-lg">
											<Globe className="w-5 h-5 text-primary" />
										</div>
										<div>
											<h3 className="text-lg font-semibold">
												{provider.name}
											</h3>
											<p className="text-sm text-muted-foreground">
												{provider.provider_url}
											</p>
										</div>
										<span
											className={cn(
												"px-2 py-1 text-xs rounded-full font-medium",
												provider.enabled
													? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
													: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
											)}
										>
											{provider.enabled
												? "Enabled"
												: "Disabled"}
										</span>
									</div>

									<div className="grid grid-cols-2 gap-4 text-sm">
										<div>
											<span className="text-muted-foreground">
												Client ID:
											</span>
											<p className="font-mono text-xs mt-1 break-all">
												{provider.client_id}
											</p>
										</div>
										<div>
											<span className="text-muted-foreground">
												Redirect URI:
											</span>
											<p className="font-mono text-xs mt-1 break-all">
												{provider.redirect_uri}
											</p>
										</div>
										<div>
											<span className="text-muted-foreground">
												Scopes:
											</span>
											<p className="font-mono text-xs mt-1">
												{provider.scopes}
											</p>
										</div>
										{provider.button_text && (
											<div>
												<span className="text-muted-foreground">
													Button Text:
												</span>
												<p className="text-xs mt-1">
													{provider.button_text}
												</p>
											</div>
										)}
									</div>
								</div>

								<div className="flex gap-2 ml-4">
									<button
										onClick={() => handleEdit(provider)}
										className="p-2 bg-primary/10 hover:bg-primary/20 text-primary rounded-lg transition cursor-pointer"
									>
										<Edit className="w-4 h-4" />
									</button>
									<button
										onClick={() =>
											handleDelete(provider.id)
										}
										className="p-2 bg-destructive/10 hover:bg-destructive/20 text-destructive rounded-lg transition cursor-pointer"
									>
										<Trash2 className="w-4 h-4" />
									</button>
								</div>
							</div>
						</div>
					))}
				</div>
			) : (
				<div className="text-center py-12 bg-card border border-border rounded-lg">
					<Globe className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
					<p className="text-muted-foreground mb-4">
						No OIDC providers configured
					</p>
					<p className="text-sm text-muted-foreground max-w-md mx-auto">
						Add an OIDC provider to enable single sign-on with
						services like Google, Microsoft, Keycloak, or Authentik
					</p>
				</div>
			)}

			{/* Modal */}
			{showModal && (
				<div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-50 flex items-center justify-center p-4">
					<div className="bg-background rounded-lg max-w-2xl w-full border border-border shadow-2xl p-6 max-h-[90vh] overflow-y-auto">
						<h2 className="text-2xl font-bold mb-6">
							{editingProvider
								? "Edit OIDC Provider"
								: "Add OIDC Provider"}
						</h2>

						<form onSubmit={handleSubmit} className="space-y-4">
							<div>
								<label className="block text-sm font-medium mb-1">
									Provider Name *
								</label>
								<input
									type="text"
									required
									value={formData.name || ""}
									onChange={(e) =>
										setFormData({
											...formData,
											name: e.target.value,
										})
									}
									className="w-full px-4 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
									placeholder="e.g., Google, Keycloak, Authentik"
								/>
							</div>

							<div>
								<label className="block text-sm font-medium mb-1">
									Provider URL (Discovery Endpoint) *
								</label>
								<input
									type="url"
									required
									value={formData.provider_url || ""}
									onChange={(e) =>
										setFormData({
											...formData,
											provider_url: e.target.value,
										})
									}
									className="w-full px-4 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
									placeholder="https://accounts.google.com"
								/>
								<p className="text-xs text-muted-foreground mt-1">
									Base URL for OIDC discovery (without
									/.well-known/openid-configuration)
								</p>
							</div>

							<div className="grid grid-cols-2 gap-4">
								<div>
									<label className="block text-sm font-medium mb-1">
										Client ID *
									</label>
									<input
										type="text"
										required
										value={formData.client_id || ""}
										onChange={(e) =>
											setFormData({
												...formData,
												client_id: e.target.value,
											})
										}
										className="w-full px-4 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
									/>
								</div>

								<div>
									<label className="block text-sm font-medium mb-1">
										Client Secret *
									</label>
									<input
										type="password"
										required
										value={formData.client_secret || ""}
										onChange={(e) =>
											setFormData({
												...formData,
												client_secret: e.target.value,
											})
										}
										className="w-full px-4 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
									/>
								</div>
							</div>

							<div>
								<label className="block text-sm font-medium mb-1">
									Redirect URI *
								</label>
								<input
									type="url"
									required
									value={formData.redirect_uri || ""}
									onChange={(e) =>
										setFormData({
											...formData,
											redirect_uri: e.target.value,
										})
									}
									className="w-full px-4 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
								/>
								<p className="text-xs text-muted-foreground mt-1">
									Configure this URL in your OIDC provider
									settings
								</p>
							</div>

							<div>
								<label className="block text-sm font-medium mb-1">
									Scopes
								</label>
								<input
									type="text"
									value={formData.scopes || ""}
									onChange={(e) =>
										setFormData({
											...formData,
											scopes: e.target.value,
										})
									}
									className="w-full px-4 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
									placeholder="openid profile email"
								/>
							</div>

							<div>
								<label className="block text-sm font-medium mb-1">
									Button Text (Optional)
								</label>
								<input
									type="text"
									value={formData.button_text || ""}
									onChange={(e) =>
										setFormData({
											...formData,
											button_text: e.target.value,
										})
									}
									className="w-full px-4 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
									placeholder="Sign in with Provider"
								/>
							</div>

							<label className="flex items-center justify-between p-3 bg-muted/50 rounded-lg cursor-pointer">
								<div>
									<div className="font-semibold">Enabled</div>
									<div className="text-xs text-muted-foreground">
										Show this provider on the login page
									</div>
								</div>
								<div className="relative inline-flex items-center">
									<input
										type="checkbox"
										checked={formData.enabled || false}
										onChange={(e) =>
											setFormData({
												...formData,
												enabled: e.target.checked,
											})
										}
										className="sr-only peer"
									/>
									<div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
								</div>
							</label>

							<div className="flex gap-3 pt-4">
								<button
									type="submit"
									disabled={
										createMutation.isPending ||
										updateMutation.isPending
									}
									className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 transition cursor-pointer"
								>
									{createMutation.isPending ||
									updateMutation.isPending
										? "Saving..."
										: editingProvider
											? "Update Provider"
											: "Add Provider"}
								</button>
								<button
									type="button"
									onClick={() => {
										setShowModal(false);
										setEditingProvider(null);
										resetForm();
									}}
									className="px-6 py-3 bg-muted text-foreground rounded-lg hover:opacity-90 transition cursor-pointer"
								>
									Cancel
								</button>
							</div>
						</form>
					</div>
				</div>
			)}
		</div>
	);
}
