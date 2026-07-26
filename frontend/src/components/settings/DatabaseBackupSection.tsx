"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
	ChevronLeft,
	ChevronRight,
	AlertTriangle,
	Loader2,
	Server,
	GitBranch,
	HardDrive,
	Boxes,
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
	total: number;
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

export default function DatabaseBackupSection() {
	const { hasPermission } = usePermissions();
	const canManage = hasPermission("system.admin");

	const [tab, setTab] = useState<Tab>("overview");
	const [revealPassword, setRevealPassword] = useState(false);
	const [copied, setCopied] = useState<string | null>(null);
	const [selectedTable, setSelectedTable] = useState<string | null>(null);
	const [page, setPage] = useState(0);
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

	const { data: rows, isFetching: rowsLoading } = useQuery<TableRows>({
		queryKey: ["admin-db-table", selectedTable, page],
		queryFn: async () =>
			(
				await api.get(`/admin/database/tables/${selectedTable}`, {
					params: { limit: PAGE_SIZE, offset: page * PAGE_SIZE },
				})
			).data,
		enabled: canManage && !!selectedTable,
	});

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

	const totalPages = rows
		? Math.max(1, Math.ceil(rows.total / PAGE_SIZE))
		: 1;

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
											setPage(0);
										}}
										className={`w-full text-left px-3 py-2 rounded-lg text-sm transition ${
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
										<div className="flex items-center justify-between mb-2">
											<span className="text-sm font-medium">
												{selectedTable}{" "}
												<span className="text-muted-foreground">
													(
													{rows?.total.toLocaleString() ??
														0}{" "}
													rows)
												</span>
											</span>
											<div className="flex items-center gap-2">
												<button
													onClick={() =>
														setPage((p) =>
															Math.max(0, p - 1),
														)
													}
													disabled={
														page === 0 ||
														rowsLoading
													}
													className="p-1.5 hover:bg-muted rounded transition disabled:opacity-40"
												>
													<ChevronLeft className="w-4 h-4" />
												</button>
												<span className="text-xs text-muted-foreground">
													{page + 1} / {totalPages}
												</span>
												<button
													onClick={() =>
														setPage((p) => p + 1)
													}
													disabled={
														page + 1 >=
															totalPages ||
														rowsLoading
													}
													className="p-1.5 hover:bg-muted rounded transition disabled:opacity-40"
												>
													<ChevronRight className="w-4 h-4" />
												</button>
											</div>
										</div>
										<div className="overflow-x-auto border border-border rounded-lg max-h-[32rem]">
											<table className="w-full text-xs">
												<thead className="bg-muted/50 sticky top-0">
													<tr>
														{rows?.columns.map(
															(c) => (
																<th
																	key={c}
																	className="text-left px-3 py-2 font-medium whitespace-nowrap"
																>
																	{c}
																</th>
															),
														)}
													</tr>
												</thead>
												<tbody>
													{rows?.rows.map(
														(row, i) => (
															<tr
																key={i}
																className="border-t border-border hover:bg-muted/30"
															>
																{rows.columns.map(
																	(c) => (
																		<td
																			key={
																				c
																			}
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
														),
													)}
												</tbody>
											</table>
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
						<div className="flex items-center gap-2 mb-4">
							<Download className="w-5 h-5 text-primary" />
							<h2 className="text-lg font-semibold">
								Backup & Restore
							</h2>
						</div>
						<div className="flex flex-wrap gap-3">
							<button
								onClick={() =>
									runExport(
										"/admin/export/full",
										"kinora-backup.zip",
									)
								}
								disabled={!!downloading}
								className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition text-sm"
							>
								{downloading === "/admin/export/full" ? (
									<Loader2 className="w-4 h-4 animate-spin" />
								) : (
									<Download className="w-4 h-4" />
								)}
								Full Backup (.zip)
							</button>
							<button
								onClick={() =>
									runExport(
										"/admin/export/database",
										"kinora-db.sql",
									)
								}
								disabled={!!downloading}
								className="flex items-center gap-2 px-4 py-2 bg-muted hover:bg-muted/80 rounded-lg transition text-sm"
							>
								{downloading === "/admin/export/database" ? (
									<Loader2 className="w-4 h-4 animate-spin" />
								) : (
									<Download className="w-4 h-4" />
								)}
								Database (.sql)
							</button>
							<button
								onClick={() =>
									runExport(
										"/admin/export/settings",
										"kinora-settings.json",
									)
								}
								disabled={!!downloading}
								className="flex items-center gap-2 px-4 py-2 bg-muted hover:bg-muted/80 rounded-lg transition text-sm"
							>
								{downloading === "/admin/export/settings" ? (
									<Loader2 className="w-4 h-4 animate-spin" />
								) : (
									<Download className="w-4 h-4" />
								)}
								Settings (.json)
							</button>
						</div>

						<div className="mt-5 pt-5 border-t border-border">
							<div className="flex items-center gap-2 mb-3">
								<Upload className="w-4 h-4 text-muted-foreground" />
								<h3 className="text-sm font-semibold">
									Restore / Import
								</h3>
							</div>
							<div className="flex flex-wrap items-center gap-3">
								<select
									value={importKind || ""}
									onChange={(e) => {
										setImportKind(
											(e.target.value || null) as
												| "database"
												| "settings"
												| null,
										);
										setImportFile(null);
										setImportConfirm(false);
										setImportMessage(null);
									}}
									className="px-3 py-2 rounded-lg border border-border bg-background text-sm"
								>
									<option value="">
										Choose what to restore...
									</option>
									<option value="database">
										Database (.sql dump)
									</option>
									<option value="settings">
										Settings (.json)
									</option>
								</select>
								{importKind && (
									<input
										type="file"
										accept={
											importKind === "database"
												? ".sql"
												: ".json"
										}
										onChange={(e) =>
											setImportFile(
												e.target.files?.[0] || null,
											)
										}
										className="text-sm"
									/>
								)}
							</div>

							{importKind && importFile && (
								<div className="mt-3 p-3 rounded-lg border border-yellow-500/40 bg-yellow-500/10">
									<div className="flex items-start gap-2">
										<AlertTriangle className="w-4 h-4 text-yellow-500 mt-0.5 flex-shrink-0" />
										<div className="flex-1">
											<p className="text-sm text-yellow-600 dark:text-yellow-400 font-medium">
												This overwrites current{" "}
												{importKind === "database"
													? "data"
													: "settings"}
												.
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
											<button
												onClick={runImport}
												disabled={
													!importConfirm || importBusy
												}
												className="mt-3 flex items-center gap-2 px-4 py-2 bg-destructive text-destructive-foreground rounded-lg hover:opacity-90 transition text-sm disabled:opacity-50"
											>
												{importBusy ? (
													<Loader2 className="w-4 h-4 animate-spin" />
												) : (
													<Upload className="w-4 h-4" />
												)}
												Restore now
											</button>
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
