# FRONTEND REACTJS - SÂN VIỆT (HTTT14)

Frontend SPA tách rời (decoupled) giao tiếp với Django REST API qua JWT.

> **Tên sản phẩm:** SportBook - Đặt sân nhanh chóng (đồng bộ với bản Django gốc)

---

## 1. Công nghệ sử dụng

| Thành phần | Công nghệ | Phiên bản |
|---|---|---|
| Framework | React | 19.x |
| Build tool | Vite | 8.x |
| Routing | React Router DOM | 7.x |
| HTTP client | Axios | 1.x |
| Styling | Tailwind CSS | 3.x |
| Bản đồ | Leaflet + OpenStreetMap | 1.9.4 |
| Ngôn ngữ | JavaScript (JSX) | ES2022 |

---

## 2. Cấu trúc thư mục

```
frontend/
├── index.html              # Entry HTML + Leaflet CDN
├── vite.config.js          # Cấu hình Vite + proxy /api -> Django
├── tailwind.config.js      # Theme Tailwind (màu brand xanh lá)
├── postcss.config.js
├── package.json
└── src/
    ├── main.jsx            # Điểm khởi tạo React
    ├── App.jsx             # Routing + ProtectedRoute/OwnerRoute
    ├── index.css           # Tailwind directives + component classes
    │
    ├── lib/
    │   └── api.js          # Axios client + JWT interceptor + toàn bộ API service
    │
    ├── context/
    │   └── AuthContext.jsx # Quản lý trạng thái đăng nhập toàn cục
    │
    ├── components/
    │   ├── Header.jsx      # Navbar + menu user + badge thông báo
    │   └── ui.jsx          # Spinner, Modal, Toast, Pagination, Badge, Stars...
    │
    └── pages/
        ├── Home.jsx            # Trang chủ + Hero + tìm kiếm nhanh
        ├── FacilityList.jsx    # Danh sách cụm sân + bộ lọc (URL-driven)
        ├── FacilityDetail.jsx  # Chi tiết + MA TRẬN SLOT 30 PHÚT + thanh toán
        ├── Auth.jsx            # Login / Register (dùng chung)
        ├── MyBookings.jsx      # Lịch sử đơn của khách
        ├── OwnerDashboard.jsx  # Kênh chủ sân (duyệt/từ chối, doanh thu)
        ├── Notifications.jsx   # Trung tâm thông báo kiểu Gmail
        ├── Favorites.jsx       # Sân yêu thích
        ├── MapPage.jsx         # Bản đồ Leaflet (7 tile provider dự phòng)
        ├── MapPage.css         # Style marker/popup phong cách Alobo
        ├── mapHelpers.js       # TILE_PROVIDERS + probeProvider()
        └── NotFound.jsx        # Trang 404
```

---

## 3. Chạy ứng dụng

### Bước 1: Khởi động Django Backend (cổng 8000)

```powershell
cd d:\sanbong
python manage.py runserver 8000
```

### Bước 2: Khởi động React Frontend (cổng 5173)

```powershell
cd d:\sanbong\frontend
npm install          # chỉ cần chạy lần đầu
npm run dev
```

Mở trình duyệt: **http://localhost:5173**

### Bước 3: Build production

```powershell
cd d:\sanbong\frontend
npm run build        # xuất ra thư mục dist/
npm run preview      # xem bản build
```

> **Lưu ý proxy:** Trong chế độ dev, Vite tự proxy `/api` và `/media` sang
> `http://127.0.0.1:8000` nên **không gặp lỗi CORS** và không cần cấu hình
> `VITE_API_URL`. Nếu deploy riêng, đặt biến môi trường:
>
> ```env
> VITE_API_URL=https://api.your-domain.com/api
> ```

---

## 4. Tài khoản demo

| Vai trò | Tên đăng nhập | Mật khẩu | Quyền |
|---|---|---|---|
| Khách hàng | `khachhang1` | `customer123` | Đặt sân, yêu thích, xem thông báo |
| Chủ sân | `chusan` | `chusan123` | Duyệt/từ chối đơn, quản lý 6 cụm sân |
| Quản trị | `admin` | `admin123` | Toàn quyền |

> Nút "Tài khoản demo" trên trang đăng nhập điền sẵn credentials để test nhanh.

---

## 5. Cơ chế xác thực JWT

Được cài đặt trong `src/lib/api.js` và `src/context/AuthContext.jsx`:

