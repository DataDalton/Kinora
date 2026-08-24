"use client";

import {
	ResponsiveContainer,
	AreaChart,
	Area,
	XAxis,
	YAxis,
	Tooltip,
	CartesianGrid,
} from "recharts";
import type { TransferHistoryPoint } from "../../../types/downloads";
import { formatSpeed } from "./format";

const DL_COLOR = "#3b82f6"; // blue-500
const UL_COLOR = "#10b981"; // emerald-500

interface TransferChartProps {
	data: TransferHistoryPoint[];
	height?: number;
	rangeHours: number;
}

function formatTick(ts: string, rangeHours: number): string {
	const d = new Date(ts);
	if (rangeHours > 48) {
		return d.toLocaleDateString([], { month: "short", day: "numeric" });
	}
	return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

interface TooltipEntry {
	name?: string;
	value?: number;
	color?: string;
}

function ChartTooltip({
	active,
	payload,
	label,
}: {
	active?: boolean;
	payload?: TooltipEntry[];
	label?: string;
}) {
	if (!active || !payload || payload.length === 0) return null;
	return (
		<div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-lg">
			<p className="text-muted-foreground mb-1">
				{label ? new Date(label).toLocaleString() : ""}
			</p>
			{payload.map((entry, i) => (
				<p key={i} style={{ color: entry.color }}>
					{entry.name}: {formatSpeed(entry.value ?? 0)}
				</p>
			))}
		</div>
	);
}

export default function TransferChart({
	data,
	height = 220,
	rangeHours,
}: TransferChartProps) {
	if (!data || data.length === 0) {
		return (
			<div
				className="flex items-center justify-center text-sm text-muted-foreground"
				style={{ height }}
			>
				No history yet. Data is collected every minute.
			</div>
		);
	}

	return (
		<ResponsiveContainer width="100%" height={height}>
			<AreaChart
				data={data}
				margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
			>
				<defs>
					<linearGradient id="dlFill" x1="0" y1="0" x2="0" y2="1">
						<stop
							offset="0%"
							stopColor={DL_COLOR}
							stopOpacity={0.35}
						/>
						<stop
							offset="100%"
							stopColor={DL_COLOR}
							stopOpacity={0}
						/>
					</linearGradient>
					<linearGradient id="ulFill" x1="0" y1="0" x2="0" y2="1">
						<stop
							offset="0%"
							stopColor={UL_COLOR}
							stopOpacity={0.35}
						/>
						<stop
							offset="100%"
							stopColor={UL_COLOR}
							stopOpacity={0}
						/>
					</linearGradient>
				</defs>
				<CartesianGrid
					strokeDasharray="3 3"
					stroke="currentColor"
					className="text-border"
					opacity={0.4}
				/>
				<XAxis
					dataKey="timestamp"
					tickFormatter={(v) => formatTick(v, rangeHours)}
					tick={{ fontSize: 11 }}
					stroke="currentColor"
					className="text-muted-foreground"
					minTickGap={40}
				/>
				<YAxis
					tickFormatter={(v) => formatSpeed(v)}
					tick={{ fontSize: 11 }}
					stroke="currentColor"
					className="text-muted-foreground"
					width={64}
				/>
				<Tooltip content={<ChartTooltip />} />
				<Area
					type="monotone"
					dataKey="download_speed"
					name="Download"
					stroke={DL_COLOR}
					fill="url(#dlFill)"
					strokeWidth={2}
					isAnimationActive={false}
				/>
				<Area
					type="monotone"
					dataKey="upload_speed"
					name="Upload"
					stroke={UL_COLOR}
					fill="url(#ulFill)"
					strokeWidth={2}
					isAnimationActive={false}
				/>
			</AreaChart>
		</ResponsiveContainer>
	);
}
