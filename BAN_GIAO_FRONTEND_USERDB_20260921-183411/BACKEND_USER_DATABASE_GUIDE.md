# Hướng dẫn kiểm tra backend tài khoản người dùng

Tài liệu này dành cho thành viên phụ trách backend kiểm tra phần database và
xác thực người dùng trước khi ghép nhánh. Logic tra cứu tổ chức hiện có không bị
thay đổi.

## 1. Thành phần đã thêm

- SQLite/SQLAlchemy database, mặc định tại `storage/users.db`.
- Bảng `users` lưu hồ sơ, quyền, trạng thái và password hash.
- Bảng `user_sessions` lưu hash của token phiên, thời hạn và thời điểm thu hồi.
- Cookie đăng nhập `bca_bqp_session` có `HttpOnly` và `SameSite=Lax`.
- API đăng ký, đăng nhập, kiểm tra phiên và đăng xuất.
- API quản trị danh sách, tìm kiếm, phân quyền và khóa/mở khóa người dùng.
- Docker volume `bca-bqp-user-data` giữ database sau khi rebuild container.

Mật khẩu dùng PBKDF2-HMAC-SHA256 với salt ngẫu nhiên và 600.000 vòng. Database
không lưu mật khẩu gốc. Token cookie cũng không được lưu trực tiếp; backend chỉ
lưu SHA-256 hash của token.

## 2. Chạy trực tiếp bằng Python

Yêu cầu Python 3.11 trở lên. Từ thư mục gốc của project:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-backend.txt
Copy-Item .env.example .env
python -m uvicorn api.main:app --host 127.0.0.1 --port 7860 --reload --env-file .env
```

Backend tự tạo `storage/users.db` ở lần chạy đầu. Không commit file này lên
GitHub.

Để backend tạo tài khoản quản trị đầu tiên, cấu hình trong `.env` trước khi
khởi động:

```text
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ThayMatKhauManh123
ADMIN_DISPLAY_NAME=Quản trị viên
```

Không commit `.env`. Khi tài khoản đã tồn tại, cấu hình này bảo đảm tài khoản
được kích hoạt và có role `admin`, nhưng không tự ghi đè mật khẩu hiện có.

Chạy test trong một terminal khác:

```powershell
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
```

## 3. Chạy bằng Docker

```powershell
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

`docker compose down` không xóa database. Không dùng `docker compose down -v`
nếu cần giữ tài khoản, vì tham số `-v` xóa volume database.

## 4. Xem và quản lý tài khoản

### Qua giao diện web (khuyến nghị)

1. Đăng nhập bằng tài khoản có `role=admin`.
2. Chọn **Quản lý người dùng** ở thanh bên hoặc menu tài khoản.
3. Có thể tìm theo họ tên/username/email, lọc vai trò và trạng thái, sửa hồ sơ,
   đổi quyền, khóa hoặc mở khóa tài khoản.

Khóa tài khoản là **khóa mềm** (`is_active=false`), không xóa hồ sơ. Mọi phiên
đăng nhập còn hiệu lực của tài khoản đó sẽ bị thu hồi. Hệ thống không cho admin
tự khóa chính mình và không cho khóa/hạ quyền admin hoạt động cuối cùng.

Nếu tài khoản admin ban đầu chưa có, đặt bốn biến `ADMIN_*` trong `.env` rồi
khởi động lại backend. Nếu username và email trùng chính xác một tài khoản đã
có, backend nâng tài khoản đó thành admin và **giữ nguyên mật khẩu hiện tại**.

### Qua tài liệu API

Khi backend đang chạy, mở:

```text
http://localhost:7860/docs
```

Nhóm `Authentication` chứa API đăng ký/đăng nhập. Nhóm quản trị chứa API danh
sách, cập nhật và khóa tài khoản. Các API `/api/v1/admin/*` chỉ chấp nhận cookie
phiên của admin.

### Xem file SQLite

File local nằm tại `storage/users.db`. Có thể mở bằng DB Browser for SQLite hoặc
extension SQLite Viewer trong VS Code. Chỉ dùng công cụ này để xem/kiểm tra;
quản lý tài khoản nên đi qua giao diện hoặc API để các quy tắc bảo vệ và thu hồi
phiên luôn được áp dụng.

