"use client";

import { Suspense, useMemo, useState, useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import Image from "next/image";
import {
	addDays,
	addMonths,
	addWeeks,
	eachDayOfInterval,
	endOfMonth,
	endOfWeek,
	format,
	formatDistanceToNow,
	isSameMonth,
	parseISO,
	startOfMonth,
	startOfWeek,
} from "date-fns";
import {
	CalendarDays,
	ChevronLeft,
	ChevronRight,
	Clock,
	CheckCircle2,
	Download,
	AlertTriangle,
	EyeOff,
	Film,
	Tv,
	Sparkles,
	Music2,
	List,
	LayoutGrid,
	Bookmark,
	Rss,
	Search,
} from "lucide-react";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { usePermissions } from "@/contexts/PermissionContext";
import { createLocalStorageStore } from "@/lib/localStorageStore";

type MediaType = "movie" | "show" | "anime" | "album";
type EntryStatus =
	| "upcoming"
	| "waiting"
	| "downloading"
	| "available"
	| "missing"
	| "unmonitored";
type CalendarView = "month" | "agenda";

interface CalendarEntry {
	key: string;
	mediaType: MediaType;
	mediaId: number;
	episodeId: number | null;
	artistId?: number | null;
	title: string;
	subtitle: string | null;
	recordType?: string | null;
	seasonNumber: number | null;
	episodeNumber: number | null;
	date: string;
	dateKind: "airDate" | "digital" | "physical" | "theatrical" | "release";
	digitalDate: string | null;
	physicalDate: string | null;
	theatricalDate: string | null;
	imageUrl: string | null;
	monitored: boolean;
	hasFile: boolean;
	status: EntryStatus;
	nextSearchAt: string | null;
	nextSearchKind: "search" | "rss" | null;
}

interface CalendarResponse {
	start: string;
	end: string;
	today: string;
	types: MediaType[];
	missingAfterDays: number;
	entries: CalendarEntry[];
}

// Sunday, matching the date-fns default.
const WEEK_STARTS_ON = 0;

// Entries listed in one month cell before the rest collapse into a "more" link.
const MONTH_CELL_LIMIT = 3;

// Screens at or below this width open in the agenda view unless a view was chosen.
const PHONE_MEDIA_QUERY = "(max-width: 767px)";

const MEDIA_TYPES: {
	type: MediaType;
	label: string;
	permission: string;
	icon: typeof Film;
}[] = [
	{ type: "movie", label: "Movies", permission: "movies", icon: Film },
	{ type: "show", label: "Shows", permission: "shows", icon: Tv },
	{ type: "anime", label: "Anime", permission: "anime", icon: Sparkles },
	{ type: "album", label: "Music", permission: "music", icon: Music2 },
];

const STATUS_STYLES: Record<
	EntryStatus,
	{ label: string; className: string; icon: typeof Clock }
> = {
	upcoming: {
		label: "Upcoming",
		className: "bg-blue-500/20 text-blue-500",
		icon: CalendarDays,
	},
	waiting: {
		label: "Aired, waiting",
		className: "bg-yellow-500/20 text-yellow-500",
		icon: Clock,
	},
	downloading: {
		label: "Downloading",
		className: "bg-purple-500/20 text-purple-500",
		icon: Download,
	},
	available: {
		label: "Available",
		className: "bg-green-500/20 text-green-500",
		icon: CheckCircle2,
	},
	missing: {
		label: "Missing",
		className: "bg-red-500/20 text-red-500",
		icon: AlertTriangle,
	},
	unmonitored: {
		label: "Not monitored",
		className: "bg-gray-500/20 text-gray-400",
		icon: EyeOff,
	},
};

const DATE_KIND_LABELS: Record<CalendarEntry["dateKind"], string> = {
	airDate: "Airs",
	digital: "Digital",
	physical: "Physical",
	theatrical: "Theatrical",
	release: "Release",
};

// The chosen view, or null when the viewer has not picked one yet.
const viewStore = createLocalStorageStore<CalendarView | null>({
	key: "kinora.calendar.view",
	serverValue: null,
	parse: (raw) => (raw === "month" || raw === "agenda" ? raw : null),
	serialize: (value) => value ?? "",
});

const monitoredOnlyStore = createLocalStorageStore<boolean>({
	key: "kinora.calendar.monitoredOnly",
	serverValue: false,
	parse: (raw) => raw === "true",
	serialize: (value) => String(value),
});

function subscribePhoneQuery(onChange: () => void) {
	const query = window.matchMedia(PHONE_MEDIA_QUERY);
	query.addEventListener("change", onChange);
	return () => query.removeEventListener("change", onChange);
}

function entryHref(entry: CalendarEntry): string {
	switch (entry.mediaType) {
		case "movie":
			return `/movies/${entry.mediaId}`;
		case "show":
			return `/shows/${entry.mediaId}`;
		case "anime":
			return `/anime/${entry.mediaId}`;
		case "album":
			return `/music/album/${entry.mediaId}`;
	}
}

function imageSrc(entry: CalendarEntry): string {
	if (!entry.imageUrl) return "/placeholder-poster.svg";
	if (entry.imageUrl.startsWith("http")) return entry.imageUrl;
	return `https://image.tmdb.org/t/p/w185${entry.imageUrl}`;
}

function episodeLabel(entry: CalendarEntry): string | null {
	if (entry.episodeNumber == null) return null;
	if (entry.seasonNumber == null) return `E${entry.episodeNumber}`;
	const season = String(entry.seasonNumber).padStart(2, "0");
	const episode = String(entry.episodeNumber).padStart(2, "0");
	return `S${season}E${episode}`;
}

function formatDay(day: string | null): string | null {
	return day ? format(parseISO(day), "MMM d, yyyy") : null;
}

function StatusBadge({ status }: { status: EntryStatus }) {
	const style = STATUS_STYLES[status];
	const Icon = style.icon;
	return (
		<span
			className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded ${style.className}`}
		>
			<Icon className="w-3 h-3" />
			{style.label}
		</span>
	);
}

function MediaIcon({
	type,
	className,
}: {
	type: MediaType;
	className: string;
}) {
	const Icon = MEDIA_TYPES.find((m) => m.type === type)?.icon ?? Film;
	return <Icon className={className} />;
}

function NextSearch({ entry }: { entry: CalendarEntry }) {
	if (!entry.nextSearchAt) return null;
	const Icon = entry.nextSearchKind === "rss" ? Rss : Search;
	const label =
		entry.nextSearchKind === "rss" ? "Next RSS check" : "Next search";
	const when = parseISO(entry.nextSearchAt);
	return (
		<span
			className="inline-flex items-center gap-1 text-xs text-muted-foreground"
			title={format(when, "PPpp")}
		>
			<Icon className="w-3 h-3" />
			{label} {formatDistanceToNow(when, { addSuffix: true })}
		</span>
	);
}

function MovieDates({ entry }: { entry: CalendarEntry }) {
	if (entry.mediaType !== "movie") return null;
	// The primary date is already the entry's date, so only the others are listed.
	const others: { label: string; day: string | null }[] = [
		{ label: "Digital", day: entry.digitalDate },
		{ label: "Physical", day: entry.physicalDate },
		{ label: "Theatrical", day: entry.theatricalDate },
	].filter((d) => d.day && d.day !== entry.date);
	if (others.length === 0) return null;
	return (
		<div className="flex gap-3 flex-wrap text-xs text-muted-foreground">
			{others.map((d) => (
				<span key={d.label}>
					{d.label}: {formatDay(d.day)}
				</span>
			))}
		</div>
	);
}

function AgendaEntry({ entry }: { entry: CalendarEntry }) {
	const episode = episodeLabel(entry);
	return (
		<Link
			href={entryHref(entry)}
			className={`flex items-center gap-4 bg-card text-card-foreground rounded-lg shadow p-4 hover:bg-accent/50 transition ${
				entry.monitored ? "" : "opacity-50"
			}`}
		>
			<div className="relative w-10 h-14 shrink-0 overflow-hidden rounded bg-muted">
				<Image
					src={imageSrc(entry)}
					alt={entry.title}
					fill
					unoptimized
					sizes="40px"
					className="object-cover"
				/>
			</div>
			<div className="flex-1 min-w-0 space-y-1">
				<div className="flex items-center gap-2 min-w-0">
					<MediaIcon
						type={entry.mediaType}
						className="w-4 h-4 shrink-0 text-muted-foreground"
					/>
					<h3 className="font-semibold truncate">{entry.title}</h3>
				</div>
				<div className="flex gap-3 flex-wrap items-center text-sm text-muted-foreground">
					{episode && (
						<span className="px-2 py-0.5 bg-muted rounded">
							{episode}
						</span>
					)}
					{entry.subtitle && (
						<span className="truncate min-w-0">
							{entry.subtitle}
						</span>
					)}
					{entry.recordType && (
						<span className="capitalize">{entry.recordType}</span>
					)}
					<span>{DATE_KIND_LABELS[entry.dateKind]}</span>
				</div>
				<MovieDates entry={entry} />
				<div className="flex gap-3 flex-wrap items-center">
					<StatusBadge status={entry.status} />
					{!entry.monitored && (
						<span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
							<Bookmark className="w-3 h-3" />
							Unmonitored
						</span>
					)}
					<NextSearch entry={entry} />
				</div>
			</div>
		</Link>
	);
}

function MonthCellEntry({ entry }: { entry: CalendarEntry }) {
	const episode = episodeLabel(entry);
	const style = STATUS_STYLES[entry.status];
	const tooltip = [
		entry.title,
		episode,
		entry.subtitle,
		style.label,
		entry.nextSearchAt
			? `${entry.nextSearchKind === "rss" ? "Next RSS check" : "Next search"} ${format(parseISO(entry.nextSearchAt), "PPpp")}`
			: null,
	]
		.filter(Boolean)
		.join(" · ");
	return (
		<Link
			href={entryHref(entry)}
			title={tooltip}
			className={`flex items-center gap-1 px-1.5 py-0.5 text-xs rounded ${style.className} ${
				entry.monitored ? "" : "opacity-50"
			}`}
		>
			<MediaIcon type={entry.mediaType} className="w-3 h-3 shrink-0" />
			<span className="truncate">
				{episode ? `${entry.title} ${episode}` : entry.title}
			</span>
		</Link>
	);
}

function CalendarContent() {
	const { canView, loading: permissionsLoading } = usePermissions();

	const storedView = useSyncExternalStore(
		viewStore.subscribe,
		viewStore.getSnapshot,
		viewStore.getServerSnapshot,
	);
	const isPhone = useSyncExternalStore(
		subscribePhoneQuery,
		() => window.matchMedia(PHONE_MEDIA_QUERY).matches,
		() => false,
	);
	const view: CalendarView = storedView ?? (isPhone ? "agenda" : "month");

	const monitoredOnly = useSyncExternalStore(
		monitoredOnlyStore.subscribe,
		monitoredOnlyStore.getSnapshot,
		monitoredOnlyStore.getServerSnapshot,
	);

	const [anchor, setAnchor] = useState(() => new Date());
	const [hiddenTypes, setHiddenTypes] = useState<Set<MediaType>>(
		() => new Set(),
	);

	const viewableTypes = MEDIA_TYPES.filter(
		(m) => permissionsLoading || canView(m.permission),
	);
	const selectedTypes = viewableTypes
		.map((m) => m.type)
		.filter((t) => !hiddenTypes.has(t));

	const { rangeStart, rangeEnd } = useMemo(() => {
		if (view === "month") {
			return {
				rangeStart: startOfWeek(startOfMonth(anchor), {
					weekStartsOn: WEEK_STARTS_ON,
				}),
				rangeEnd: endOfWeek(endOfMonth(anchor), {
					weekStartsOn: WEEK_STARTS_ON,
				}),
			};
		}
		const weekStart = startOfWeek(anchor, { weekStartsOn: WEEK_STARTS_ON });
		return { rangeStart: weekStart, rangeEnd: addDays(weekStart, 6) };
	}, [view, anchor]);

	const startParam = format(rangeStart, "yyyy-MM-dd");
	const endParam = format(rangeEnd, "yyyy-MM-dd");

	const { data, isLoading, isError } = useQuery<CalendarResponse>({
		queryKey: [
			"calendar",
			startParam,
			endParam,
			selectedTypes.join(","),
			monitoredOnly,
		],
		queryFn: async () => {
			const response = await api.get("/calendar/", {
				params: {
					start: startParam,
					end: endParam,
					types: selectedTypes.join(","),
					monitoredOnly,
				},
			});
			return response.data;
		},
		enabled: !permissionsLoading && selectedTypes.length > 0,
		// Statuses and next search times move as downloads progress.
		refetchInterval: 60000,
	});

	const entriesByDay = useMemo(() => {
		const grouped = new Map<string, CalendarEntry[]>();
		for (const entry of data?.entries ?? []) {
			const dayEntries = grouped.get(entry.date) ?? [];
			dayEntries.push(entry);
			grouped.set(entry.date, dayEntries);
		}
		return grouped;
	}, [data]);

	const days = eachDayOfInterval({ start: rangeStart, end: rangeEnd });
	const todayKey = format(new Date(), "yyyy-MM-dd");

	const statusCounts = useMemo(() => {
		const counts: Partial<Record<EntryStatus, number>> = {};
		for (const entry of data?.entries ?? []) {
			counts[entry.status] = (counts[entry.status] ?? 0) + 1;
		}
		return counts;
	}, [data]);

	const step = (direction: 1 | -1) => {
		setAnchor((current) =>
			view === "month"
				? addMonths(current, direction)
				: addWeeks(current, direction),
		);
	};

	const toggleType = (type: MediaType) => {
		setHiddenTypes((current) => {
			const next = new Set(current);
			if (next.has(type)) next.delete(type);
			else next.add(type);
			return next;
		});
	};

	const openWeek = (day: Date) => {
		setAnchor(day);
		viewStore.set("agenda");
	};

	const rangeLabel =
		view === "month"
			? format(anchor, "MMMM yyyy")
			: `${format(rangeStart, "MMM d")} - ${format(rangeEnd, "MMM d, yyyy")}`;

	const toggleButtonClass = (active: boolean) =>
		`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition cursor-pointer ${
			active
				? "bg-primary text-primary-foreground shadow-lg"
				: "bg-card text-foreground hover:bg-accent"
		}`;

	return (
		<div className="min-h-screen">
			<PageHeader
				title="Calendar"
				description="Upcoming and recent releases across your library"
				gradientFrom="cyan-600/10"
				gradientVia="blue-600/10"
				gradientTo="indigo-600/10"
			/>

			<div className="container mx-auto px-6 py-8">
				{/* Range navigation and view switch */}
				<div className="flex flex-col md:flex-row md:items-center gap-4 mb-6">
					<div className="flex items-center gap-2">
						<button
							onClick={() => step(-1)}
							className="px-4 py-2 bg-card border border-border text-foreground rounded-lg hover:bg-accent transition cursor-pointer"
							aria-label="Previous"
						>
							<ChevronLeft className="w-4 h-4" />
						</button>
						<button
							onClick={() => setAnchor(new Date())}
							className="px-4 py-2 bg-card border border-border text-foreground rounded-lg hover:bg-accent transition cursor-pointer"
						>
							Today
						</button>
						<button
							onClick={() => step(1)}
							className="px-4 py-2 bg-card border border-border text-foreground rounded-lg hover:bg-accent transition cursor-pointer"
							aria-label="Next"
						>
							<ChevronRight className="w-4 h-4" />
						</button>
					</div>
					<h2 className="text-2xl font-bold flex-1">{rangeLabel}</h2>
					<div className="flex gap-2">
						<button
							onClick={() => viewStore.set("month")}
							className={toggleButtonClass(view === "month")}
						>
							<LayoutGrid className="w-4 h-4" />
							Month
						</button>
						<button
							onClick={() => viewStore.set("agenda")}
							className={toggleButtonClass(view === "agenda")}
						>
							<List className="w-4 h-4" />
							Agenda
						</button>
					</div>
				</div>

				{/* Filters */}
				<div className="flex gap-2 flex-wrap mb-4 items-center justify-between">
					<div className="flex gap-2 flex-wrap">
						{viewableTypes.map((m) => {
							const Icon = m.icon;
							return (
								<button
									key={m.type}
									onClick={() => toggleType(m.type)}
									className={toggleButtonClass(
										!hiddenTypes.has(m.type),
									)}
								>
									<Icon className="w-4 h-4" />
									{m.label}
								</button>
							);
						})}
					</div>
					<button
						onClick={() => monitoredOnlyStore.set(!monitoredOnly)}
						className={toggleButtonClass(monitoredOnly)}
					>
						<Bookmark className="w-4 h-4" />
						Monitored only
					</button>
				</div>

				{/* Status legend with counts for the range */}
				<div className="flex gap-2 flex-wrap items-center mb-6">
					{(Object.keys(STATUS_STYLES) as EntryStatus[]).map(
						(status) => (
							<span
								key={status}
								className="inline-flex items-center gap-1"
							>
								<StatusBadge status={status} />
								<span className="text-xs text-muted-foreground">
									{statusCounts[status] ?? 0}
								</span>
							</span>
						),
					)}
					{data && (
						<span className="text-xs text-muted-foreground">
							Missing after {data.missingAfterDays} days without a
							file
						</span>
					)}
				</div>

				{selectedTypes.length === 0 ? (
					<div className="bg-card text-card-foreground rounded-lg shadow p-12 text-center">
						<h2 className="text-2xl font-bold mb-4">
							No Media Types Selected
						</h2>
						<p className="text-muted-foreground">
							Select at least one media type to see its releases
						</p>
					</div>
				) : isLoading ? (
					<div className="text-center py-12">Loading calendar...</div>
				) : isError ? (
					<div className="bg-card text-card-foreground rounded-lg shadow p-12 text-center">
						<h2 className="text-2xl font-bold mb-4">
							Calendar Unavailable
						</h2>
						<p className="text-muted-foreground">
							The release calendar could not be loaded
						</p>
					</div>
				) : view === "month" ? (
					<div className="bg-card text-card-foreground rounded-lg shadow overflow-hidden">
						<div
							className="grid border-b border-border"
							style={{
								gridTemplateColumns:
									"repeat(7, minmax(0, 1fr))",
							}}
						>
							{days.slice(0, 7).map((day) => (
								<div
									key={day.toISOString()}
									className="p-2 text-xs font-medium text-muted-foreground text-center"
								>
									{format(day, isPhone ? "EEEEE" : "EEE")}
								</div>
							))}
						</div>
						<div
							className="grid"
							style={{
								gridTemplateColumns:
									"repeat(7, minmax(0, 1fr))",
							}}
						>
							{days.map((day) => {
								const dayKey = format(day, "yyyy-MM-dd");
								const dayEntries =
									entriesByDay.get(dayKey) ?? [];
								const hiddenCount =
									dayEntries.length - MONTH_CELL_LIMIT;
								const inMonth = isSameMonth(day, anchor);
								return (
									<div
										key={dayKey}
										className={`p-1 border-r border-b border-border min-w-0 space-y-1 ${
											inMonth ? "" : "bg-muted/50"
										}`}
										style={{ minHeight: "6.5rem" }}
									>
										<div
											className={`text-xs font-medium px-1 ${
												dayKey === todayKey
													? "text-primary"
													: inMonth
														? ""
														: "text-muted-foreground"
											}`}
										>
											{format(day, "d")}
										</div>
										{dayEntries
											.slice(0, MONTH_CELL_LIMIT)
											.map((entry) => (
												<MonthCellEntry
													key={entry.key}
													entry={entry}
												/>
											))}
										{hiddenCount > 0 && (
											<button
												onClick={() => openWeek(day)}
												className="w-full text-left px-1.5 text-xs text-muted-foreground hover:text-primary cursor-pointer"
											>
												+{hiddenCount} more
											</button>
										)}
									</div>
								);
							})}
						</div>
					</div>
				) : (
					<div className="space-y-6">
						{days
							.map((day) => format(day, "yyyy-MM-dd"))
							.filter((dayKey) => entriesByDay.has(dayKey))
							.map((dayKey) => (
								<div key={dayKey}>
									<h3
										className={`text-lg font-bold mb-3 ${
											dayKey === todayKey
												? "text-primary"
												: ""
										}`}
									>
										{format(
											parseISO(dayKey),
											"EEEE, MMMM d",
										)}
										{dayKey === todayKey && (
											<span className="text-sm font-medium text-muted-foreground">
												{" "}
												Today
											</span>
										)}
									</h3>
									<div className="space-y-3">
										{entriesByDay
											.get(dayKey)!
											.map((entry) => (
												<AgendaEntry
													key={entry.key}
													entry={entry}
												/>
											))}
									</div>
								</div>
							))}
						{entriesByDay.size === 0 && (
							<div className="bg-card text-card-foreground rounded-lg shadow p-12 text-center">
								<h2 className="text-2xl font-bold mb-4">
									No Releases This Week
								</h2>
								<p className="text-muted-foreground">
									Episodes, movies and albums dated in this
									week will appear here
								</p>
							</div>
						)}
					</div>
				)}
			</div>
		</div>
	);
}

// The page reads the current date, so it renders per visit inside Suspense rather than
// being prerendered at build time.
export default function CalendarPage() {
	return (
		<Suspense fallback={<div className="min-h-screen" />}>
			<CalendarContent />
		</Suspense>
	);
}
