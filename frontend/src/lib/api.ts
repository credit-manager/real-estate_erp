import axios from "axios";

// Prefer same-origin requests in production/Desktop. An explicit API URL is
// still supported for split frontend/backend deployments and local development.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
let csrfToken = "";

export function setCsrfToken(token?: string): void {
  csrfToken = typeof token === "string" ? token : "";
}

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((request) => {
  if (csrfToken && request.method && !["get", "head", "options"].includes(request.method.toLowerCase())) {
    request.headers.set("X-CSRF-Token", csrfToken);
  }
  return request;
});

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config as (typeof error.config & { _retry?: boolean }) | undefined;
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true;
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default api;
