import type { PortalSession, UserRole } from "../types/portal";
import {
  apiUrl,
  authenticatedHeaders,
  clearAuthToken,
  saveAuthToken,
} from "./apiClient";

const AUTH_BASE_PATH = "/api/v1/auth";

interface BackendUser {
  id: string;
  username: string;
  email: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

interface AuthenticationResponse {
  user: BackendUser;
  token?: string | null;
}

export interface RegistrationInput {
  displayName: string;
  email: string;
  username: string;
  password: string;
}

function toPortalSession(user: BackendUser): PortalSession {
  return {
    userId: user.id,
    username: user.username,
    displayName: user.display_name,
    email: user.email,
    role: user.role,
    isActive: user.is_active,
    createdAt: user.created_at,
    lastLoginAt: user.last_login_at,
  };
}

async function errorMessage(response: Response, fallback: string) {
  try {
    // Check if response has content before trying to parse JSON
    const text = await response.text();
    if (!text || text.trim() === '') {
      return fallback;
    }
    const body = JSON.parse(text) as { detail?: string | Array<{ msg?: string }> };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      const messages = body.detail.map((item) => item.msg).filter(Boolean);
      if (messages.length) return messages.join(" ");
    }
  } catch {
    // Use the friendly fallback when the backend did not return JSON.
  }
  return fallback;
}

async function authRequest(path: string, init?: RequestInit) {
  try {
    const headers = authenticatedHeaders(init?.headers);
    if (init?.body) headers.set("Content-Type", "application/json");
    return await fetch(apiUrl(`${AUTH_BASE_PATH}${path}`), {
      ...init,
      credentials: "include",
      headers,
    });
  } catch {
    throw new Error("Không thể kết nối dịch vụ tài khoản. Vui lòng kiểm tra máy chủ và thử lại.");
  }
}

async function authenticationBody(response: Response, remember?: boolean) {
  const text = await response.text();
  if (!text.trim()) {
    throw new Error("Backend trả về response rỗng. Vui lòng kiểm tra VITE_API_BASE_URL.");
  }
  let body: AuthenticationResponse;
  try {
    body = JSON.parse(text) as AuthenticationResponse;
  } catch {
    throw new Error("Backend không trả về dữ liệu JSON hợp lệ. Vui lòng kiểm tra VITE_API_BASE_URL.");
  }
  if (!body?.user) {
    throw new Error("Backend trả về response không đầy đủ. Vui lòng kiểm tra kết nối API.");
  }
  if (body.token && remember !== undefined) saveAuthToken(body.token, remember);
  return toPortalSession(body.user);
}

export async function authenticateAccount(username: string, password: string, remember: boolean) {
  const response = await authRequest("/login", {
    method: "POST",
    body: JSON.stringify({ username, password, remember }),
  });
  if (!response.ok) throw new Error(await errorMessage(response, "Không thể đăng nhập tài khoản."));
  return authenticationBody(response, remember);
}

export async function registerAccount(input: RegistrationInput, remember: boolean) {
  const response = await authRequest("/register", {
    method: "POST",
    body: JSON.stringify({
      display_name: input.displayName,
      email: input.email,
      username: input.username,
      password: input.password,
      remember,
    }),
  });
  if (!response.ok) throw new Error(await errorMessage(response, "Không thể tạo tài khoản."));
  return authenticationBody(response, remember);
}

export async function restoreSession(): Promise<PortalSession | null> {
  const response = await authRequest("/me");
  if (response.status === 401) {
    clearAuthToken();
    return null;
  }
  if (!response.ok) throw new Error(await errorMessage(response, "Không thể kiểm tra phiên đăng nhập."));
  return authenticationBody(response);
}

export async function logoutAccount() {
  try {
    const response = await authRequest("/logout", { method: "POST" });
    if (!response.ok && response.status !== 401) {
      throw new Error(await errorMessage(response, "Không thể đăng xuất tài khoản."));
    }
  } finally {
    clearAuthToken();
  }
}