```
┌──────────────┐                    ┌─────────────────────┐
│  React SPA   │  POST /auth/login/ │  Django REST API    │
│              │ ──────────────────> │  (SimpleJWT)        │
│              │ <─ access_token ──  │                     │
│              │    refresh_token    │                     │
└──────────────┘                    └─────────────────────┘
       │
       │ 1. Lưu token vào localStorage
       │    ttp_access_token / ttp_refresh_token / ttp_user
       │
       │ 2. Mỗi request -> Axios request interceptor
       │    gắn header: Authorization: Bearer <access_token>
       │
       │ 3. Response 401 -> refresh tự động (có queue chống race condition)
       │    POST /auth/token/refresh/ -> retry request cũ
       │
       │ 4. Refresh thất bại -> xóa token, dispatch 'auth:expired'
       │    -> AuthContext setUser(null) -> điều hướng về /login
```

**Refresh token tự động (trong `api.js`):**

- `isRefreshing` flag đảm bảo chỉ 1 request refresh chạy tại 1 thời điểm
- `pendingQueue` giữ các request đang chờ, sau khi refresh xong sẽ được
  gửi lại với token mới
- Đánh dấu `_retry = true` để tránh vòng lặp vô hạn

---

## 6. Các luồng nghiệp vụ đã hiện thực

### 6.1. Tìm kiếm & lọc cụm sân (`/facilities`)

- Bộ lọc được lưu **trong URL** (`?q=&sport=&min_price=&max_price=&page=`)
  → có thể chia sẻ link, hỗ trợ nút Back của trình duyệt
- Danh sách môn thể thao lấy động từ `GET /api/categories/`
- Phân trang server-side, hỗ trợ `page_size`

### 6.2. Ma trận đặt sân 30 phút (`/facilities/:id`)

Đây là phần cốt lõi của đồ án:

```
        05:00  05:30  06:00  06:30 ...
Sân 1  [ 75k ] [ 75k ] [ 75k ] [ 75k ]
Sân 2  [ 75k ] [ 75k ] [XXXXX] [ 75k ]
Sân 3  [ 75k ] [ 75k ] [ 75k ] [ 75k ]
```

- **Hàng** = khung giờ 30 phút (`start_time_str` → `end_time_str`)
- **Cột** = sân thi đấu, tự động gắn icon môn thể thao
- **Màu sắc:**
  - Viền xám + giá → trống, có thể đặt
  - Xanh đậm + ✓ → đang chọn
  - Xám đậm + ✕ → đã có người đặt
  - Xám nhạt + — → khung giờ đã qua
- Chọn slot tự động cập nhật giỏ hàng bên phải (tổng tiền realtime)
- Chuyển ngày bằng nút ◀ ▶ hoặc input `date`
- Backend tự quản lý **lock 10 phút** (chống tranh chấp)
- Endpoint `GET /api/slots/` **không phân trang** để trả về đủ ma trận

### 6.3. Thanh toán VietQR

- Tạo đơn: `POST /api/bookings/` → backend trả `vietqr_url` (ảnh QR đã điền sẵn
  số tiền + mã đơn)
- Modal hiển thị QR + mã đơn + tổng tiền
- Upload ảnh bill: `POST /api/bookings/<code>/upload-proof/` (multipart/form-data)
- Sau khi gửi bill → trạng thái đơn chuyển sang **chờ chủ sân duyệt**

### 6.4. Kênh chủ sân (`/owner`)

- Thống kê: tổng đơn, doanh thu, số đơn chờ duyệt, số cụm sân
- Tab: Chờ duyệt / Đã xác nhận / Từ chối / Tất cả
- Nút **Duyệt** (`POST /api/bookings/<code>/approve/`) và
  **Từ chối** (`POST /api/bookings/<code>/reject/` có lý do)
- Danh sách cụm sân của chủ + trạng thái (Hoạt động / Chờ duyệt)

### 6.5. Trung tâm thông báo (`/notifications`)

- Kiểu Gmail: đọc / chưa đọc, màu nền khác nhau
- Đánh dấu đã xem từng thông báo hoặc tất cả
- Badge số chưa đọc trên icon chuông (Header)

### 6.6. Bản đồ Leaflet (`/map`)

Đồng bộ hoàn toàn với bản Django gốc (`templates/facilities/facility_map.html`):

- **7 nhà cung cấp tile dự phòng**: Google Maps → Esri → OpenStreetMap → OSM DE/JP/FR → CARTO Voyager
- Tự động **dò (probe)** provider trước khi dùng bằng `<img>.onerror` (bắt chắc lỗi HTTP 403 mà `tileerror` của Leaflet bỏ sót)
- Nút **"Đổi nền bản đồ"** để chuyển thủ công khi IP bị chặn
- Marker gradient xanh lá, đổi sang cam khi được chọn
- Popup đầy đủ: ảnh bìa, rating, tích xanh KYC, giờ mở cửa, môn thể thao, giá từ, nút "Đặt lịch", link chỉ đường Google Maps
- Bấm item trong sidebar → `setView` zoom 17 + mở popup, đồng bộ highlight hai chiều
- Nút **"Vị trí tôi"** dùng Geolocation API
- Cảnh báo khi không tải được nền bản đồ

