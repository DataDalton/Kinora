"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { usePermissions } from "@/contexts/PermissionContext";
import {
	Database,
	Table as TableIcon,
	Download,
	Upload,
	Copy,
	Check,
	Eye,
	EyeOff,
	AlertTriangle,
	FileJson,
	Filter,
	Loader2,
	Search,
	Server,
	GitBranch,
	HardDrive,
	Boxes,
	X,
} from "lucide-react";

interface ConnectionInfo {
	host: string;
	port: number;
	database: string;
	user: string;
	password: string;
	connection_string: string;
}

interface Overview {
	postgres_version: string;
	database_size: string;
	database_size_bytes: number;
	table_count: number;
	alembic_current: string | null;
	alembic_head: string | null;
	up_to_date: boolean;
}

interface TableEntry {
	name: string;
	row_count: number;
	size_bytes: number;
	size_pretty: string;
}

interface TableRows {
	table: string;
	columns: string[];
	rows: Record<string, unknown>[];
	// Null on follow-up pages, which skip the count query. Page one always counts.
	total: number | null;
	limit: number;
	offset: number;
}

type Tab = "overview" | "tables" | "backup";

const PAGE_SIZE = 50;

function downloadBlob(data: Blob, filename: string) {
	const url = URL.createObjectURL(data);
	const a = document.createElement("a");
	a.href = url;
	a.download = filename;
	document.body.appendChild(a);
	a.click();
	a.remove();
	URL.revokeObjectURL(url);
}

function filenameFromDisposition(
	header: string | undefined,
	fallback: string,
): string {
	if (!header) return fallback;
	const match = header.match(/filename="?([^";]+)"?/);
	return match ? match[1] : fallback;
}

function cellText(value: unknown): string {
	if (value === null || value === undefined) return "";
	if (typeof value === "object") return JSON.stringify(value);
	return String(value);
}

// Debounce a value so search and filter inputs do not fire a request per keystroke.
function useDebouncedValue<T>(value: T, delayMs: number): T {
	const [debounced, setDebounced] = useState(value);
	useEffect(() => {
		const timer = setTimeout(() => setDebounced(value), delayMs);
		return () => clearTimeout(timer);
	}, [value, delayMs]);
	return debounced;
}

