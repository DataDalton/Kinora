import type { MetadataRoute } from "next";

// Web app manifest served at /manifest.webmanifest. Colors match the dark theme
// background and primary accent in globals.css.
export default function manifest(): MetadataRoute.Manifest {
	return {
		id: "/",
		name: "Kinora",
		short_name: "Kinora",
		description: "Unified media management",
		start_url: "/",
		scope: "/",
		display: "standalone",
		background_color: "#0a0a0a",
		theme_color: "#0a0a0a",
		icons: [
			{
				src: "/icons/icon-192.png",
				sizes: "192x192",
				type: "image/png",
				purpose: "any",
			},
			{
				src: "/icons/icon-512.png",
				sizes: "512x512",
				type: "image/png",
				purpose: "any",
			},
			{
				src: "/icons/icon-512.png",
				sizes: "512x512",
				type: "image/png",
				purpose: "maskable",
			},
			{
				src: "/icons/icon.svg",
				sizes: "any",
				type: "image/svg+xml",
			},
		],
	};
}
