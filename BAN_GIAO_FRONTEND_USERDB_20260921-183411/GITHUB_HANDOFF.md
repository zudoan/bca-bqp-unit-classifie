# Bàn giao phần frontend và quản lý người dùng

Tài liệu này tổng hợp phần đã triển khai để kiểm tra trước khi đưa toàn bộ
frontend và backend lên GitHub.

## Chức năng hoàn thành

- React frontend thay thế giao diện Gradio cũ.
- Giao diện đăng ký, đăng nhập và khôi phục phiên qua backend.
- Lịch sử tra cứu theo tài khoản, lọc, xem chi tiết và xuất CSV.
- SQLite/SQLAlchemy database cho tài khoản và phiên đăng nhập.
- Password hash PBKDF2, cookie `HttpOnly`, đăng xuất và thu hồi phiên.
- Phân quyền `admin`/`user`, khóa/mở khóa tài khoản và bảo vệ admin cuối cùng.
- Trang quản lý người dùng dành riêng cho quản trị viên.
- Docker volume giữ database sau khi rebuild.

## File frontend thuộc phần triển khai

- `frontend/index.html`
- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- `frontend/src/types/portal.ts`
- `frontend/src/components/Icons.tsx`
- `frontend/src/components/LoginScreen.tsx`
- `frontend/src/components/HistoryPanel.tsx`
- `frontend/src/components/AdminUsersPanel.tsx`
- `frontend/src/services/portalStore.ts`
- `frontend/src/services/authApi.ts`
- `frontend/src/services/adminApi.ts`

## File backend và cấu hình thuộc phần triển khai

- `api/main.py`
- `api/database.py`
- `api/models.py`
- `api/security.py`
- `api/auth.py`
- `api/admin.py`
- `tests/test_user_database.py`
- `tests/test_auth_api.py`
- `tests/test_admin_api.py`
- `requirements-backend.txt`
- `Dockerfile.backend`
- `docker-compose.yml`
- `.env.example`
- `.gitignore`
- `.dockerignore`
- `README.md`
- `BACKEND_USER_DATABASE_GUIDE.md`
- `HUONG_DAN_BAN_GIAO_BACKEND.md`
- `GITHUB_HANDOFF.md`

## Không đưa lên GitHub

- `.env`
- `.venv/`
- `frontend/node_modules/`
- `frontend/dist/`
- `storage/*.db`
- `__pycache__/`, `.pytest_cache/`, `*.pyc`

Các mục trên đã được loại trừ bằng `.gitignore` hoặc `.dockerignore`. Trước khi
commit vẫn cần kiểm tra `git status` để bảo đảm không có secret hoặc database.

## Kiểm tra trước khi commit

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm.cmd run build
```

Kết quả mong đợi: toàn bộ test Python thành công và Vite build không có lỗi.

## Cấu hình tối thiểu khi chạy

Sao chép `.env.example` thành `.env` và đặt thông tin admin thật. Không sử dụng
mật khẩu ví dụ trong production hoặc commit mật khẩu lên GitHub.

```text
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=<mật khẩu mạnh riêng>
ADMIN_DISPLAY_NAME=Quản trị viên
AUTH_COOKIE_SECURE=false
```

Khi chạy HTTPS, đặt `AUTH_COOKIE_SECURE=true`. Nếu frontend chạy ở domain khác,
đặt `CORS_ORIGINS` đúng domain frontend, không dùng wildcard `*`.

## Gợi ý commit

```powershell
git add .
git status
git commit -m "feat: add React portal and user account management"
git push
```

Chỉ chạy `git add .` sau khi đã đọc danh sách trong `git status` và chắc chắn
không có `.env`, database, API key, file upload hoặc dữ liệu nhạy cảm.