export default function DatabaseBackupSection() {
	const { hasPermission } = usePermissions();
	const canManage = hasPermission("system.admin");

	const [tab, setTab] = useState<Tab>("overview");
	const [revealPassword, setRevealPassword] = useState(false);
	const [copied, setCopied] = useState<string | null>(null);
	const [selectedTable, setSelectedTable] = useState<string | null>(null);
	// Free-text search across all columns, and per-column filter values.
	const [tableSearch, setTableSearch] = useState("");
	const [columnFilters, setColumnFilters] = useState<Record<string, string>>(
		{},
	);
	// Columns whose filter input is open (toggled from the header filter button).
	const [openFilterColumns, setOpenFilterColumns] = useState<Set<string>>(
		new Set(),
	);
	const debouncedSearch = useDebouncedValue(tableSearch, 400);
	const debouncedFilters = useDebouncedValue(columnFilters, 400);

	const toggleFilterColumn = (column: string) => {
		setOpenFilterColumns((prev) => {
			const next = new Set(prev);
			if (next.has(column)) {
				next.delete(column);
			} else {
				next.add(column);
			}
			return next;
		});
	};
	const [downloading, setDownloading] = useState<string | null>(null);
	const [importKind, setImportKind] = useState<
		"database" | "settings" | null
	>(null);
	const [importFile, setImportFile] = useState<File | null>(null);
	const [importConfirm, setImportConfirm] = useState(false);
	const [importBusy, setImportBusy] = useState(false);
	const [importMessage, setImportMessage] = useState<string | null>(null);

	const { data: overview } = useQuery<Overview>({
		queryKey: ["admin-db-overview"],
		queryFn: async () => (await api.get("/admin/database/overview")).data,
		enabled: canManage,
	});

	const { data: info } = useQuery<ConnectionInfo>({
		queryKey: ["admin-db-info"],
		queryFn: async () => (await api.get("/admin/database/info")).data,
		enabled: canManage,
	});

	const { data: tables } = useQuery<{ tables: TableEntry[] }>({
		queryKey: ["admin-db-tables"],
		queryFn: async () => (await api.get("/admin/database/tables")).data,
		enabled: canManage,
	});

	// Only filters with a value are sent, as a JSON object of column to value.
	const activeFilters = useMemo(
		() =>
			Object.fromEntries(
				Object.entries(debouncedFilters).filter(
					([, value]) => value.trim() !== "",
				),
			),
		[debouncedFilters],
	);
	const hasActiveFilters =
		debouncedSearch.trim() !== "" || Object.keys(activeFilters).length > 0;

	// Rows load through an infinite query: scrolling near the bottom of the table
	// fetches the next page until the (filtered) set is fully loaded.
	const {
		data: rowPages,
		isFetching: rowsLoading,
		fetchNextPage,
		hasNextPage,
		isFetchingNextPage,
	} = useInfiniteQuery<TableRows>({
		queryKey: [
			"admin-db-table",
			selectedTable,
			debouncedSearch,
			activeFilters,
		],
		queryFn: async ({ pageParam }) =>
			(
				await api.get(`/admin/database/tables/${selectedTable}`, {
					params: {
						limit: PAGE_SIZE,
						offset: pageParam as number,
						search: debouncedSearch.trim() || undefined,
						filters: Object.keys(activeFilters).length
							? JSON.stringify(activeFilters)
							: undefined,
						// The filtered count runs once on the first page. Later
						// pages reuse it instead of re-counting per scroll step.
						with_total: (pageParam as number) === 0,
					},
				})
			).data,
		initialPageParam: 0,
		getNextPageParam: (lastPage, allPages) => {
			const total = allPages[0]?.total ?? 0;
			const nextOffset = lastPage.offset + lastPage.rows.length;
			return lastPage.rows.length > 0 && nextOffset < total
				? nextOffset
				: undefined;
		},
		enabled: canManage && !!selectedTable,
	});

	const tableColumns = rowPages?.pages[0]?.columns ?? [];
	const tableTotal = rowPages?.pages[0]?.total ?? 0;
	const allRows = useMemo(
		() => rowPages?.pages.flatMap((p) => p.rows) ?? [],
		[rowPages],
	);

	// Sentinel element at the bottom of the scroll container. When it becomes
	// visible (within 200px), the next page loads.
	const scrollRootRef = useRef<HTMLDivElement | null>(null);
	const [sentinel, setSentinel] = useState<HTMLDivElement | null>(null);

	useEffect(() => {
		if (!sentinel) return;
		const observer = new IntersectionObserver(
			(entries) => {
				if (
					entries[0]?.isIntersecting &&
					hasNextPage &&
					!isFetchingNextPage
				) {
					fetchNextPage();
				}
			},
			{ root: scrollRootRef.current, rootMargin: "200px" },
		);
		observer.observe(sentinel);
		return () => observer.disconnect();
	}, [sentinel, hasNextPage, isFetchingNextPage, fetchNextPage]);

	const clearTableFilters = () => {
		setTableSearch("");
		setColumnFilters({});
		setOpenFilterColumns(new Set());
	};

	const copyValue = async (label: string, value: string) => {
		try {
			await navigator.clipboard.writeText(value);
			setCopied(label);
			setTimeout(() => setCopied(null), 2000);
		} catch {
			// clipboard unavailable
		}
	};

	const runExport = async (path: string, fallback: string) => {
		setDownloading(path);
		try {
			const response = await api.get(path, { responseType: "blob" });
			downloadBlob(
				response.data,
				filenameFromDisposition(
					response.headers["content-disposition"],
					fallback,
				),
			);
		} catch {
			setImportMessage(
				"Export failed. Check that the server has database tools available.",
			);
		} finally {
			setDownloading(null);
		}
	};

	const runImport = async () => {
		if (!importKind || !importFile) return;
		setImportBusy(true);
		setImportMessage(null);
		try {
			const form = new FormData();
			form.append("file", importFile);
			form.append("confirm", "true");
			const path =
				importKind === "database"
					? "/admin/import/database"
					: "/admin/import/settings";
			const response = await api.post(path, form);
			setImportMessage(
				importKind === "database"
					? "Database restored successfully."
					: `Settings imported: ${JSON.stringify(response.data.imported)}`,
			);
			setImportKind(null);
			setImportFile(null);
			setImportConfirm(false);
		} catch (error: unknown) {
			const detail =
				(error as { response?: { data?: { detail?: string } } })
					?.response?.data?.detail || "Import failed.";
			setImportMessage(detail);
		} finally {
			setImportBusy(false);
		}
	};

	if (!canManage) {
		return (
			<div>
				<PageHeader
					title="Database & Backup"
					description="Administrator access only"
				/>
				<div className="px-6 py-12 text-center text-muted-foreground">
					You do not have permission to view this page.
				</div>
			</div>
		);
	}

	const infoRow = (label: string, value: string, secret = false) => (
		<div className="flex items-center justify-between gap-3 py-2 border-b border-border last:border-0">
			<span className="text-sm text-muted-foreground">{label}</span>
			<div className="flex items-center gap-2 min-w-0">
				<span className="text-sm font-mono truncate">
					{secret && !revealPassword ? "•".repeat(12) : value}
				</span>
				{secret && (
					<button
						onClick={() => setRevealPassword((v) => !v)}
						className="p-1 hover:bg-muted rounded transition"
						title={revealPassword ? "Hide" : "Reveal"}
					>
						{revealPassword ? (
							<EyeOff className="w-4 h-4" />
						) : (
							<Eye className="w-4 h-4" />
						)}
					</button>
				)}
				<button
					onClick={() => copyValue(label, value)}
					className="p-1 hover:bg-muted rounded transition"
					title="Copy"
				>
					{copied === label ? (
						<Check className="w-4 h-4 text-green-500" />
					) : (
						<Copy className="w-4 h-4 text-muted-foreground" />
					)}
				</button>
			</div>
		</div>
	);

	const statCard = (
		icon: React.ReactNode,
		label: string,
		value: React.ReactNode,
	) => (
		<div className="bg-card text-card-foreground rounded-lg border border-border p-4 flex items-center gap-3">
			<div className="w-9 h-9 rounded-lg bg-primary/10 text-primary flex items-center justify-center flex-shrink-0">
				{icon}
			</div>
			<div className="min-w-0">
				<div className="text-xs text-muted-foreground">{label}</div>
				<div className="text-base font-semibold truncate">{value}</div>
			</div>
		</div>
	);

	const tabButton = (id: Tab, label: string) => (
		<button
			onClick={() => setTab(id)}
			className={`px-4 py-2 text-sm font-medium rounded-lg transition cursor-pointer ${
				tab === id
					? "bg-primary text-primary-foreground"
					: "text-muted-foreground hover:bg-muted"
			}`}
		>
			{label}
		</button>
	);

	return (
		<div>
			<PageHeader
				title="Database & Backup"
				description="Server status, migration version, table browser, and full export and restore"
			/>

			<div className="px-6 py-6 space-y-6">
				{/* Tabs */}
				<div className="flex gap-2 border-b border-border pb-3">
					{tabButton("overview", "Overview")}
					{tabButton("tables", "Tables")}
					{tabButton("backup", "Backup & Restore")}
				</div>

				{/* Overview tab */}
				{tab === "overview" && (
					<div className="space-y-6">
						{/* Stat cards */}
						<div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
							{statCard(
								<Server className="w-5 h-5" />,
								"PostgreSQL",
								overview?.postgres_version ?? "…",
							)}
							{statCard(
								<HardDrive className="w-5 h-5" />,
								"Database size",
								overview?.database_size ?? "…",
							)}
							{statCard(
								<Boxes className="w-5 h-5" />,
								"Tables",
								overview?.table_count ?? "…",
							)}
							{statCard(
								<GitBranch className="w-5 h-5" />,
								"Schema version",
								overview ? (
									<span className="flex items-center gap-2">
										<span className="font-mono text-sm truncate">
											{overview.alembic_current ??
												"unknown"}
										</span>
										{overview.alembic_head && (
											<span
												className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
													overview.up_to_date
														? "bg-green-500/15 text-green-600 dark:text-green-400"
														: "bg-yellow-500/15 text-yellow-600 dark:text-yellow-400"
												}`}
											>
												{overview.up_to_date
													? "Up to date"
													: "Update pending"}
											</span>
										)}
									</span>
								) : (
									"…"
								),
							)}
						</div>

						<div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
							{/* Connection info */}
							<section className="bg-card text-card-foreground rounded-lg border border-border p-5 h-full">
								<div className="flex items-center gap-2 mb-4">
									<Database className="w-5 h-5 text-primary" />
									<h2 className="text-lg font-semibold">
										Database Access
									</h2>
								</div>
								{info ? (
									<div>
										<div className="grid grid-cols-1 sm:grid-cols-2 sm:gap-x-6">
											{infoRow("Host", info.host)}
											{infoRow("Port", String(info.port))}
											{infoRow("Database", info.database)}
											{infoRow("User", info.user)}
										</div>
										{infoRow(
											"Password",
											info.password,
											true,
										)}
										{infoRow(
											"Connection string",
											info.connection_string,
											true,
										)}
										<p className="text-xs text-muted-foreground mt-3">
											Connect from this machine on the
											localhost-bound port, or from your
											server address if you exposed the
											port.
										</p>
									</div>
								) : (
									<div className="text-sm text-muted-foreground">
										Loading...
									</div>
								)}
							</section>

							{/* Migration detail */}
							<section className="bg-card text-card-foreground rounded-lg border border-border p-5 h-full">
								<div className="flex items-center gap-2 mb-4">
									<GitBranch className="w-5 h-5 text-primary" />
									<h2 className="text-lg font-semibold">
										Migration Version
									</h2>
								</div>
								{overview ? (
									<div>
										{infoRow(
											"Current revision",
											overview.alembic_current ??
												"unknown",
										)}
										{infoRow(
											"Latest revision",
											overview.alembic_head ?? "unknown",
										)}
										<div className="flex items-center justify-between py-2">
											<span className="text-sm text-muted-foreground">
												Status
											</span>
											{overview.alembic_head ? (
												<span
													className={`text-xs font-medium px-2 py-1 rounded-full ${
														overview.up_to_date
															? "bg-green-500/15 text-green-600 dark:text-green-400"
															: "bg-yellow-500/15 text-yellow-600 dark:text-yellow-400"
													}`}
												>
													{overview.up_to_date
														? "Schema up to date"
														: "Migrations pending"}
												</span>
											) : (
												<span className="text-xs text-muted-foreground">
													Unknown
												</span>
											)}
										</div>
										<p className="text-xs text-muted-foreground mt-3">
											The current revision is what the
											database is on. The latest revision
											is what this build ships. They match
											when all migrations have run.
										</p>
									</div>
								) : (
									<div className="text-sm text-muted-foreground">
										Loading...
									</div>
								)}
							</section>
						</div>
					</div>
				)}

				{/* Tables tab */}
				{tab === "tables" && (
					<section className="bg-card text-card-foreground rounded-lg border border-border p-5">
						<div className="flex items-center gap-2 mb-4">
							<TableIcon className="w-5 h-5 text-primary" />
							<h2 className="text-lg font-semibold">
								Table Browser
							</h2>
							<span className="text-xs text-muted-foreground">
								(read-only)
							</span>
						</div>
						<div className="grid grid-cols-1 md:grid-cols-4 gap-4">
							<div className="md:col-span-1 space-y-1 max-h-[32rem] overflow-y-auto pr-2">
								{tables?.tables.map((t) => (
									<button
										key={t.name}
										onClick={() => {
											setSelectedTable(t.name);
											setTableSearch("");
											setColumnFilters({});
											setOpenFilterColumns(new Set());
										}}
										className={`w-full text-left px-3 py-2 rounded-lg text-sm transition cursor-pointer ${
											selectedTable === t.name
												? "bg-primary/10 text-primary"
												: "hover:bg-muted"
										}`}
									>
										<span className="truncate block">
											{t.name}
										</span>
										<span className="text-xs text-muted-foreground">
											{t.row_count.toLocaleString()} rows
											· {t.size_pretty}
										</span>
									</button>
								))}
							</div>

							<div className="md:col-span-3 min-w-0">
								{!selectedTable ? (
									<div className="flex items-center justify-center h-40 text-sm text-muted-foreground">
										Select a table to browse its rows.
									</div>
								) : (
									<div>
										<div className="flex items-center justify-between gap-3 mb-2">
											<span className="text-sm font-medium whitespace-nowrap">
												{selectedTable}{" "}
												<span className="text-muted-foreground">
													(
													{tableTotal.toLocaleString()}{" "}
													{hasActiveFilters
														? "matching rows"
														: "rows"}
													)
												</span>
											</span>
											{hasActiveFilters && (
												<button
													onClick={clearTableFilters}
													className="flex items-center gap-1 px-2 py-1 text-xs text-muted-foreground hover:bg-muted rounded transition whitespace-nowrap cursor-pointer"
													title="Clear search and column filters"
												>
													<X className="w-3 h-3" />
													Clear filters
												</button>
											)}
											<span className="flex items-center gap-2 text-xs text-muted-foreground whitespace-nowrap ml-auto">
												{rowsLoading && (
													<Loader2 className="w-3.5 h-3.5 animate-spin" />
												)}
												{allRows.length.toLocaleString()}{" "}
												loaded
											</span>
										</div>
										<div className="relative mb-2">
											<Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
											<input
												type="text"
												value={tableSearch}
												onChange={(e) =>
													setTableSearch(
														e.target.value,
													)
												}
												placeholder="Search all columns..."
												className="w-full pl-10 pr-4 py-2 bg-muted border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary text-sm"
											/>
										</div>
										<div
											ref={scrollRootRef}
											className="overflow-x-auto border border-border rounded-lg max-h-[32rem] overflow-y-auto"
										>
											<table className="w-full text-xs">
												<thead className="bg-muted sticky top-0 z-10">
													<tr>
														{tableColumns.map(
															(c) => (
																<th
																	key={c}
																	className="text-left px-3 py-2 font-medium whitespace-nowrap"
																>
																	<span className="flex items-center gap-1">
																		{c}
																		<button
																			onClick={() =>
																				toggleFilterColumn(
																					c,
																				)
																			}
																			className={`p-0.5 rounded hover:bg-muted/80 transition cursor-pointer ${
																				(
																					columnFilters[
																						c
																					] ??
																					""
																				).trim() !==
																				""
																					? "text-primary"
																					: openFilterColumns.has(
																								c,
																						  )
																						? "text-foreground"
																						: "text-muted-foreground"
																			}`}
																			title={`Filter ${c}`}
																		>
																			<Filter className="w-3 h-3" />
																		</button>
																	</span>
																</th>
															),
														)}
													</tr>
													{/* Filter row, shown once any column filter is opened or has a value.
													    Values combine with AND. */}
													{tableColumns.some(
														(c) =>
															openFilterColumns.has(
																c,
															) ||
															(
																columnFilters[
																	c
																] ?? ""
															).trim() !== "",
													) && (
														<tr>
															{tableColumns.map(
																(c) => (
																	<th
																		key={c}
																		className="px-2 py-1 font-normal"
																	>
																		{(openFilterColumns.has(
																			c,
																		) ||
																			(
																				columnFilters[
																					c
																				] ??
																				""
																			).trim() !==
																				"") && (
																			<input
																				type="text"
																				autoFocus={openFilterColumns.has(
																					c,
																				)}
																				value={
																					columnFilters[
																						c
																					] ??
																					""
																				}
																				onChange={(
																					e,
																				) => {
																					setColumnFilters(
																						(
																							f,
																						) => ({
																							...f,
																							[c]: e
																								.target
																								.value,
																						}),
																					);
																				}}
																				placeholder="Filter..."
																				className="w-full px-2 py-1 text-xs bg-background border border-border rounded focus:outline-none focus:ring-2 focus:ring-primary"
																			/>
																		)}
																	</th>
																),
															)}
														</tr>
													)}
												</thead>
												<tbody>
													{allRows.map((row, i) => (
														<tr
															key={i}
															className="border-t border-border hover:bg-muted/30"
														>
															{tableColumns.map(
																(c) => (
																	<td
																		key={c}
																		className="px-3 py-2 whitespace-nowrap max-w-xs truncate"
																		title={cellText(
																			row[
																				c
																			],
																		)}
																	>
																		{cellText(
																			row[
																				c
																			],
																		)}
																	</td>
																),
															)}
														</tr>
													))}
												</tbody>
											</table>
											<div
												ref={setSentinel}
												className="flex items-center justify-center py-3"
											>
												{isFetchingNextPage ? (
													<Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
												) : !hasNextPage &&
												  allRows.length > 0 ? (
													<span className="text-xs text-muted-foreground">
														All{" "}
														{tableTotal.toLocaleString()}{" "}
														rows loaded
													</span>
												) : null}
											</div>
										</div>
									</div>
								)}
							</div>
						</div>
					</section>
				)}

				{/* Backup & Restore tab */}
				{tab === "backup" && (
					<section className="bg-card text-card-foreground rounded-lg border border-border p-5">
						<div className="flex items-center gap-2 mb-1">
							<Download className="w-5 h-5 text-primary" />
							<h2 className="text-lg font-semibold">
								Backup & Restore
							</h2>
						</div>
						<p className="text-xs text-muted-foreground mb-4">
							Download a backup of this instance. Exports run
							against the live database.
						</p>
						<div className="grid grid-cols-1 md:grid-cols-3 gap-3">
							<button
								onClick={() =>
									runExport(
										"/admin/export/full",
										"kinora-backup.zip",
									)
								}
								disabled={!!downloading}
								className="flex flex-col items-start gap-3 p-4 rounded-lg border border-border hover:border-primary/50 hover:bg-muted/50 text-left transition cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
							>
								<span className="flex items-center gap-2 w-full">
									<Boxes className="w-5 h-5 text-primary shrink-0" />
									<span className="text-sm font-medium">
										Full Backup
									</span>
									<span className="ml-auto px-2 py-0.5 bg-primary/20 text-primary rounded text-xs">
										Recommended
									</span>
								</span>
								<span className="text-xs text-muted-foreground">
									Everything in one archive: the complete
									database dump plus the portable settings
									file and a manifest.
								</span>
								<span className="flex items-center gap-1.5 text-xs text-primary">
									{downloading === "/admin/export/full" ? (
										<>
											<Loader2 className="w-3.5 h-3.5 animate-spin" />
											Preparing...
										</>
									) : (
										<>
											<Download className="w-3.5 h-3.5" />
											Download .zip
										</>
									)}
								</span>
							</button>
							<button
								onClick={() =>
									runExport(
										"/admin/export/database",
										"kinora-db.sql",
									)
								}
								disabled={!!downloading}
								className="flex flex-col items-start gap-3 p-4 rounded-lg border border-border hover:border-primary/50 hover:bg-muted/50 text-left transition cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
							>
								<span className="flex items-center gap-2">
									<Database className="w-5 h-5 text-primary shrink-0" />
									<span className="text-sm font-medium">
										Database
									</span>
								</span>
								<span className="text-xs text-muted-foreground">
									Plain SQL dump of every table. Restorable
									here or with psql against any PostgreSQL
									server.
								</span>
								<span className="flex items-center gap-1.5 text-xs text-primary">
									{downloading ===
									"/admin/export/database" ? (
										<>
											<Loader2 className="w-3.5 h-3.5 animate-spin" />
											Preparing...
										</>
									) : (
										<>
											<Download className="w-3.5 h-3.5" />
											Download .sql
										</>
									)}
								</span>
							</button>
							<button
								onClick={() =>
									runExport(
										"/admin/export/settings",
										"kinora-settings.json",
									)
								}
								disabled={!!downloading}
								className="flex flex-col items-start gap-3 p-4 rounded-lg border border-border hover:border-primary/50 hover:bg-muted/50 text-left transition cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
							>
								<span className="flex items-center gap-2">
									<FileJson className="w-5 h-5 text-primary shrink-0" />
									<span className="text-sm font-medium">
										Settings
									</span>
								</span>
								<span className="text-xs text-muted-foreground">
									Profiles, root folders, and app settings in
									a portable file. Importable on any Kinora
									instance.
								</span>
								<span className="flex items-center gap-1.5 text-xs text-primary">
									{downloading ===
									"/admin/export/settings" ? (
										<>
											<Loader2 className="w-3.5 h-3.5 animate-spin" />
											Preparing...
										</>
									) : (
										<>
											<Download className="w-3.5 h-3.5" />
											Download .json
										</>
									)}
								</span>
							</button>
						</div>

						<div className="mt-5 pt-5 border-t border-border">
							<div className="flex items-center gap-2 mb-1">
								<Upload className="w-4 h-4 text-muted-foreground" />
								<h3 className="text-sm font-semibold">
									Restore / Import
								</h3>
							</div>
							<p className="text-xs text-muted-foreground mb-4">
								Restore from a backup created above. Restoring
								overwrites current data, so it asks for
								confirmation before running.
							</p>

							{/* Step 1: what to restore */}
							<div className="grid grid-cols-1 md:grid-cols-2 gap-3">
								<button
									onClick={() => {
										setImportKind("database");
										setImportFile(null);
										setImportConfirm(false);
										setImportMessage(null);
									}}
									className={`flex items-start gap-3 p-4 rounded-lg border text-left transition cursor-pointer ${
										importKind === "database"
											? "border-primary bg-primary/10"
											: "border-border hover:border-primary/50 hover:bg-muted/50"
									}`}
								>
									<Database className="w-5 h-5 text-primary mt-0.5 shrink-0" />
									<span>
										<span className="block text-sm font-medium">
											Database (.sql)
										</span>
										<span className="block text-xs text-muted-foreground mt-1">
											Full restore of every table from a
											database dump. Replaces all current
											data.
										</span>
									</span>
								</button>
								<button
									onClick={() => {
										setImportKind("settings");
										setImportFile(null);
										setImportConfirm(false);
										setImportMessage(null);
									}}
									className={`flex items-start gap-3 p-4 rounded-lg border text-left transition cursor-pointer ${
										importKind === "settings"
											? "border-primary bg-primary/10"
											: "border-border hover:border-primary/50 hover:bg-muted/50"
									}`}
								>
									<FileJson className="w-5 h-5 text-primary mt-0.5 shrink-0" />
									<span>
										<span className="block text-sm font-medium">
											Settings (.json)
										</span>
										<span className="block text-xs text-muted-foreground mt-1">
											Profiles, root folders, and app
											settings. Updates matching entries,
											leaves everything else untouched.
										</span>
									</span>
								</button>
							</div>

							{/* Step 2: pick the file */}
							{importKind && (
								<label className="mt-3 flex items-center justify-between gap-3 p-4 rounded-lg border border-dashed border-border hover:border-primary/50 hover:bg-muted/30 transition cursor-pointer">
									<span className="flex items-center gap-3 min-w-0">
										<Upload className="w-5 h-5 text-muted-foreground shrink-0" />
										<span className="min-w-0">
											<span className="block text-sm font-medium truncate">
												{importFile
													? importFile.name
													: importKind === "database"
														? "Choose a .sql dump file"
														: "Choose a settings .json file"}
											</span>
											<span className="block text-xs text-muted-foreground mt-0.5">
												{importFile
													? `${(importFile.size / (1024 * 1024)).toFixed(2)} MB`
													: "Click to browse"}
											</span>
										</span>
									</span>
									{importFile && (
										<Check className="w-4 h-4 text-green-500 shrink-0" />
									)}
									<input
										type="file"
										className="hidden"
										accept={
											importKind === "database"
												? ".sql"
												: ".json"
										}
										onChange={(e) => {
											setImportFile(
												e.target.files?.[0] || null,
											);
											setImportConfirm(false);
											setImportMessage(null);
										}}
									/>
								</label>
							)}

							{/* Step 3: confirm and run */}
							{importKind && importFile && (
								<div className="mt-3 p-4 rounded-lg border border-yellow-500/40 bg-yellow-500/10">
									<div className="flex items-start gap-3">
										<AlertTriangle className="w-4 h-4 text-yellow-500 mt-0.5 shrink-0" />
										<div className="flex-1">
											<p className="text-sm text-yellow-600 dark:text-yellow-400 font-medium">
												This overwrites current{" "}
												{importKind === "database"
													? "data"
													: "settings"}{" "}
												and cannot be undone.
											</p>
											<label className="flex items-center gap-2 mt-2 text-sm cursor-pointer">
												<input
													type="checkbox"
													checked={importConfirm}
													onChange={(e) =>
														setImportConfirm(
															e.target.checked,
														)
													}
												/>
												I understand, proceed with the
												restore.
											</label>
											<div className="flex items-center gap-2 mt-3">
												<button
													onClick={runImport}
													disabled={
														!importConfirm ||
														importBusy
													}
													className="flex items-center gap-2 px-4 py-2 bg-destructive text-destructive-foreground rounded-lg hover:opacity-90 transition text-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
												>
													{importBusy ? (
														<Loader2 className="w-4 h-4 animate-spin" />
													) : (
														<Upload className="w-4 h-4" />
													)}
													Restore now
												</button>
												<button
													onClick={() => {
														setImportKind(null);
														setImportFile(null);
														setImportConfirm(false);
														setImportMessage(null);
													}}
													disabled={importBusy}
													className="px-3 py-2 text-sm text-muted-foreground hover:bg-muted rounded-lg transition cursor-pointer disabled:opacity-50"
												>
													Cancel
												</button>
											</div>
										</div>
									</div>
								</div>
							)}
							{importMessage && (
								<p className="mt-3 text-sm text-muted-foreground break-words">
									{importMessage}
								</p>
							)}
						</div>
					</section>
				)}
			</div>
		</div>
	);
}
