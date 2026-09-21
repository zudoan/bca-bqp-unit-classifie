import type { PortalSession, UserRole } from "../types/portal";

const AUTH_BASE_URL = "/api/v1/auth";

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
    const body = await response.json() as { detail?: string | Array<{ msg?: string }> };
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
    return await fetch(`${AUTH_BASE_URL}${path}`, {
      ...init,
      credentials: "include",
      headers: init?.body
        ? { "Content-Type": "application/json", ...init.headers }
        : init?.headers,
    });
  } catch {
    throw new Error("Không thể kết nối dịch vụ tài khoản. Vui lòng kiểm tra máy chủ và thử lại.");
  }
}

export async function authenticateAccount(username: string, password: string, remember: boolean) {
  const response = await authRequest("/login", {
    method: "POST",
    body: JSON.stringify({ username, password, remember }),
  });
  if (!response.ok) throw new Error(await errorMessage(response, "Không thể đăng nhập tài khoản."));
  return toPortalSession((await response.json() as AuthenticationResponse).user);
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
  return toPortalSession((await response.json() as AuthenticationResponse).user);
}

export async function restoreSession(): Promise<PortalSession | null> {
  const response = await authRequest("/me");
  if (response.status === 401) return null;
  if (!response.ok) throw new Error(await errorMessage(response, "Không thể kiểm tra phiên đăng nhập."));
  return toPortalSession((await response.json() as AuthenticationResponse).user);
}

export async function logoutAccount() {
  const response = await authRequest("/logout", { method: "POST" });
  if (!response.ok && response.status !== 401) {
    throw new Error(await errorMessage(response, "Không thể đăng xuất tài khoản."));
  }
}
