import type { UserRole } from "../types/portal";

export interface ManagedUser {
  id: string;
  username: string;
  email: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface UserListResponse {
  items: ManagedUser[];
  total: number;
  active_count: number;
  inactive_count: number;
  admin_count: number;
}

export interface UserFilters {
  query?: string;
  role?: UserRole | "";
  isActive?: boolean | null;
  signal?: AbortSignal;
}

export interface UserUpdate {
  display_name?: string;
  email?: string;
  role?: UserRole;
  is_active?: boolean;
}

async function adminError(response: Response, fallback: string) {
  try {
    const body = await response.json() as { detail?: string };
    if (body.detail) return body.detail;
  } catch {
    // Keep the fallback for non-JSON responses.
  }
  return fallback;
}

async function adminRequest(path: string, init?: RequestInit) {
  try {
    return await fetch(`/api/v1/admin${path}`, {
      ...init,
      credentials: "include",
      headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
    });
  } catch {
    throw new Error("Không thể kết nối dịch vụ quản trị người dùng.");
  }
}

export async function fetchUsers(filters: UserFilters = {}) {
  const search = new URLSearchParams({ limit: "100" });
  if (filters.query?.trim()) search.set("query", filters.query.trim());
  if (filters.role) search.set("role", filters.role);
  if (filters.isActive !== undefined && filters.isActive !== null) search.set("is_active", String(filters.isActive));
  const response = await adminRequest(`/users?${search}`, { signal: filters.signal });
  if (!response.ok) throw new Error(await adminError(response, "Không thể tải danh sách người dùng."));
  return response.json() as Promise<UserListResponse>;
}

export async function updateManagedUser(userId: string, values: UserUpdate) {
  const response = await adminRequest(`/users/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    body: JSON.stringify(values),
  });
  if (!response.ok) throw new Error(await adminError(response, "Không thể cập nhật tài khoản."));
  return response.json() as Promise<ManagedUser>;
}

export async function deactivateManagedUser(userId: string) {
  const response = await adminRequest(`/users/${encodeURIComponent(userId)}`, { method: "DELETE" });
  if (!response.ok) throw new Error(await adminError(response, "Không thể khóa tài khoản."));
}

