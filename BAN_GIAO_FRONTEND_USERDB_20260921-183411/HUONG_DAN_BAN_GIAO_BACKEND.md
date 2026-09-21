# Hướng dẫn nhận bàn giao frontend và quản lý người dùng

Gói bàn giao này là **gói chép đè theo đường dẫn**, không phải toàn bộ repository.
Người nhận cần giải nén vào thư mục gốc của project BCA/BQP hiện tại, sau đó
kiểm tra thay đổi trước khi commit.

## 1. Phạm vi bàn giao

- React frontend thay thế giao diện Gradio cũ.
- Đăng ký, đăng nhập, đăng xuất và khôi phục phiên bằng cookie `HttpOnly`.
- SQLite/SQLAlchemy lưu tài khoản và phiên đăng nhập.
- Phân quyền `admin`/`user`, khóa/mở khóa và chỉnh sửa tài khoản.
- Lịch sử tra cứu theo tài khoản trên trình duyệt.
- Ba bộ test dành cho database, xác thực và API quản trị.

Thuật toán tra cứu tổ chức, dữ liệu BCA/BQP và xử lý OCR hiện có không bị thay
thế. `api/main.py` chỉ được ghép thêm vòng đời khởi tạo database, router xác thực,
router quản trị và cấu hình CORS cần cho frontend.

## 2. Cách ghép vào repository

1. Sao lưu hoặc tạo nhánh Git mới trong repository đích.
2. Giải nén gói bàn giao.
3. Chép các thư mục và file trong gói vào đúng thư mục gốc của project.
4. Khi có xung đột ở `api/main.py`, `docker-compose.yml`, `README.md`,
   `.gitignore` hoặc `.dockerignore`, cần merge nội dung thay vì xóa thay đổi mới
   của backend.
5. Không chép database hoặc `.env` từ máy khác.

Các điểm bắt buộc phải giữ khi merge `api/main.py`:

- Gọi `initialize_database()` và `initialize_admin_account()` trong lifespan.
- `app.include_router(auth_router)` và `app.include_router(admin_router)`.
- CORS bật `allow_credentials=True` và cho phép `GET`, `POST`, `PATCH`,
  `DELETE`, `OPTIONS`.
- Giữ nguyên toàn bộ endpoint tra cứu tổ chức và xử lý file hiện có.

## 3. Cấu hình local

Từ thư mục gốc project:

```powershell
Copy-Item .env.example .env
```

Điền tài khoản quản trị ban đầu trong `.env`:

```text
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=<mật khẩu mạnh riêng, tối thiểu 8 ký tự có chữ và số>
ADMIN_DISPLAY_NAME=Quản trị viên hệ thống
AUTH_COOKIE_SECURE=false
```

Không commit `.env`. Nếu username và email trùng chính xác một tài khoản đã có,
backend nâng tài khoản đó thành admin và giữ nguyên mật khẩu đang lưu.

## 4. Chạy không cần Docker

Backend:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-backend.txt
python -m uvicorn api.main:app --host 127.0.0.1 --port 7860 --reload --env-file .env
```

Frontend, mở terminal khác:

```powershell
cd frontend
npm install
npm run dev
```

Mở `http://localhost:5173`. Tài liệu API ở
`http://localhost:7860/docs`, health check ở `http://localhost:7860/health`.

## 5. Database người dùng

Mặc định backend tự tạo `storage/users.db` ở lần chạy đầu:

- `users`: hồ sơ, quyền, trạng thái và password hash.
- `user_sessions`: hash token phiên, hạn dùng và thời điểm thu hồi.

Mật khẩu không lưu dạng rõ. Token cookie cũng không lưu trực tiếp. Quản lý tài
khoản nên thực hiện qua trang **Quản lý người dùng** hoặc API `/api/v1/admin/*`,
không sửa trực tiếp SQLite. Xem thêm `BACKEND_USER_DATABASE_GUIDE.md`.

Không đưa lên GitHub:

- `.env`
- `storage/*.db`
- `.venv/`
- `frontend/node_modules/`
- `frontend/dist/`
- `*.tsbuildinfo`, `__pycache__/`, `*.pyc`

Database và tài khoản demo trên máy người bàn giao **không có trong gói ZIP**.
Người nhận tự tạo admin qua `.env` cho môi trường của mình.

## 6. Kiểm tra trước khi commit

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm.cmd run build
```

Kết quả xác nhận trước khi đóng gói: 36 test Python thành công và frontend build
thành công.

Sau khi kiểm tra, dùng `git status` và đọc từng diff trước khi commit. Không chạy
`git add .` cho đến khi chắc chắn không có `.env`, database, API key, file tải lên
hoặc dữ liệu cá nhân.

## 7. File tham khảo thêm

- `BACKEND_USER_DATABASE_GUIDE.md`: chi tiết schema, endpoint và cách vận hành.
- `GITHUB_HANDOFF.md`: danh sách thành phần và checklist đưa lên GitHub.
- `README.md`: kiến trúc và cách chạy toàn bộ project.
