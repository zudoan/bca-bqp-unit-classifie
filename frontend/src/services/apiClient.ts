const configuredBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").trim();

export const API_BASE_URL = configuredBaseUrl.replace(/\/+$/, "");

const PERSISTENT_TOKEN_KEY = "bca-bqp.auth.token";
const SESSION_TOKEN_KEY = "bca-bqp.auth.session-token";

export function apiUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

export function getAuthToken() {
  return sessionStorage.getItem(SESSION_TOKEN_KEY) || localStorage.getItem(PERSISTENT_TOKEN_KEY);
}

export function saveAuthToken(token: string, remember: boolean) {
  clearAuthToken();
  const storage = remember ? localStorage : sessionStorage;
  const key = remember ? PERSISTENT_TOKEN_KEY : SESSION_TOKEN_KEY;
  storage.setItem(key, token);
}

export function clearAuthToken() {
  localStorage.removeItem(PERSISTENT_TOKEN_KEY);
  sessionStorage.removeItem(SESSION_TOKEN_KEY);
}

export function authenticatedHeaders(headers?: HeadersInit) {
  const result = new Headers(headers);
  const token = getAuthToken();
  if (token && !result.has("Authorization")) {
    result.set("Authorization", `Bearer ${token}`);
  }
  return result;
}
