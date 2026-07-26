"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
	UserPlus,
	Loader2,
	Film,
	ArrowRight,
	ArrowLeft,
	Shield,
	Key,
	ChevronDown,
	ChevronUp,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import TwoFactorSettings from "@/components/TwoFactorSettings";
import HolographicGrid from "@/components/HolographicGrid";

type RegistrationStep = "credentials" | "setup" | "2fa";

export default function RegisterPage() {
	const router = useRouter();
	const [currentStep, setCurrentStep] =
		useState<RegistrationStep>("credentials");
	const [username, setUsername] = useState("");
	const [password, setPassword] = useState("");
	const [confirmPassword, setConfirmPassword] = useState("");
	const [error, setError] = useState("");
	const [loading, setLoading] = useState(false);
	const [checking, setChecking] = useState(true);

	// Inline first-run setup (shown after the security step for the first admin only).
	const [needsSetup, setNeedsSetup] = useState(false);
	const [tmdbKey, setTmdbKey] = useState("");
	const [customizeQbit, setCustomizeQbit] = useState(false);
	const [qbit, setQbit] = useState({
		name: "qBittorrent",
		host: "gluetun",
		port: 8080,
		username: "admin",
		password: "adminadmin",
		use_ssl: false,
	});
	const [setupError, setSetupError] = useState("");

	useEffect(() => {
		const checkRegistrationStatus = async () => {
			try {
				const response = await api.get("/auth/registration-status");
				if (!response.data.enabled) {
					router.push("/login?error=registration_disabled");
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
		setError("");

		if (password !== confirmPassword) {
			setError("Passwords do not match");
			return;
		}

		if (password.length < 8) {
			setError("Password must be at least 8 characters long");
			return;
		}

		setLoading(true);

		try {
			await api.post("/auth/register", {
				username,
				password,
			});

			const formData = new FormData();
			formData.append("username", username);
			formData.append("password", password);

			const loginResponse = await api.post("/auth/login", formData, {
				headers: {
					"Content-Type": "application/x-www-form-urlencoded",
				},
			});

			const { access_token, refresh_token } = loginResponse.data;

			document.cookie = `access_token=${access_token}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
			document.cookie = `refresh_token=${refresh_token}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;

			// Everyone goes to the optional security step next. The first admin with setup
			// not yet complete then continues to the inline setup step afterward. qBittorrent
			// and root folders are already auto-configured, so the only required input there
			// is the TMDB key.
			try {
				const status = await api.get("/setup/status");
				setNeedsSetup(
					!status.data.is_setup_complete && status.data.is_admin,
				);
			} catch {
				setNeedsSetup(false);
			}
			setCurrentStep("2fa");
			setLoading(false);
		} catch (err: any) {
			setError(
				err.response?.data?.detail ||
					"Registration failed. Please try again.",
			);
			setLoading(false);
		}
	};

	const handleSetup = async (e: React.FormEvent) => {
		e.preventDefault();
		setSetupError("");
		if (!tmdbKey.trim()) {
			setSetupError("A TMDB API key is required.");
			return;
		}
		setLoading(true);
		try {
			// qBittorrent is auto-configured. Only send an override when the user customized it.
			if (customizeQbit) {
				await api.post("/setup/qbittorrent", qbit);
			}
			await api.post("/setup/tmdb", { api_key: tmdbKey });
			// Finalize: seeds the default system settings and marks setup complete.
			await api.post("/setup/complete");
			router.push("/");
		} catch (err: any) {
			setSetupError(
				err.response?.data?.detail ||
					"Could not save setup. Check your TMDB key" +
						(customizeQbit ? " and qBittorrent settings." : "."),
			);
		} finally {
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

			{/* Register card */}
			<div
				className={cn(
					"relative w-full z-10 transition-all",
					currentStep === "2fa" ? "max-w-4xl" : "max-w-md",
				)}
			>
				<div className="text-center mb-8">
					<div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-[#27272a] to-[#3b82f6] mb-6 shadow-2xl">
						<Film className="w-10 h-10 text-white" />
					</div>
					<h1 className="text-6xl font-bold logo-gradient mb-3">
						Kinora
					</h1>
					<p className="text-lg text-muted-foreground font-medium">
						Unified Media Management
					</p>
				</div>

				<div className="bg-card border border-border rounded-2xl shadow-2xl p-8 backdrop-blur-sm">
					{/* Step indicators */}
					<div className="flex items-center justify-center mb-8 gap-2">
						<div
							className={cn(
								"flex items-center gap-2 px-4 py-2 rounded-lg transition-all",
								currentStep === "credentials"
									? "bg-primary text-primary-foreground"
									: "bg-muted text-muted-foreground",
							)}
						>
							<UserPlus className="w-4 h-4" />
							<span className="text-sm font-medium">Account</span>
						</div>
						<ArrowRight className="w-4 h-4 text-muted-foreground" />
						<div
							className={cn(
								"flex items-center gap-2 px-4 py-2 rounded-lg transition-all",
								currentStep === "2fa"
									? "bg-primary text-primary-foreground"
									: "bg-muted text-muted-foreground",
							)}
						>
							<Shield className="w-4 h-4" />
							<span className="text-sm font-medium">
								Security (Optional)
							</span>
						</div>
						{needsSetup && (
							<>
								<ArrowRight className="w-4 h-4 text-muted-foreground" />
								<div
									className={cn(
										"flex items-center gap-2 px-4 py-2 rounded-lg transition-all",
										currentStep === "setup"
											? "bg-primary text-primary-foreground"
											: "bg-muted text-muted-foreground",
									)}
								>
									<Key className="w-4 h-4" />
									<span className="text-sm font-medium">
										Setup
									</span>
								</div>
							</>
						)}
					</div>

					{currentStep === "credentials" && (
						<>
							<h2 className="text-2xl font-bold text-foreground mb-6 text-center">
								Create Your Account
							</h2>

							<form className="space-y-6" onSubmit={handleSubmit}>
								{error && (
									<div className="rounded-lg bg-destructive/10 border border-destructive/50 p-4">
										<div className="text-sm text-destructive font-medium">
											{error}
										</div>
									</div>
								)}

								<div className="space-y-4">
									<div>
										<label
											htmlFor="username"
											className="block text-sm font-semibold text-foreground mb-2"
										>
											Username
										</label>
										<input
											id="username"
											name="username"
											type="text"
											required
											value={username}
											onChange={(e) =>
												setUsername(e.target.value)
											}
											className={cn(
												"w-full px-4 py-3 rounded-lg",
												"bg-background border-2 border-input",
												"text-foreground placeholder:text-muted-foreground",
												"focus:outline-none focus:border-primary focus:ring-4 focus:ring-ring/20",
												"transition-all duration-200",
											)}
											placeholder="Choose a username"
										/>
									</div>

									<div>
										<label
											htmlFor="password"
											className="block text-sm font-semibold text-foreground mb-2"
										>
											Password
										</label>
										<input
											id="password"
											name="password"
											type="password"
											required
											value={password}
											onChange={(e) =>
												setPassword(e.target.value)
											}
											className={cn(
												"w-full px-4 py-3 rounded-lg",
												"bg-background border-2 border-input",
												"text-foreground placeholder:text-muted-foreground",
												"focus:outline-none focus:border-primary focus:ring-4 focus:ring-ring/20",
												"transition-all duration-200",
											)}
											placeholder="At least 8 characters"
										/>
									</div>

									<div>
										<label
											htmlFor="confirmPassword"
											className="block text-sm font-semibold text-foreground mb-2"
										>
											Confirm Password
										</label>
										<input
											id="confirmPassword"
											name="confirmPassword"
											type="password"
											required
											value={confirmPassword}
											onChange={(e) =>
												setConfirmPassword(
													e.target.value,
												)
											}
											className={cn(
												"w-full px-4 py-3 rounded-lg",
												"bg-background border-2 border-input",
												"text-foreground placeholder:text-muted-foreground",
												"focus:outline-none focus:border-primary focus:ring-4 focus:ring-ring/20",
												"transition-all duration-200",
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
										"transition-all cursor-pointer",
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
										Already have an account?{" "}
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

					{currentStep === "setup" && (
						<>
							<h2 className="text-2xl font-bold text-foreground mb-2 text-center">
								Configure Kinora
							</h2>
							<p className="text-sm text-muted-foreground mb-6 text-center">
								Your download client and library folders are set
								up automatically. Add your TMDB API key to
								enable search and metadata.
							</p>
							<form className="space-y-6" onSubmit={handleSetup}>
								{setupError && (
									<div className="rounded-lg bg-destructive/10 border border-destructive/50 p-4">
										<div className="text-sm text-destructive font-medium">
											{setupError}
										</div>
									</div>
								)}
								<div>
									<label
										htmlFor="tmdb"
										className="block text-sm font-semibold text-foreground mb-2"
									>
										TMDB API Key
									</label>
									<input
										id="tmdb"
										type="text"
										required
										value={tmdbKey}
										onChange={(e) =>
											setTmdbKey(e.target.value)
										}
										className={cn(
											"w-full px-4 py-3 rounded-lg",
											"bg-background border-2 border-input",
											"text-foreground placeholder:text-muted-foreground",
											"focus:outline-none focus:border-primary focus:ring-4 focus:ring-ring/20",
											"transition-all duration-200",
										)}
										placeholder="Your TMDB API key"
									/>
									<p className="text-xs text-muted-foreground mt-2">
										Free from{" "}
										<a
											href="https://www.themoviedb.org/settings/api"
											target="_blank"
											rel="noopener noreferrer"
											className="text-primary underline hover:no-underline"
										>
											themoviedb.org
										</a>{" "}
										under Settings, API.
									</p>
								</div>
								<div className="border border-border rounded-lg">
									<button
										type="button"
										onClick={() =>
											setCustomizeQbit((v) => !v)
										}
										className="w-full flex items-center justify-between px-4 py-3 text-sm cursor-pointer"
									>
										<span className="font-medium text-foreground">
											Download client (auto-configured)
										</span>
										{customizeQbit ? (
											<ChevronUp className="w-4 h-4" />
										) : (
											<ChevronDown className="w-4 h-4" />
										)}
									</button>
									{customizeQbit && (
										<div className="px-4 pb-4 space-y-3">
											<p className="text-xs text-muted-foreground">
												qBittorrent is already
												connected. Change these only to
												point Kinora at a different
												client.
											</p>
											<div className="grid grid-cols-2 gap-3">
												<input
													placeholder="Host"
													value={qbit.host}
													onChange={(e) =>
														setQbit({
															...qbit,
															host: e.target
																.value,
														})
													}
													className="px-3 py-2 rounded-lg bg-background border-2 border-input text-foreground text-sm"
												/>
												<input
													placeholder="Port"
													type="number"
													value={qbit.port}
													onChange={(e) =>
														setQbit({
															...qbit,
															port: Number(
																e.target.value,
															),
														})
													}
													className="px-3 py-2 rounded-lg bg-background border-2 border-input text-foreground text-sm"
												/>
												<input
													placeholder="Username"
													value={qbit.username}
													onChange={(e) =>
														setQbit({
															...qbit,
															username:
																e.target.value,
														})
													}
													className="px-3 py-2 rounded-lg bg-background border-2 border-input text-foreground text-sm"
												/>
												<input
													placeholder="Password"
													type="password"
													value={qbit.password}
													onChange={(e) =>
														setQbit({
															...qbit,
															password:
																e.target.value,
														})
													}
													className="px-3 py-2 rounded-lg bg-background border-2 border-input text-foreground text-sm"
												/>
											</div>
										</div>
									)}
								</div>
								<div className="flex gap-3">
									<button
										type="button"
										onClick={() => setCurrentStep("2fa")}
										disabled={loading}
										className="px-6 py-3 bg-muted text-foreground rounded-lg hover:opacity-90 transition flex items-center gap-2 cursor-pointer disabled:opacity-50"
									>
										<ArrowLeft className="w-4 h-4" />
										Back
									</button>
									<button
										type="submit"
										disabled={loading}
										className={cn(
											"flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg",
											"bg-primary text-primary-foreground font-semibold",
											"hover:bg-primary/90 focus:outline-none focus:ring-4 focus:ring-ring/20",
											"transition-all duration-200 disabled:opacity-50 cursor-pointer",
										)}
									>
										{loading ? (
											<>
												<Loader2 className="w-5 h-5 animate-spin" />
												Saving...
											</>
										) : (
											<>
												Finish
												<ArrowRight className="w-5 h-5" />
											</>
										)}
									</button>
								</div>
							</form>
						</>
					)}

					{currentStep === "2fa" && (
						<div className="space-y-6">
							<div className="text-center mb-6">
								<h2 className="text-2xl font-bold text-foreground mb-2 flex items-center justify-center gap-2">
									Secure Your Account
									<span className="text-xs font-medium px-2 py-1 rounded-md bg-primary/10 text-primary border border-primary/20">
										Optional
									</span>
								</h2>
								<p className="text-sm text-muted-foreground mb-2">
									Add an extra layer of security with
									two-factor authentication
								</p>
								<p className="text-xs text-muted-foreground/70">
									You can always set this up later from your
									profile settings
								</p>
							</div>

							<TwoFactorSettings />

							<div className="flex gap-3 pt-6 border-t border-border">
								<button
									onClick={() =>
										setCurrentStep("credentials")
									}
									className="px-6 py-3 bg-muted text-foreground rounded-lg hover:opacity-90 transition flex items-center gap-2 cursor-pointer"
								>
									<ArrowLeft className="w-4 h-4" />
									Back
								</button>
								<button
									onClick={() =>
										needsSetup
											? setCurrentStep("setup")
											: router.push("/")
									}
									className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition flex items-center justify-center gap-2 font-medium cursor-pointer"
								>
									{needsSetup ? "Continue" : "Skip for now"}
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
