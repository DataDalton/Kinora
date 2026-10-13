import axios from "axios";

const API_URL =
	process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const api = axios.create({
	baseURL: API_URL,
	headers: {
		"Content-Type": "application/json",
	},
});

api.interceptors.request.use((config) => {
	const cookieToken = document.cookie
		.split("; ")
		.find((row) => row.startsWith("access_token="));
	if (cookieToken) {
		const token = cookieToken.split("=")[1];
		config.headers.Authorization = `Bearer ${token}`;
	}
	return config;
});

// The server's explanation from a FastAPI error body. detail is a string for raised
// HTTP errors and a list of field errors for request validation failures.
function serverDetail(data: unknown): string | null {
	const detail = (data as { detail?: unknown } | undefined)?.detail;
	if (typeof detail === "string") return detail;
	if (Array.isArray(detail) && typeof detail[0]?.msg === "string") {
		return detail[0].msg;
	}
	return null;
}

api.interceptors.response.use(
	(response) => response,
	async (error) => {
		// Replaces the generic "Request failed with status code N" so any handler that
		// shows error.message shows the server's reason instead.
		const detail = serverDetail(error.response?.data);
		if (detail) error.message = detail;

		if (error.response?.status === 401) {
			const isLoginPage = window.location.pathname === "/login";
			if (!isLoginPage) {
				document.cookie = "access_token=; path=/; max-age=0";
				document.cookie = "refresh_token=; path=/; max-age=0";
				window.location.href = "/login";
			}
		}
		return Promise.reject(error);
	},
);

export default api;