Hai bảng hiện có:

| Bảng | Nội dung |
| --- | --- |
| `users` | Hồ sơ, username/email, password hash, vai trò, trạng thái và thời gian đăng nhập |
| `user_sessions` | Hash token phiên, hạn dùng và thời điểm thu hồi; liên kết với `users.user_id` |

Không sửa trực tiếp `password_hash`, `token_hash` và không mở/chỉnh file SQLite
khi đang sao chép hoặc thay thế database. Nên dừng backend và sao lưu file trước
các thao tác bảo trì thủ công.

## 5. Kiểm tra API bằng PowerShell

Tạo một WebSession để PowerShell giữ cookie giống trình duyệt:

```powershell
$webSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession

$registerBody = @{
  display_name = "Nguyễn Văn A"
  email        = "nguyenvana@example.com"
  username     = "nguyenvana"
  password     = "Matkhau123"
  remember     = $true
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:7860/api/v1/auth/register" `
  -ContentType "application/json; charset=utf-8" `
  -Body ([Text.Encoding]::UTF8.GetBytes($registerBody)) `
  -WebSession $webSession
```

Kiểm tra phiên hiện tại:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:7860/api/v1/auth/me" `
  -WebSession $webSession
```

Đăng xuất:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:7860/api/v1/auth/logout" `
  -WebSession $webSession
```

Đăng nhập lại:

```powershell
$loginBody = @{
  username = "nguyenvana"
  password = "Matkhau123"
  remember = $true
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:7860/api/v1/auth/login" `
  -ContentType "application/json; charset=utf-8" `
  -Body ([Text.Encoding]::UTF8.GetBytes($loginBody)) `
  -WebSession $webSession
```

## 6. Endpoint và mã phản hồi

| Method | Endpoint | Thành công | Lỗi thường gặp |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/register` | `201` | `409` trùng username/email, `422` dữ liệu sai |
| `POST` | `/api/v1/auth/login` | `200` | `401` sai thông tin, `403` tài khoản khóa |
| `GET` | `/api/v1/auth/me` | `200` | `401` thiếu/hết hạn phiên, `403` tài khoản khóa |
| `POST` | `/api/v1/auth/logout` | `204` | Luôn an toàn khi gọi lại |
| `GET` | `/api/v1/admin/users` | `200` | `403` không có quyền admin |
| `PATCH` | `/api/v1/admin/users/{id}` | `200` | `404`, `409` vi phạm bảo vệ admin |
| `DELETE` | `/api/v1/admin/users/{id}` | `204` | Khóa mềm tài khoản và thu hồi phiên |

## 7. Kiểm tra trực tiếp database

```powershell
python -c "import sqlite3; db=sqlite3.connect('storage/users.db'); print(db.execute('SELECT id, username, email, role, is_active, created_at, last_login_at FROM users').fetchall())"
```

Không in cột `password_hash` hoặc `token_hash` vào log/chụp màn hình gửi công
khai.

Sao lưu local (nên dừng backend trước khi sao chép):

```powershell
Copy-Item storage/users.db "storage/users-backup-$(Get-Date -Format yyyyMMdd-HHmmss).db"
```

Các file `storage/*.db` được loại khỏi Git và không được đưa lên repository.
Trong Docker, database nằm trong volume `bca-bqp-user-data`, không nằm trực tiếp
trong source code của container.

## 8. Cấu hình triển khai

- Local HTTP: giữ `AUTH_COOKIE_SECURE=false`.
- Production HTTPS: đặt `AUTH_COOKIE_SECURE=true`.
- Có thể đổi database bằng `USER_DATABASE_URL`; SQLite là mặc định cho đồ án.
- CORS phải liệt kê chính xác domain frontend và bật credentials. Không dùng
  wildcard `*` cùng cookie đăng nhập.
- Tài khoản đăng ký công khai luôn có role `user`. API cấp quyền `admin` sẽ được
  triển khai ở bước quản trị người dùng, không nhận role từ request đăng ký.