Dữ liệu lấy từ `GET /api/facilities/map/` (trả `results[]` + `center_lat/lng`).

---

## 7. Cấu trúc lớp API (`src/lib/api.js)

```javascript
api            // Axios instance (interceptors, timeout 20s)
├── authApi        register, login, logout, me
├── facilityApi    list, detail, map, categories, courts, pricingRules, addons
├── slotApi        list (ma trận slot)
├── bookingApi     create, list, detail, lookup, cancel, uploadProof
├── favoriteApi    list, toggle
├── notificationApi list, unreadCount, markRead
├── couponApi      validate
└── ownerApi       facilities, bookings, stats, registerFacility, approve, reject
```

Mọi lỗi được chuẩn hoá qua `getErrorMessage()` trả về thông báo tiếng Việt,
map tên field (`username`, `password`, `slot_ids`...) sang nhãn tiếng Việt.

---

## 8. Bảng màu & design system

| Token | Màu | Dùng cho |
|---|---|---|
| `brand-50` | `#f0fdf4` | Nền nhạt, hover |
| `brand-500` | `#22c55e` | Icon, phụ đạo |
| `brand-600` | `#16a34a` | Nút chính, trạng thái active |
| `brand-700` | `#15803d` | Chữ trên nền sáng, giá |
| `slate-50` | `#f8fafc` | Nền trang |
| `amber` | — | Chờ thanh toán / giữ chỗ |
| `red` | — | Từ chối / hủy |

Class component dùng lại (định nghĩa trong `index.css`):
`.btn-primary` `.btn-secondary` `.btn-ghost` `.card` `.card-hover` `.input`
`.label` `.badge` `.badge-green` `.badge-amber` `.badge-red` `.badge-blue` `.badge-gray`

---

## 9. Kết nối với Backend Django

| Điểm | Giá trị |
|---|---|
| Backend URL | `http://127.0.0.1:8000` |
| API prefix | `/api/` |
| Auth endpoints | `/api/auth/register/`, `/api/auth/login/`, `/api/auth/logout/`, `/api/auth/me/`, `/api/auth/token/refresh/` |
| Tài liệu API đầy đủ | [`API_DOCS.md`](../API_DOCS.md) |

CORS đã được cấu hình sẵn trong `config/settings.py`:

```python
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000', 'http://localhost:5173',
    'http://127.0.0.1:3000', 'http://127.0.0.1:5173',
]
```

---

## 10. Kiểm thử

```powershell
# Backend: 100 test (54 API test + 46 test nghiệp vụ)
cd d:\sanbong
python manage.py test

# Frontend: lint + build
cd d:\sanbong\frontend
npx oxlint src
npm run build
```

### Checklist kiểm thử thủ công

- [ ] Đăng ký tài khoản mới → tự đăng nhập, vào được trang chủ
- [ ] Đăng nhập → header hiện avatar + menu "Đơn của tôi"
- [ ] Lọc cụm sân theo môn → danh sách + chip filter cập nhật
- [ ] Vào chi tiết cụm sân → ma trận 7 cột × 37 dòng (slot 30 phút)
- [ ] Chọn 2 slot liên tiếp → giỏ hàng hiện tổng tiền
- [ ] Bấm "Đặt sân" → modal hiện QR VietQR + mã đơn
- [ ] Upload bill → thông báo "đã gửi ảnh thanh toán"
- [ ] Đăng nhập `chusan` → kênh chủ sân thấy đơn chờ duyệt
- [ ] Duyệt đơn → trạng thái chuyển "Đã xác nhận", khách nhận thông báo
- [ ] Trang thông báo → đánh dấu đã xem hoạt động
- [ ] Refresh token hết hạn → tự refresh, không mất phiên

---

## 11. Triển khai production

```powershell
cd d:\sanbong\frontend
npm run build
# Copy thư mục dist/ vào web server (nginx / Apache / IIS)
```

Cấu hình web server để:

1. Phục vụ file tĩnh từ `dist/`
2. **Fallback** mọi route về `index.html` (SPA routing):
   ```nginx
   location / {
       try_files $uri $uri/ /index.html;
   }
   ```
3. Proxy `/api` → Django backend (hoặc đặt `VITE_API_URL` khi build)

---

## 12. Hướng phát triển tiếp

- [ ] Tích hợp React Query / TanStack Query để cache & refetch thông minh
- [ ] WebSocket (Django Channels) để cập nhật slot realtime khi có người đặt
- [ ] Đặt sân định kỳ (RecurringBooking) — backend đã có model, frontend chưa làm UI
- [ ] Đánh giá sân (RatingStars đã sẵn sàng, chưa có form submit)
- [ ] Chọn dịch vụ phụ (vợt, nước) trong giỏ hàng — API đã hỗ trợ
- [ ] PWA / offline caching
- [ ] Đa ngôn ngữ (i18n)
