"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useState, useEffect, useRef } from "react";
import {
	LogOut,
	ChevronLeft,
	ChevronRight,
	Search,
	Plus,
	LayoutDashboard,
	Activity,
	Film,
	Tv,
	Sparkles,
	Music2,
	Compass,
	Disc3,
	PlusCircle,
	Settings,
	FileVideo,
	Wrench,
	Inbox,
	Download,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useSidebar } from "@/contexts/SidebarContext";
import { usePermissions } from "@/contexts/PermissionContext";
import { getRequestCounts } from "@/lib/api/requests";
import { api } from "@/lib/api";
import NotificationBell from "./NotificationBell";

export default function Navigation() {
	const router = useRouter();
	const pathname = usePathname();
	const { collapsed, toggleCollapsed } = useSidebar();
	const {
		canView,
		hasAnyPermission,
		hasPermission,
		loading: permissionsLoading,
		user,
	} = usePermissions();
	const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
	const [mounted, setMounted] = useState(false);
	const [searchQuery, setSearchQuery] = useState("");
	const [searchResults, setSearchResults] = useState<any[]>([]);
	const [showDropdown, setShowDropdown] = useState(false);
	const [isSearching, setIsSearching] = useState(false);
	const searchRef = useRef<HTMLDivElement>(null);

	// Permission checks for navigation visibility (only valid after permissions loaded)
	const hasAnyApprovePermission =
		!permissionsLoading &&
		hasAnyPermission(
			"movies.approve",
			"shows.approve",
			"anime.approve",
			"music.approve",
		);
	const hasAnyRequestOrApprovePermission =
		!permissionsLoading &&
		hasAnyPermission(
			"movies.request",
			"shows.request",
			"anime.request",
			"music.request",
			"movies.approve",
			"shows.approve",
			"anime.approve",
			"music.approve",
		);
	const hasAnySystemPermission =
		!permissionsLoading &&
		hasAnyPermission(
			"system.admin",
			"system.settings",
			"system.users",
			"system.logs",
		);

	// Fetch pending request counts for badge display
	const { data: requestCounts } = useQuery({
		queryKey: ["request-counts"],
		queryFn: getRequestCounts,
		refetchInterval: 30000,
		enabled: !permissionsLoading && hasAnyApprovePermission,
	});

	useEffect(() => {
		setMounted(true);
	}, []);

	useEffect(() => {
		const handleClickOutside = (event: MouseEvent) => {
			if (
				searchRef.current &&
				!searchRef.current.contains(event.target as Node)
			) {
				setShowDropdown(false);
			}
		};

		document.addEventListener("mousedown", handleClickOutside);
		return () =>
			document.removeEventListener("mousedown", handleClickOutside);
	}, []);

	useEffect(() => {
		const searchLibrary = async () => {
			if (searchQuery.trim().length < 2) {
				setSearchResults([]);
				setShowDropdown(false);
				return;
			}

			setIsSearching(true);
			try {
				const response = await api.get("/library-search", {
					params: { query: searchQuery, limit: 5 },
				});

				// Transform results to match existing format
				const results = response.data.map((item: any) => ({
					...item,
					title: item.title,
					name: item.media_type === "artist" ? item.title : undefined,
				}));

				setSearchResults(results);
				setShowDropdown(true);
			} catch (error) {
				console.error("Search error:", error);
				setSearchResults([]);
			} finally {
				setIsSearching(false);
			}
		};

		const debounce = setTimeout(searchLibrary, 300);
		return () => clearTimeout(debounce);
	}, [searchQuery]);

	const handleLogout = () => {
		document.cookie = "access_token=; path=/; max-age=0";
		document.cookie = "refresh_token=; path=/; max-age=0";
		router.push("/login");
	};

	const isActive = (path: string) => pathname === path;

	// Build navigation sections with permission-based visibility
	// While loading, show all items; after loaded, filter by permissions
	const navSections = [
		{
			label: "General",
			links: [
				{
					href: "/",
					label: "Dashboard",
					icon: LayoutDashboard,
					visible: true,
				},
				{
					href: "/activity",
					label: "Activity",
					icon: Activity,
					visible: true,
				},
				{
					href: "/downloads",
					label: "Downloads",
					icon: Download,
					visible:
						permissionsLoading || hasPermission("system.downloads"),
				},
			],
		},
		{
			label: "Media",
			links: [
				{
					href: "/movies",
					label: "Movies",
					icon: Film,
					visible: permissionsLoading || canView("movies"),
				},
				{
					href: "/shows",
					label: "TV Shows",
					icon: Tv,
					visible: permissionsLoading || canView("shows"),
				},
				{
					href: "/anime",
					label: "Anime",
					icon: Sparkles,
					visible: permissionsLoading || canView("anime"),
				},
				{
					href: "/music",
					label: "Music",
					icon: Music2,
					visible: permissionsLoading || canView("music"),
				},
				{
					href: "/requests",
					label: "Requests",
					icon: Inbox,
					visible:
						permissionsLoading || hasAnyRequestOrApprovePermission,
					badge:
						hasAnyApprovePermission && requestCounts?.pending
							? requestCounts.pending
							: undefined,
				},
			],
		},
		{
			label: "Discovery",
			links: [
				{
					href: "/discover",
					label: "Discover",
					icon: Compass,
					visible: true,
				},
				{
					href: "/discover-music",
					label: "Discover Music",
					icon: Disc3,
					visible: true,
				},
				{
					href: "/search",
					label: "Search",
					icon: PlusCircle,
					visible: true,
				},
			],
		},
		{
			label: "Management",
			links: [
				{
					href: "/transcoding",
					label: "Transcoding",
					icon: Settings,
					visible: permissionsLoading || hasAnySystemPermission,
				},
				{
					href: "/media-profiles",
					label: "Media Profiles",
					icon: FileVideo,
					visible: permissionsLoading || hasAnySystemPermission,
				},
				{
					href: "/settings",
					label: "Settings",
					icon: Wrench,
					visible: permissionsLoading || hasAnySystemPermission,
				},
			],
		},
	]
		.map((section) => ({
			...section,
			links: section.links.filter((link) => link.visible),
		}))
		.filter((section) => section.links.length > 0);

	if (!mounted) return null;

	const token = document.cookie
		.split("; ")
		.find((row) => row.startsWith("access_token="));
	const isAuthPage = pathname === "/login" || pathname === "/register";

	if (!token || isAuthPage) return null;

	return (
		<>
			{/* Desktop Sidebar */}
			<aside
				className={`hidden md:flex flex-col fixed left-0 top-0 h-screen bg-background border-r-2 border-border transition-all duration-300 ${collapsed ? "w-20" : "w-64"}`}
			>
				{/* Logo and Collapse Button */}
				<div className="flex items-center justify-between p-4 border-b-2 border-border">
					{!collapsed && (
						<Link
							href="/"
							className="text-2xl font-bold logo-gradient"
						>
							Kinora
						</Link>
					)}
					<div className="flex items-center gap-1 ml-auto">
						{hasPermission("system.downloads") && (
							<NotificationBell collapsed={collapsed} />
						)}
						<button
							onClick={toggleCollapsed}
							className="p-2 rounded-lg hover:bg-accent transition cursor-pointer"
							aria-label="Toggle sidebar"
						>
							{collapsed ? (
								<ChevronRight className="w-5 h-5" />
							) : (
								<ChevronLeft className="w-5 h-5" />
							)}
						</button>
					</div>
				</div>

				{/* Global Search */}
				{!collapsed && (
					<div className="px-3 py-2 relative" ref={searchRef}>
						<div className="relative">
							<Search className="w-5 h-5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
							<input
								type="text"
								value={searchQuery}
								onChange={(e) => setSearchQuery(e.target.value)}
								onFocus={() =>
									searchQuery.length >= 2 &&
									setShowDropdown(true)
								}
								placeholder="Quick Search..."
								className="w-full pl-10 pr-4 py-3 rounded-lg bg-accent/50 border border-border hover:bg-accent hover:border-primary/30 focus:bg-accent focus:border-primary/30 focus:outline-none transition-all text-sm placeholder:text-muted-foreground"
							/>
						</div>

						{showDropdown && (
							<div className="absolute top-full left-3 right-3 mt-2 bg-background border border-border rounded-lg shadow-2xl z-50 max-h-96 overflow-y-auto">
								{isSearching ? (
									<div className="p-4 text-center text-sm text-muted-foreground">
										Searching...
									</div>
								) : searchResults.length > 0 ? (
									<>
										<div className="p-2">
											{searchResults.map((item) => {
												const getImageUrl = () => {
													if (
														item.media_type ===
														"artist"
													) {
														return (
															item.picture_medium ||
															item.picture ||
															"/placeholder-poster.svg"
														);
													}
													if (
														item.media_type ===
														"album"
													) {
														return (
															item.cover_medium ||
															item.cover ||
															"/placeholder-poster.svg"
														);
													}
													if (item.poster_path) {
														return `https://image.tmdb.org/t/p/w92${item.poster_path}`;
													}
													return null;
												};

												const getHref = () => {
													if (
														item.media_type ===
															"artist" ||
														item.media_type ===
															"album"
													) {
														return "/music";
													}
													if (
														item.media_type ===
														"movie"
													)
														return `/movies/${item.id}`;
													if (
														item.media_type ===
														"show"
													)
														return `/shows/${item.id}`;
													if (
														item.media_type ===
														"anime"
													)
														return `/anime/${item.id}`;
													return "/";
												};

												const imageUrl = getImageUrl();

												return (
													<Link
														key={`${item.media_type}-${item.id}`}
														href={getHref()}
														onClick={() => {
															setShowDropdown(
																false,
															);
															setSearchQuery("");
														}}
														className="flex items-center gap-3 p-2 rounded-lg hover:bg-accent transition"
													>
														{imageUrl && (
															<img
																src={imageUrl}
																alt={
																	item.title ||
																	item.name
																}
																className={`object-cover rounded ${item.media_type === "artist" ? "w-10 h-10" : "w-10 h-14"}`}
															/>
														)}
														<div className="flex-1 min-w-0">
															<p className="font-medium text-sm truncate">
																{item.title ||
																	item.name}
															</p>
															<p className="text-xs text-muted-foreground capitalize">
																{
																	item.media_type
																}
															</p>
														</div>
													</Link>
												);
											})}
										</div>
										<div className="border-t border-border p-2">
											<button
												onClick={() => {
													router.push(
														`/search?q=${encodeURIComponent(searchQuery)}`,
													);
													setShowDropdown(false);
													setSearchQuery("");
												}}
												className="w-full flex items-center justify-center gap-2 p-2 rounded-lg hover:bg-accent transition text-sm text-primary cursor-pointer"
											>
												<Plus className="w-4 h-4" />
												<span>Add new media</span>
											</button>
										</div>
									</>
								) : searchQuery.length >= 2 ? (
									<div className="p-4">
										<p className="text-sm text-muted-foreground text-center mb-3">
											No items found in library
										</p>
										<button
											onClick={() => {
												router.push(
													`/search?q=${encodeURIComponent(searchQuery)}`,
												);
												setShowDropdown(false);
												setSearchQuery("");
											}}
											className="w-full flex items-center justify-center gap-2 p-2 rounded-lg hover:bg-accent transition text-sm text-primary cursor-pointer"
										>
											<Plus className="w-4 h-4" />
											<span>
												Search for "{searchQuery}" to
												add
											</span>
										</button>
									</div>
								) : null}
							</div>
						)}
					</div>
				)}

				{/* Navigation Links */}
				<nav className="flex-1 overflow-y-auto py-4">
					<div className="space-y-6 px-3">
						{navSections.map((section) => (
							<div key={section.label}>
								{!collapsed && (
									<h3 className="px-4 mb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
										{section.label}
									</h3>
								)}
								<div className="space-y-1">
									{section.links.map((link) => (
										<Link
											key={link.href}
											href={link.href}
											className={`relative flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
												isActive(link.href)
													? "bg-primary text-primary-foreground shadow-lg shadow-primary/50"
													: "text-foreground/70 hover:text-foreground hover:bg-accent/70"
											}`}
											title={
												collapsed
													? link.label
													: undefined
											}
										>
											<div className="relative">
												<link.icon className="w-5 h-5" />
												{collapsed &&
													link.badge !== undefined &&
													link.badge > 0 && (
														<span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full h-4 w-4 flex items-center justify-center font-medium">
															{link.badge > 9
																? "9+"
																: link.badge}
														</span>
													)}
											</div>
											{!collapsed && (
												<>
													<span className="font-medium">
														{link.label}
													</span>
													{link.badge !== undefined &&
														link.badge > 0 && (
															<span className="ml-auto bg-red-500 text-white text-xs rounded-full h-5 min-w-5 px-1.5 flex items-center justify-center font-medium">
																{link.badge > 99
																	? "99+"
																	: link.badge}
															</span>
														)}
												</>
											)}
										</Link>
									))}
								</div>
							</div>
						))}
					</div>
				</nav>

				{/* Bottom Section - User */}
				<div className="border-t-2 border-border p-3 space-y-2">
					{user && !collapsed && (
						<Link
							href="/profile"
							className="block mx-2 p-3 rounded-xl bg-gradient-to-br from-primary/10 to-primary/5 border border-primary/20 shadow-sm hover:shadow-md hover:from-primary/15 hover:to-primary/10 transition-all cursor-pointer"
						>
							<div className="flex items-center gap-3">
								<div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
									<span className="text-lg font-bold text-primary">
										{user.username?.charAt(0).toUpperCase()}
									</span>
								</div>
								<div className="flex-1 min-w-0">
									<p className="text-sm font-semibold text-foreground truncate">
										{user.username}
									</p>
									{user.groups?.[0] ? (
										<span
											className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border"
											style={{
												backgroundColor: `${user.groups[0].color}20`,
												color: user.groups[0].color,
												borderColor: `${user.groups[0].color}50`,
											}}
										>
											{user.groups[0].displayName}
										</span>
									) : (
										<span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-muted text-muted-foreground border border-border">
											User
										</span>
									)}
								</div>
							</div>
						</Link>
					)}

					<button
						onClick={handleLogout}
						className="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-destructive/10 text-destructive transition w-full cursor-pointer"
						title={collapsed ? "Logout" : undefined}
					>
						<LogOut className="w-5 h-5" />
						{!collapsed && (
							<span className="text-sm font-medium">Logout</span>
						)}
					</button>
				</div>
			</aside>

			{/* Mobile Top Nav */}
			<nav className="md:hidden bg-background text-card-foreground shadow-lg border-b-2 border-border fixed top-0 left-0 right-0 z-50">
				<div className="flex justify-between items-center h-16 px-4">
					<Link href="/" className="text-xl font-bold logo-gradient">
						Kinora
					</Link>

					<div className="flex items-center gap-1">
						{hasPermission("system.downloads") && (
							<NotificationBell />
						)}
						<button
							onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
							className="p-2 rounded-md hover:bg-accent cursor-pointer"
						>
							<svg
								className="w-6 h-6"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								{mobileMenuOpen ? (
									<path
										strokeLinecap="round"
										strokeLinejoin="round"
										strokeWidth={2}
										d="M6 18L18 6M6 6l12 12"
									/>
								) : (
									<path
										strokeLinecap="round"
										strokeLinejoin="round"
										strokeWidth={2}
										d="M4 6h16M4 12h16M4 18h16"
									/>
								)}
							</svg>
						</button>
					</div>
				</div>

				{/* Mobile Menu */}
				{mobileMenuOpen && (
					<div className="border-t-2 border-border bg-background">
						<div className="px-2 pt-2 pb-3 space-y-4 max-h-[calc(100vh-4rem)] overflow-y-auto">
							{navSections.map((section) => (
								<div key={section.label}>
									<h3 className="px-3 mb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
										{section.label}
									</h3>
									<div className="space-y-1">
										{section.links.map((link) => (
											<Link
												key={link.href}
												href={link.href}
												onClick={() =>
													setMobileMenuOpen(false)
												}
												className={`flex items-center gap-3 px-3 py-3 rounded-lg transition ${
													isActive(link.href)
														? "bg-primary text-primary-foreground"
														: "text-muted-foreground hover:bg-accent hover:text-foreground"
												}`}
											>
												<link.icon className="w-5 h-5" />
												<span className="font-medium">
													{link.label}
												</span>
												{link.badge !== undefined &&
													link.badge > 0 && (
														<span className="ml-auto bg-red-500 text-white text-xs rounded-full h-5 min-w-5 px-1.5 flex items-center justify-center font-medium">
															{link.badge > 99
																? "99+"
																: link.badge}
														</span>
													)}
											</Link>
										))}
									</div>
								</div>
							))}
							<div className="pt-4 border-t-2 border-border space-y-2">
								{user && (
									<Link
										href="/profile"
										onClick={() => setMobileMenuOpen(false)}
										className="block mx-2 p-3 rounded-xl bg-gradient-to-br from-primary/10 to-primary/5 border border-primary/20 shadow-sm hover:shadow-md hover:from-primary/15 hover:to-primary/10 transition-all"
									>
										<div className="flex items-center gap-3">
											<div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
												<span className="text-lg font-bold text-primary">
													{user.username
														?.charAt(0)
														.toUpperCase()}
												</span>
											</div>
											<div className="flex-1 min-w-0">
												<p className="text-sm font-semibold text-foreground truncate">
													{user.username}
												</p>
												{user.groups?.[0] ? (
													<span
														className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border"
														style={{
															backgroundColor: `${user.groups[0].color}20`,
															color: user
																.groups[0]
																.color,
															borderColor: `${user.groups[0].color}50`,
														}}
													>
														{
															user.groups[0]
																.displayName
														}
													</span>
												) : (
													<span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-muted text-muted-foreground border border-border">
														User
													</span>
												)}
											</div>
										</div>
									</Link>
								)}
								<button
									onClick={() => {
										setMobileMenuOpen(false);
										handleLogout();
									}}
									className="w-full flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-destructive/10 text-destructive cursor-pointer"
								>
									<LogOut className="w-5 h-5" />
									<span className="font-medium">Logout</span>
								</button>
							</div>
						</div>
					</div>
				)}
			</nav>
		</>
	);
}
