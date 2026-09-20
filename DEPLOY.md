# 🚀 BCA-BQP Organization Registry - Docker Deployment

## 📋 Kiến trúc hệ thống

```
┌─────────────────────────────────────────┐
│  User Browser (http://localhost:3000)  │
└──────────────┬──────────────────────────┘
               │
       ┌───────▼────────┐
       │  Frontend      │  Port 3000
       │  React + Nginx │  (Container: bca-bqp-frontend)
       └───────┬────────┘
               │ Proxy /api/* → backend:7860
               │
       ┌───────▼────────┐
       │  Backend       │  Port 7860
       │  FastAPI       │  (Container: bca-bqp-backend)
       └────────────────┘
```

## 🔧 Yêu cầu

- Docker Desktop (Windows/Mac) hoặc Docker Engine (Linux)
- Docker Compose (thường đi kèm Docker Desktop)
- Port 3000 và 7860 chưa bị sử dụng

## 🚀 Chạy ứng dụng

### Windows:
```bash
start.bat
```

### Linux/Mac:
```bash
chmod +x start.sh
./start.sh
```

### Hoặc dùng docker-compose trực tiếp:
```bash
docker-compose up -d --build
```

## 🌐 Truy cập

- **Frontend (Giao diện chính):** http://localhost:3000
- **Backend API Docs:** http://localhost:7860/docs
- **Backend Health Check:** http://localhost:7860/health

## 📊 Quản lý

### Xem logs
```bash
# Tất cả services
docker-compose logs -f

# Chỉ frontend
docker-compose logs -f frontend

# Chỉ backend
docker-compose logs -f backend
```

### Dừng services
```bash
docker-compose down
```

### Khởi động lại
```bash
docker-compose restart
```

### Xóa và build lại từ đầu
```bash
docker-compose down
docker-compose up -d --build --force-recreate
```

## 🔍 Kiểm tra trạng thái

```bash
docker-compose ps
```

## 🐛 Troubleshooting

### Port đã được sử dụng
Sửa file `docker-compose.yml`:
```yaml
frontend:
  ports:
    - "8080:80"  # Đổi 3000 → 8080

backend:
  ports:
    - "8000:7860"  # Đổi 7860 → 8000
```

### Frontend không kết nối được backend
1. Kiểm tra backend đang chạy:
```bash
curl http://localhost:7860/health
```

2. Xem logs:
```bash
docker-compose logs backend
```

### Rebuild sau khi sửa code
```bash
# Rebuild service cụ thể
docker-compose up -d --build frontend
docker-compose up -d --build backend

# Hoặc rebuild tất cả
docker-compose up -d --build
```

## 📦 Cấu trúc Docker

- **Frontend:** Multi-stage build (Node build → Nginx serve)
- **Backend:** Python 3.11 slim + FastAPI + Uvicorn
- **Network:** Docker network riêng `bca-bqp-network`

## 🎯 Production Deployment

Để deploy lên production server:

1. Sửa nginx.conf thay `backend:7860` thành domain thực
2. Thêm SSL certificate
3. Sử dụng environment variables cho config
4. Setup CI/CD pipeline

## 📝 Notes

- Frontend build static files → serve bằng Nginx
- Backend chạy Uvicorn ASGI server
- Nginx proxy /api/* requests sang backend
- Hot reload không có trong production build
