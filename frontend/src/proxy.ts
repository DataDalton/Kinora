import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function proxy(request: NextRequest) {
	const token = request.cookies.get("access_token")?.value;

	const publicPaths = ["/login", "/register"];
	const isPublicPath = publicPaths.some((path) =>
		request.nextUrl.pathname.startsWith(path),
	);

	if (!token && !isPublicPath) {
		return NextResponse.redirect(new URL("/login", request.url));
	}

	if (token && isPublicPath) {
		return NextResponse.redirect(new URL("/", request.url));
	}

	return NextResponse.next();
}

export const config = {
	matcher: [
		// The manifest, service worker, and icons are fetched without the session cookie,
		// so they must not redirect to the login page.
		"/((?!api|_next/static|_next/image|favicon.ico|manifest.webmanifest|sw.js|icons/).*)",
	],
};
