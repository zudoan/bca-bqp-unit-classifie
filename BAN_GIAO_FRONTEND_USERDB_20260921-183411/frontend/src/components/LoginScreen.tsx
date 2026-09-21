import { useState } from "react";
import type { FormEvent } from "react";
import { GoogleIcon } from "./Icons";
import { authenticateAccount, registerAccount } from "../services/authApi";
import type { PortalSession } from "../types/portal";

interface LoginScreenProps {
  onLogin: (session: PortalSession) => void;
}

type AuthMode = "login" | "register";

export function LoginScreen({ onLogin }: LoginScreenProps) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function changeMode(nextMode: AuthMode) {
    setMode(nextMode);
    setError("");
    setPassword("");
    setConfirmPassword("");
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (mode === "register" && password !== confirmPassword) {
      setError("Mật khẩu xác nhận không trùng khớp.");
      return;
    }

    setSubmitting(true);
    try {
      const session = mode === "login"
        ? await authenticateAccount(username, password, remember)
        : await registerAccount({ displayName, email, username, password }, remember);
      onLogin(session);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể xử lý yêu cầu tài khoản.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-context" aria-label="Giới thiệu hệ thống">
        <div className="login-context-inner">
          <div className="login-emblem"><GoogleIcon name="account_balance" size={34} filled /></div>
          <span className="login-system-code">HỆ THỐNG TRA CỨU TỔ CHỨC BCA · BQP</span>
          <h1>Cổng tra cứu và định danh tổ chức</h1>
          <p>Đối chiếu nguồn trả lương, phạm vi quản lý và lưu vết các phiên tra cứu trong một không gian nghiệp vụ thống nhất.</p>
        </div>
      </section>

      <section className="login-panel" aria-labelledby="auth-title">
        <div className={`login-card ${mode === "register" ? "is-register" : ""}`}>
          <div className="auth-mode-tabs" role="tablist" aria-label="Tài khoản">
            <button type="button" role="tab" aria-selected={mode === "login"} className={mode === "login" ? "is-active" : ""} onClick={() => changeMode("login")}>Đăng nhập</button>
            <button type="button" role="tab" aria-selected={mode === "register"} className={mode === "register" ? "is-active" : ""} onClick={() => changeMode("register")}>Đăng ký</button>
          </div>

          <header>
            <span className="section-code">{mode === "login" ? "TRUY CẬP HỆ THỐNG" : "ĐĂNG KÝ TÀI KHOẢN"}</span>
            <h2 id="auth-title">{mode === "login" ? "Đăng nhập hệ thống" : "Tạo tài khoản mới"}</h2>
            <p>{mode === "login" ? "Nhập thông tin tài khoản để tiếp tục tra cứu." : "Thiết lập thông tin cá nhân và tài khoản đăng nhập."}</p>
          </header>

          <form onSubmit={submit}>
            {mode === "register" && (
              <>
                <div className="login-field">
                  <label htmlFor="register-name">Họ và tên</label>
                  <div><GoogleIcon name="id_card" size={20} /><input id="register-name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Nhập họ và tên" autoComplete="name" autoFocus /></div>
                </div>
                <div className="login-field">
                  <label htmlFor="register-email">Email</label>
                  <div><GoogleIcon name="mail" size={20} /><input id="register-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Nhập địa chỉ email" autoComplete="email" /></div>
                </div>
              </>
            )}

            <div className="login-field">
              <label htmlFor="auth-username">Tên đăng nhập</label>
              <div><GoogleIcon name="person" size={20} /><input id="auth-username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Nhập tên đăng nhập" autoComplete="username" autoFocus={mode === "login"} /></div>
              {mode === "register" && <small>4–32 ký tự, dùng chữ thường, số, dấu chấm hoặc gạch dưới.</small>}
            </div>
            <div className="login-field">
              <label htmlFor="auth-password">Mật khẩu</label>
              <div><GoogleIcon name="lock" size={20} /><input id="auth-password" type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Nhập mật khẩu" autoComplete={mode === "login" ? "current-password" : "new-password"} /><button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}><GoogleIcon name={showPassword ? "visibility_off" : "visibility"} size={19} /></button></div>
              {mode === "register" && <small>Tối thiểu 8 ký tự, bao gồm chữ và số.</small>}
            </div>

            {mode === "register" && (
              <div className="login-field">
                <label htmlFor="register-confirm-password">Xác nhận mật khẩu</label>
                <div><GoogleIcon name="lock_reset" size={20} /><input id="register-confirm-password" type={showPassword ? "text" : "password"} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Nhập lại mật khẩu" autoComplete="new-password" /></div>
              </div>
            )}

            <label className="remember-login"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} /><span>Ghi nhớ đăng nhập trên thiết bị này</span></label>
            {error && <div className="login-error" role="alert"><GoogleIcon name="error" size={19} filled />{error}</div>}

            <button className="login-submit" type="submit" disabled={submitting || !username.trim() || !password || (mode === "register" && (!displayName.trim() || !email.trim() || !confirmPassword))}>
              {submitting ? <span className="spinner" /> : <GoogleIcon name={mode === "login" ? "login" : "person_add"} size={20} />}
              {submitting ? "Đang xử lý..." : mode === "login" ? "Đăng nhập" : "Tạo tài khoản"}
            </button>
          </form>

          <div className="auth-switch">
            <span>{mode === "login" ? "Chưa có tài khoản?" : "Đã có tài khoản?"}</span>
            <button type="button" onClick={() => changeMode(mode === "login" ? "register" : "login")}>{mode === "login" ? "Đăng ký ngay" : "Quay lại đăng nhập"}</button>
          </div>
        </div>
      </section>
    </main>
  );
}
