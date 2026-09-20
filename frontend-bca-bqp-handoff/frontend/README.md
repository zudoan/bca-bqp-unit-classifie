# Frontend tra cứu tổ chức BCA / BQP

Frontend độc lập được xây dựng bằng React, TypeScript và Vite. Thư mục này không chứa hoặc thay đổi logic matching của backend Python.

## Chạy ở chế độ trình diễn

Yêu cầu Node.js 20.19 trở lên.

```bash
cp .env.example .env
npm install
npm run dev
```

Mặc định `VITE_USE_MOCK_API=true`, do đó có thể xem và kiểm thử toàn bộ trạng thái giao diện mà chưa cần backend. Các truy vấn mẫu gồm:

- `Công an tỉnh Thái Bình`: kết quả BCA.
- `Bộ Chỉ huy Quân sự tỉnh Quảng Ninh`: kết quả BQP.
- `BCHQS huyện Sóc Sơn`: kết quả alias.
- `Công an huyện Châu Thành`: kết quả mơ hồ cần chọn thêm địa phương.
- Một tên bất kỳ không có trong mock: trạng thái UNKNOWN.

## Kết nối backend

Đổi cấu hình trong `.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK_API=false
```

Frontend đang chờ các endpoint:

- `POST /api/search`: nhận JSON với các trường tùy chọn `organization_id`, `organization_name`, `province_name`, `organization_type`.
- `GET /api/statistics`: trả về `{ "total": 14303, "bca": 9689, "bqp": 4614, "provinces": 63 }`.

Kiểu dữ liệu request/response được định nghĩa trong `src/types/search.ts`. Toàn bộ kết nối HTTP tập trung tại `src/services/searchApi.ts`, giúp thay đổi hợp đồng API mà không ảnh hưởng component giao diện.
