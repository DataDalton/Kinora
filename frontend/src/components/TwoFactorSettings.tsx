"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
	Loader2,
	Shield,
	Key,
	Smartphone,
	Trash2,
	Plus,
	AlertCircle,
	CheckCircle,
	Copy,
	Download,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface TOTPStatus {
	enabled: boolean;
	created_at?: string;
	verified_at?: string;
}

interface WebAuthnCredential {
	id: number;
	credential_id: string;
	name?: string;
	created_at: string;
	last_used_at?: string;
}

interface TwoFactorStatus {
	totp_enabled: boolean;
	webauthn_enabled: boolean;
	webauthn_credentials_count: number;
}

interface TOTPSetupData {
	secret: string;
	qr_code_url: string;
	backup_codes: string[];
}

function base64urlToUint8Array(base64url: string): Uint8Array {
	const base64 = base64url.replace(/-/g, "+").replace(/_/g, "/");
	const paddedBase64 = base64.padEnd(
		base64.length + ((4 - (base64.length % 4)) % 4),
		"=",
	);
	const binary = atob(paddedBase64);
	return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

export default function TwoFactorSettings() {
	const queryClient = useQueryClient();
	const [showTOTPSetup, setShowTOTPSetup] = useState(false);
	const [totpSetupData, setTotpSetupData] = useState<TOTPSetupData | null>(
		null,
	);
	const [verifyCode, setVerifyCode] = useState("");
	const [disableCode, setDisableCode] = useState("");
	const [showDisableModal, setShowDisableModal] = useState(false);
	const [webauthnName, setWebauthnName] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [success, setSuccess] = useState<string | null>(null);

	const { data: status, isLoading: statusLoading } =
		useQuery<TwoFactorStatus>({
			queryKey: ["2fa-status"],
			queryFn: async () => {
				const response = await api.get("/2fa/status");
				return response.data;
			},
		});

	const { data: webauthnCredentials, isLoading: credentialsLoading } =
		useQuery<WebAuthnCredential[]>({
			queryKey: ["webauthn-credentials"],
			queryFn: async () => {
				const response = await api.get("/2fa/webauthn/credentials");
				return response.data;
			},
		});

	const setupTOTPMutation = useMutation({
		mutationFn: async () => {
			const response = await api.post("/2fa/totp/setup");
			return response.data;
		},
		onSuccess: (data) => {
			setTotpSetupData(data);
			setShowTOTPSetup(true);
			setError(null);
		},
		onError: (err: any) => {
			setError(err.response?.data?.detail || "Failed to setup TOTP");
		},
	});

	const verifyTOTPMutation = useMutation({
		mutationFn: async (code: string) => {
			const response = await api.post("/2fa/totp/verify", { code });
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["2fa-status"] });
			setShowTOTPSetup(false);
			setTotpSetupData(null);
			setVerifyCode("");
			setSuccess("TOTP enabled successfully!");
			setTimeout(() => setSuccess(null), 3000);
		},
		onError: (err: any) => {
			setError(err.response?.data?.detail || "Invalid TOTP code");
		},
	});

	const disableTOTPMutation = useMutation({
		mutationFn: async (code: string) => {
			const response = await api.post("/2fa/totp/disable", { code });
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["2fa-status"] });
			setShowDisableModal(false);
			setDisableCode("");
			setError(null);
			setSuccess("TOTP disabled successfully!");
			setTimeout(() => setSuccess(null), 3000);
		},
		onError: (err: any) => {
			setError(err.response?.data?.detail || "Invalid TOTP code");
		},
	});

	const registerWebAuthnMutation = useMutation({
		mutationFn: async (name: string) => {
			const startResponse = await api.post(
				"/2fa/webauthn/register/start",
				{ name },
			);
			const options = startResponse.data.options;

			const credential = (await navigator.credentials.create({
				publicKey: {
					...options,
					challenge: base64urlToUint8Array(options.challenge),
					user: {
						...options.user,
						id: base64urlToUint8Array(options.user.id),
					},
				},
			})) as PublicKeyCredential | null;

			if (!credential) {
				throw new Error("Failed to create credential");
			}

			const attestationResponse =
				credential.response as AuthenticatorAttestationResponse;

			const response = await api.post("/2fa/webauthn/register/verify", {
				credential: {
					id: credential.id,
					rawId: btoa(
						String.fromCharCode(
							...new Uint8Array(credential.rawId),
						),
					),
					response: {
						clientDataJSON: btoa(
							String.fromCharCode(
								...new Uint8Array(
									attestationResponse.clientDataJSON,
								),
							),
						),
						attestationObject: btoa(
							String.fromCharCode(
								...new Uint8Array(
									attestationResponse.attestationObject,
								),
							),
						),
					},
					type: credential.type,
				},
				name,
			});

			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: ["webauthn-credentials"],
			});
			queryClient.invalidateQueries({ queryKey: ["2fa-status"] });
			setWebauthnName("");
			setSuccess("Security key registered successfully!");
			setTimeout(() => setSuccess(null), 3000);
		},
		onError: (err: any) => {
			console.error("WebAuthn error:", err);
			setError(
				err.response?.data?.detail ||
					err.message ||
					"Failed to register security key",
			);
		},
	});

	const deleteWebAuthnMutation = useMutation({
		mutationFn: async (id: number) => {
			await api.delete(`/2fa/webauthn/credentials/${id}`);
		},
		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: ["webauthn-credentials"],
			});
			queryClient.invalidateQueries({ queryKey: ["2fa-status"] });
			setSuccess("Security key removed successfully!");
			setTimeout(() => setSuccess(null), 3000);
		},
		onError: (err: any) => {
			setError(
				err.response?.data?.detail || "Failed to remove security key",
			);
		},
	});

	const handleCopyBackupCodes = () => {
		if (totpSetupData) {
			navigator.clipboard.writeText(
				totpSetupData.backup_codes.join("\n"),
			);
			setSuccess("Backup codes copied to clipboard!");
			setTimeout(() => setSuccess(null), 2000);
		}
	};

	const handleDownloadBackupCodes = () => {
		if (totpSetupData) {
			const blob = new Blob([totpSetupData.backup_codes.join("\n")], {
				type: "text/plain",
			});
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			a.download = "kinora-backup-codes.txt";
			a.click();
			URL.revokeObjectURL(url);
		}
	};

	if (statusLoading) {
		return (
			<div className="bg-card border border-border rounded-lg p-6">
				<div className="flex items-center justify-center py-8">
					<Loader2 className="w-6 h-6 animate-spin text-primary" />
				</div>
			</div>
		);
	}

	return (
		<div className="space-y-6">
			{/* Status Messages (hidden while the disable modal is open, which shows its own error) */}
			{error && !showDisableModal && (
				<div className="p-4 bg-destructive/10 border border-destructive/50 rounded-lg flex items-center gap-2">
					<AlertCircle className="w-5 h-5 text-destructive" />
					<p className="text-sm text-destructive">{error}</p>
				</div>
			)}

			{success && (
				<div className="p-4 bg-green-100 dark:bg-green-900/30 border border-green-500 rounded-lg flex items-center gap-2">
					<CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
					<p className="text-sm text-green-800 dark:text-green-200">
						{success}
					</p>
				</div>
			)}

			{/* TOTP Section */}
			<div className="bg-card border border-border rounded-lg p-6">
				<div className="flex items-center gap-3 mb-4">
					<div className="p-2 bg-primary/10 rounded-lg">
						<Smartphone className="w-5 h-5 text-primary" />
					</div>
					<div>
						<h2 className="text-xl font-bold text-foreground">
							Authenticator App (TOTP)
						</h2>
						<p className="text-sm text-muted-foreground">
							Use apps like Google Authenticator, Authy, or
							1Password
						</p>
					</div>
				</div>

				{status?.totp_enabled ? (
					<div className="space-y-4">
						<div className="p-4 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-900 rounded-lg">
							<div className="flex items-center gap-2">
								<CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
								<p className="text-sm font-medium text-green-800 dark:text-green-200">
									TOTP is enabled and active
								</p>
							</div>
						</div>

						<button
							onClick={() => {
								setError(null);
								setShowDisableModal(true);
							}}
							className="px-4 py-2 bg-destructive text-destructive-foreground rounded-lg hover:opacity-90 transition cursor-pointer"
						>
							Disable TOTP
						</button>
					</div>
				) : showTOTPSetup && totpSetupData ? (
					<div className="space-y-4">
						<div className="p-4 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900 rounded-lg">
							<p className="text-sm text-blue-900 dark:text-blue-100 mb-3">
								Scan this QR code with your authenticator app:
							</p>
							<div className="flex justify-center mb-4">
								<img
									src={totpSetupData.qr_code_url}
									alt="TOTP QR Code"
									className="w-48 h-48"
								/>
							</div>
							<p className="text-xs text-blue-800 dark:text-blue-200 font-mono text-center mb-4">
								Or enter this key manually:{" "}
								{totpSetupData.secret}
							</p>
						</div>

						<div className="p-4 bg-yellow-50 dark:bg-yellow-950/30 border border-yellow-200 dark:border-yellow-900 rounded-lg">
							<p className="text-sm font-semibold text-yellow-900 dark:text-yellow-100 mb-2">
								Backup Recovery Codes
							</p>
							<p className="text-xs text-yellow-800 dark:text-yellow-200 mb-3">
								Save these codes in a safe place. Each can be
								used once if you lose access to your
								authenticator.
							</p>
							<div className="grid grid-cols-2 gap-2 mb-3">
								{totpSetupData.backup_codes.map((code, idx) => (
									<code
										key={idx}
										className="text-xs bg-background p-2 rounded border border-border"
									>
										{code}
									</code>
								))}
							</div>
							<div className="flex gap-2">
								<button
									onClick={handleCopyBackupCodes}
									className="flex items-center gap-2 px-3 py-1 text-sm bg-background border border-border rounded hover:bg-accent transition cursor-pointer"
								>
									<Copy className="w-4 h-4" />
									Copy
								</button>
								<button
									onClick={handleDownloadBackupCodes}
									className="flex items-center gap-2 px-3 py-1 text-sm bg-background border border-border rounded hover:bg-accent transition cursor-pointer"
								>
									<Download className="w-4 h-4" />
									Download
								</button>
							</div>
						</div>

						<div>
							<label className="block text-sm font-medium mb-2">
								Enter code from your app to verify:
							</label>
							<div className="flex gap-2">
								<input
									type="text"
									value={verifyCode}
									onChange={(e) =>
										setVerifyCode(e.target.value)
									}
									placeholder="000000"
									maxLength={6}
									className="flex-1 px-4 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
								/>
								<button
									onClick={() =>
										verifyTOTPMutation.mutate(verifyCode)
									}
									disabled={
										verifyTOTPMutation.isPending ||
										verifyCode.length !== 6
									}
									className="px-6 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 transition cursor-pointer"
								>
									{verifyTOTPMutation.isPending ? (
										<Loader2 className="w-5 h-5 animate-spin" />
									) : (
										"Verify"
									)}
								</button>
							</div>
						</div>

						<button
							onClick={() => {
								setShowTOTPSetup(false);
								setTotpSetupData(null);
								setVerifyCode("");
							}}
							className="px-4 py-2 bg-muted text-foreground rounded-lg hover:opacity-90 transition cursor-pointer"
						>
							Cancel
						</button>
					</div>
				) : (
					<button
						onClick={() => setupTOTPMutation.mutate()}
						disabled={setupTOTPMutation.isPending}
						className="px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 transition flex items-center gap-2 cursor-pointer"
					>
						{setupTOTPMutation.isPending && (
							<Loader2 className="w-5 h-5 animate-spin" />
						)}
						Setup TOTP
					</button>
				)}
			</div>

			{/* WebAuthn Section */}
			<div className="bg-card border border-border rounded-lg p-6">
				<div className="flex items-center gap-3 mb-4">
					<div className="p-2 bg-primary/10 rounded-lg">
						<Key className="w-5 h-5 text-primary" />
					</div>
					<div>
						<h2 className="text-xl font-bold text-foreground">
							Security Keys (WebAuthn/FIDO2)
						</h2>
						<p className="text-sm text-muted-foreground">
							Use hardware security keys like Yubikey or built-in
							biometrics
						</p>
					</div>
				</div>

				{credentialsLoading ? (
					<div className="flex items-center justify-center py-4">
						<Loader2 className="w-5 h-5 animate-spin text-primary" />
					</div>
				) : (
					<>
						{webauthnCredentials &&
							webauthnCredentials.length > 0 && (
								<div className="space-y-2 mb-4">
									{webauthnCredentials.map((cred) => (
										<div
											key={cred.id}
											className="flex items-center justify-between p-3 bg-background border border-border rounded-lg"
										>
											<div>
												<p className="font-medium">
													{cred.name ||
														"Security Key"}
												</p>
												<p className="text-xs text-muted-foreground">
													Added{" "}
													{new Date(
														cred.created_at,
													).toLocaleDateString()}
													{cred.last_used_at &&
														` • Last used ${new Date(cred.last_used_at).toLocaleDateString()}`}
												</p>
											</div>
											<button
												onClick={() => {
													if (
														confirm(
															"Remove this security key?",
														)
													) {
														deleteWebAuthnMutation.mutate(
															cred.id,
														);
													}
												}}
												className="p-2 hover:bg-destructive/10 text-destructive rounded transition cursor-pointer"
											>
												<Trash2 className="w-4 h-4" />
											</button>
										</div>
									))}
								</div>
							)}

						<div className="flex gap-2">
							<input
								type="text"
								value={webauthnName}
								onChange={(e) =>
									setWebauthnName(e.target.value)
								}
								placeholder="Key name (optional)"
								className="flex-1 px-4 py-2 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
							/>
							<button
								onClick={() =>
									registerWebAuthnMutation.mutate(
										webauthnName || "Security Key",
									)
								}
								disabled={registerWebAuthnMutation.isPending}
								className="px-6 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 transition flex items-center gap-2 cursor-pointer"
							>
								{registerWebAuthnMutation.isPending ? (
									<Loader2 className="w-5 h-5 animate-spin" />
								) : (
									<Plus className="w-5 h-5" />
								)}
								Add Security Key
							</button>
						</div>
					</>
				)}
			</div>

			{/* Disable TOTP Modal */}
			{showDisableModal && (
				<div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-50 flex items-center justify-center p-4">
					<div className="bg-background rounded-lg max-w-md w-full border border-border shadow-2xl p-6">
						<h2 className="text-2xl font-bold mb-4">
							Disable TOTP
						</h2>
						<p className="text-sm text-muted-foreground mb-4">
							Enter your current TOTP code or a backup code to
							disable two-factor authentication.
						</p>
						<div className="space-y-4">
							{error && (
								<div className="p-3 bg-destructive/10 border border-destructive/50 rounded-lg flex items-center gap-2">
									<AlertCircle className="w-5 h-5 text-destructive shrink-0" />
									<p className="text-sm text-destructive">
										{error}
									</p>
								</div>
							)}
							<div>
								<label className="block text-sm font-medium mb-2">
									TOTP Code or Backup Code
								</label>
								<input
									type="text"
									value={disableCode}
									onChange={(e) =>
										setDisableCode(e.target.value)
									}
									placeholder="000000 or XXXXXXXX"
									className="w-full px-4 py-3 border border-border bg-background text-foreground rounded-lg focus:ring-2 focus:ring-primary"
								/>
							</div>
							<div className="flex gap-3 pt-4">
								<button
									onClick={() =>
										disableTOTPMutation.mutate(disableCode)
									}
									disabled={
										disableTOTPMutation.isPending ||
										!disableCode
									}
									className="flex-1 px-6 py-3 bg-destructive text-destructive-foreground rounded-lg hover:opacity-90 disabled:opacity-50 transition cursor-pointer"
								>
									{disableTOTPMutation.isPending
										? "Disabling..."
										: "Disable TOTP"}
								</button>
								<button
									onClick={() => {
										setShowDisableModal(false);
										setDisableCode("");
										setError(null);
									}}
									className="px-6 py-3 bg-muted text-foreground rounded-lg hover:opacity-90 transition cursor-pointer"
								>
									Cancel
								</button>
							</div>
						</div>
					</div>
				</div>
			)}
		</div>
	);
}
