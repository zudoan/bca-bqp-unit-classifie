import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { deactivateManagedUser, fetchUsers, updateManagedUser } from "../services/adminApi";
import type { ManagedUser } from "../services/adminApi";
import type { UserRole } from "../types/portal";
import { GoogleIcon } from "./Icons";

interface AdminUsersPanelProps {
  currentUserId: string;
}

function formatDate(value: string | null) {
  if (!value) return "Chưa đăng nhập";
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

export function AdminUsersPanel({ currentUserId }: AdminUsersPanelProps) {
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<UserRole | "">("");
  const [status, setStatus] = useState<"" | "active" | "inactive">("");
  const [metrics, setMetrics] = useState({ total: 0, active: 0, inactive: 0, admin: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState<ManagedUser | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError("");
      fetchUsers({
        query,
        role,
        isActive: status === "" ? null : status === "active",
        signal: controller.signal,
      })
        .then((response) => {
          setUsers(response.items);
          setMetrics({
            total: response.total,
            active: response.active_count,
            inactive: response.inactive_count,
            admin: response.admin_count,
          });
        })
        .catch((caught) => {
          if (caught instanceof DOMException && caught.name === "AbortError") return;
          setError(caught instanceof Error ? caught.message : "Không thể tải danh sách người dùng.");
        })
        .finally(() => setLoading(false));
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, revision, role, status]);

  function refresh(message?: string) {
    if (message) setNotice(message);
    setRevision((value) => value + 1);
  }

  async function toggleUser(user: ManagedUser) {
    setError("");
    setNotice("");
    if (user.id === currentUserId) {
      setError("Bạn không thể khóa tài khoản đang đăng nhập.");
      return;
    }
    if (user.is_active && !window.confirm(`Khóa tài khoản ${user.username}? Các phiên đang đăng nhập sẽ bị thu hồi.`)) return;
    try {
      if (user.is_active) {
        await deactivateManagedUser(user.id);
        refresh("Đã khóa tài khoản và thu hồi các phiên đăng nhập.");
      } else {
        await updateManagedUser(user.id, { is_active: true });
        refresh("Đã mở khóa tài khoản.");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể cập nhật trạng thái tài khoản.");
    }
  }

  return (
    <section className="user-admin-workspace">
      <div className="user-admin-metrics">
        <article><small>KẾT QUẢ HIỂN THỊ</small><strong>{metrics.total}</strong></article>
        <article><small>ĐANG HOẠT ĐỘNG</small><strong>{metrics.active}</strong></article>
        <article><small>ĐÃ KHÓA</small><strong>{metrics.inactive}</strong></article>
        <article><small>QUẢN TRỊ VIÊN</small><strong>{metrics.admin}</strong></article>
      </div>

      <div className="desk-panel user-admin-panel">
        <div className="user-admin-toolbar">
          <div><span className="section-code">KIỂM SOÁT TRUY CẬP</span><h2>Danh sách tài khoản hệ thống</h2><p>Quản lý hồ sơ, quyền truy cập và trạng thái hoạt động của người dùng.</p></div>
          <button type="button" onClick={() => refresh()} disabled={loading}><GoogleIcon name="refresh" size={18} /> Làm mới</button>
        </div>

        <div className="user-admin-filters">
          <label><GoogleIcon name="search" size={19} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm theo họ tên, username hoặc email..." /></label>
          <select value={role} onChange={(event) => setRole(event.target.value as UserRole | "")} aria-label="Lọc vai trò">
            <option value="">Tất cả vai trò</option><option value="admin">Quản trị viên</option><option value="user">Người dùng</option>
          </select>
          <select value={status} onChange={(event) => setStatus(event.target.value as typeof status)} aria-label="Lọc trạng thái">
            <option value="">Tất cả trạng thái</option><option value="active">Đang hoạt động</option><option value="inactive">Đã khóa</option>
          </select>
        </div>

        {error && <div className="admin-feedback is-error"><GoogleIcon name="error" size={18} filled />{error}</div>}
        {notice && <div className="admin-feedback is-success"><GoogleIcon name="task_alt" size={18} filled />{notice}</div>}

        <div className="user-table-wrap">
          <table className="user-table">
            <thead><tr><th>Người dùng</th><th>Vai trò</th><th>Trạng thái</th><th>Ngày tạo</th><th>Đăng nhập gần nhất</th><th aria-label="Thao tác" /></tr></thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td><span className="user-table-avatar">{user.display_name.charAt(0).toLocaleUpperCase("vi")}</span><div><strong>{user.display_name}{user.id === currentUserId && <i>Bạn</i>}</strong><small>@{user.username} · {user.email}</small></div></td>
                  <td><span className={`role-badge is-${user.role}`}>{user.role === "admin" ? "Quản trị viên" : "Người dùng"}</span></td>
                  <td><span className={`account-status is-${user.is_active ? "active" : "inactive"}`}><i />{user.is_active ? "Hoạt động" : "Đã khóa"}</span></td>
                  <td>{formatDate(user.created_at)}</td>
                  <td>{formatDate(user.last_login_at)}</td>
                  <td><div className="user-row-actions"><button type="button" onClick={() => { setNotice(""); setError(""); setEditing(user); }} title="Chỉnh sửa"><GoogleIcon name="edit" size={18} /></button><button type="button" disabled={user.id === currentUserId} onClick={() => void toggleUser(user)} title={user.is_active ? "Khóa tài khoản" : "Mở khóa tài khoản"}><GoogleIcon name={user.is_active ? "lock" : "lock_open"} size={18} /></button></div></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && !users.length && <div className="empty-user-list"><h3>Không có tài khoản phù hợp</h3><p>Thử thay đổi từ khóa hoặc điều kiện lọc.</p></div>}
          {loading && <div className="user-list-loading"><span className="spinner dark-spinner" /> Đang tải danh sách tài khoản...</div>}
        </div>
      </div>

      {editing && <UserEditDialog user={editing} currentUserId={currentUserId} onClose={() => setEditing(null)} onSaved={(message) => { setEditing(null); refresh(message); }} />}
    </section>
  );
}

function UserEditDialog({ user, currentUserId, onClose, onSaved }: { user: ManagedUser; currentUserId: string; onClose: () => void; onSaved: (message: string) => void }) {
  const [displayName, setDisplayName] = useState(user.display_name);
  const [email, setEmail] = useState(user.email);
  const [role, setRole] = useState<UserRole>(user.role);
  const [isActive, setIsActive] = useState(user.is_active);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const isSelf = user.id === currentUserId;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await updateManagedUser(user.id, { display_name: displayName, email, role, is_active: isActive });
      onSaved("Thông tin tài khoản đã được cập nhật.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể cập nhật tài khoản.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="history-modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="user-edit-dialog" role="dialog" aria-modal="true" aria-labelledby="user-edit-title" onMouseDown={(event) => event.stopPropagation()}>
        <header><div><span className="section-code">HỒ SƠ NGƯỜI DÙNG</span><h2 id="user-edit-title">Chỉnh sửa tài khoản</h2></div><button type="button" onClick={onClose} aria-label="Đóng"><GoogleIcon name="close" size={20} /></button></header>
        <form onSubmit={submit}>
          <label><span>Họ và tên</span><input value={displayName} onChange={(event) => setDisplayName(event.target.value)} required minLength={2} maxLength={120} /></label>
          <label><span>Email</span><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
          <label><span>Tên đăng nhập</span><input value={user.username} disabled /></label>
          <div className="user-edit-grid">
            <label><span>Vai trò</span><select value={role} onChange={(event) => setRole(event.target.value as UserRole)} disabled={isSelf}><option value="user">Người dùng</option><option value="admin">Quản trị viên</option></select></label>
            <label><span>Trạng thái</span><select value={isActive ? "active" : "inactive"} onChange={(event) => setIsActive(event.target.value === "active")} disabled={isSelf}><option value="active">Đang hoạt động</option><option value="inactive">Đã khóa</option></select></label>
          </div>
          {isSelf && <small className="self-edit-note">Bạn có thể sửa hồ sơ nhưng không thể tự đổi quyền hoặc khóa tài khoản của mình.</small>}
          {error && <div className="admin-feedback is-error"><GoogleIcon name="error" size={18} filled />{error}</div>}
          <footer><button type="button" onClick={onClose}>Hủy</button><button type="submit" disabled={saving || !displayName.trim() || !email.trim()}>{saving ? <span className="spinner" /> : <GoogleIcon name="save" size={18} />} {saving ? "Đang lưu..." : "Lưu thay đổi"}</button></footer>
        </form>
      </section>
    </div>
  );
}
