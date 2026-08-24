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

api.interceptors.response.use(
	(response) => response,
	async (error) => {
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
