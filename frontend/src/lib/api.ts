import axios from "axios";

// Prefer same-origin requests in production/Desktop. An explicit API URL is
// still supported for split frontend/backend deployments and local development.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const CSRF_STORAGE_KEY = "dynamicpro_csrf_token";

function readStoredCsrfToken(): string {
  if (typeof window === "undefined") return "";
  try {
    const token = window.sessionStorage.getItem(CSRF_STORAGE_KEY);
    return typeof token === "string" ? token : "";
  } catch {
    return "";
  }
}

let csrfToken = readStoredCsrfToken();

export function setCsrfToken(token?: string): void {
  csrfToken = typeof token === "string" ? token : "";
  if (typeof window === "undefined") return;
  try {
    if (csrfToken) window.sessionStorage.setItem(CSRF_STORAGE_KEY, csrfToken);
    else window.sessionStorage.removeItem(CSRF_STORAGE_KEY);
  } catch {
    // sessionStorage may be unavailable in hardened/private browser contexts.
  }
}

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((request) => {
  if (!csrfToken) csrfToken = readStoredCsrfToken();
  if (csrfToken && request.method && !["get", "head", "options"].includes(request.method.toLowerCase())) {
    request.headers.set("X-CSRF-Token", csrfToken);
  }
  return request;
});

api.interceptors.response.use(
  (res) => {
    const token = res.headers["x-csrf-token"];
    if (typeof token === "string" && token) {
      setCsrfToken(token);
    }
    return res;
  },
  async (error) => {
    const responseToken = error.response?.headers?.["x-csrf-token"];
    if (typeof responseToken === "string" && responseToken) {
      setCsrfToken(responseToken);
    }
    const original = error.config as (typeof error.config & { _retry?: boolean }) | undefined;
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true;
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        setCsrfToken();
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default api;