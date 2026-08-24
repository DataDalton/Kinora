"use client";

// Renders the torrent piece states as a compact grid, like qBittorrent/VueTorrent.
// 0 = missing, 1 = downloading, 2 = downloaded. Long piece arrays are downsampled
// into fixed-width cells so the map stays readable for large torrents.

interface PieceMapProps {
	pieces: number[];
	maxCells?: number;
}

export default function PieceMap({ pieces, maxCells = 200 }: PieceMapProps) {
	if (!pieces || pieces.length === 0) {
		return (
			<div className="text-xs text-muted-foreground">
				No piece data available
			</div>
		);
	}

	const cellCount = Math.min(pieces.length, maxCells);
	const chunkSize = pieces.length / cellCount;

	// Downsample: each cell summarizes a slice of pieces to the lowest completeness
	// present in that slice, so a partial cell never reads as fully done.
	const cells: number[] = [];
	for (let i = 0; i < cellCount; i++) {
		const start = Math.floor(i * chunkSize);
		const end = Math.floor((i + 1) * chunkSize);
		let hasDownloading = false;
		let allDone = true;
		for (let j = start; j < end; j++) {
			if (pieces[j] === 1) hasDownloading = true;
			if (pieces[j] !== 2) allDone = false;
		}
		cells.push(allDone ? 2 : hasDownloading ? 1 : 0);
	}

	const colorFor = (state: number) => {
		if (state === 2) return "bg-primary";
		if (state === 1) return "bg-yellow-500";
		return "bg-secondary";
	};

	return (
		<div className="flex flex-wrap gap-px rounded overflow-hidden">
			{cells.map((state, idx) => (
				<div
					key={idx}
					className={`h-3 flex-1 min-w-[3px] ${colorFor(state)}`}
					title={`Piece block ${idx + 1}: ${state === 2 ? "complete" : state === 1 ? "downloading" : "missing"}`}
				/>
			))}
		</div>
	);
}
