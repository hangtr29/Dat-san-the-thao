# RESTful API & Xác thực JWT — HTTT14

> Base URL: `http://127.0.0.1:8000/api/`
> Xác thực: **JWT Bearer Token** (`djangorestframework-simplejwt`)
> CORS: đã bật cho ReactJS (`localhost:3000`, `localhost:5173`) và Flutter

---

## 1. Cách dùng token

```bash
# 1. Đăng nhập -> nhận access + refresh token
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"khachhang1","password":"customer123"}'

# 2. Gọi endpoint cần xác thực
curl http://127.0.0.1:8000/api/bookings/ \
  -H "Authorization: Bearer <ACCESS_TOKEN>"

# 3. Làm mới access token khi hết hạn (1 giờ)
curl -X POST http://127.0.0.1:8000/api/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh":"<REFRESH_TOKEN>"}'
```

| Token | Thời hạn | Mục đích |
|---|---|---|
| `access` | 1 giờ | Gửi kèm mọi request (`Authorization: Bearer ...`) |
| `refresh` | 7 ngày | Lấy access token mới, có **rotate** (token cũ tự vô hiệu) |

---

## 2. Danh mục endpoint

### 2.1 Xác thực — `/api/auth/`

| Method | Endpoint | Auth | Mô tả |
|---|---|---|---|
| POST | `/api/auth/register/` | ✗ | Đăng ký tài khoản → trả `access` + `refresh` |
| POST | `/api/auth/login/` | ✗ | Đăng nhập (username **hoặc** email) → trả token |
| POST | `/api/auth/logout/` | ✓ | Đăng xuất (blacklist refresh token) |
| GET | `/api/auth/me/` | ✓ | Thông tin user hiện tại |
| POST | `/api/auth/token/refresh/` | ✗ | Làm mới access token |
| POST | `/api/auth/token/` | ✗ | TokenObtainPairView (tương đương `/login/`) |

**Body đăng ký:**
```json
{
  "username": "khachmoi",
  "email": "khachmoi@gmail.com",
  "phone": "0912345678",
  "password": "password123",
  "password_confirm": "password123",
  "role": "CUSTOMER"
}
```
> Không cho tự đăng ký `role = ADMIN` (trả 400).

### 2.2 Dữ liệu công khai (không cần token)

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/categories/` | Danh mục môn thể thao + số lượng sân |
| GET | `/api/facilities/` | Danh sách cụm sân (tìm kiếm, lọc, phân trang) |
| GET | `/api/facilities/<uuid>/` | Chi tiết: sân con, bảng giá, dịch vụ, ảnh, coupon, đánh giá |
| GET | `/api/facilities/map/` | Dữ liệu marker bản đồ (Leaflet) |
| GET | `/api/courts/` | Sân thi đấu (`?facility=<uuid>`) |
| GET | `/api/pricing-rules/` | Bảng giá theo cụm sân (`?facility=<uuid>`) |
| GET | `/api/addons/` | Dịch vụ bổ sung (`?facility=<uuid>`) |
| GET | `/api/coupons/` | Mã giảm giá đang hiệu lực |
| GET | `/api/coupons/validate_code/` | Kiểm tra mã: `?code=XXX&amount=200000&facility=<uuid>` |
| GET | `/api/slots/` | Ma trận khung giờ: `?facility=<uuid>&date=YYYY-MM-DD&available_only=true` |

**Query filters của `/api/facilities/`:**

| Param | Ví dụ | Ý nghĩa |
|---|---|---|
| `q` | `?q=cầu lông` | Tìm theo tên / địa chỉ / mô tả |
| `sport` | `?sport=Pickleball` | Lọc theo môn thể thao |
| `lat` / `lng` | `?lat=10.77&lng=106.70` | Lọc theo bán kính ~0.5° quanh GPS |
| `min_price` / `max_price` | `?min_price=100000` | Lọc theo giá/giờ |
| `verified` | `?verified=true` | Chỉ cụm sân đã tích xanh |

### 2.3 Đặt sân (cần token) — `/api/bookings/`

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/bookings/` | Danh sách đơn của tôi (chủ sân thấy đơn cụm sân mình) |
| POST | `/api/bookings/` | **Tạo đơn** → khóa slot 10 phút, trả `booking_code` + QR VietQR |
| GET | `/api/bookings/<code>/` | Chi tiết đơn (dùng **mã đơn** làm định danh) |
| POST | `/api/bookings/<code>/upload-proof/` | Tải ảnh bill (`multipart/form-data`, field `payment_proof`) |
| POST | `/api/bookings/<code>/cancel/` | Khách hủy đơn → giải phóng slot |
| POST | `/api/bookings/<code>/approve/` | Chủ sân duyệt → `CONFIRMED` |
| POST | `/api/bookings/<code>/reject/` | Chủ sân từ chối (body: `{"reason": "..."}`) → `NEEDS_REUPLOAD` |
| GET | `/api/bookings/lookup/<code>/` | **Tra cứu đơn bằng mã — KHÔNG cần đăng nhập** |

**Body tạo đơn:**
```json
{
  "slot_ids": ["uuid-1", "uuid-2"],
  "customer_name": "Nguyễn Văn A",
  "customer_phone": "0912345678",
  "customer_note": "Mình thuê thêm 2 vợt"
}
```

**Response tạo đơn (rút gọn):**
```json
{
  "ok": true,
  "message": "Khóa slot thành công!",
  "booking": {
    "booking_code": "BKQECE6DLM",
    "status": "PENDING_BILL",
    "total_amount": 150000,
    "court_amount": 150000,
    "addon_amount": 0,
    "discount_amount": 0,
    "facility_name": "CLB Thể Thao Sài Gòn Star",
    "court_name": "Sân 1",
    "slots": [
      {"id": "...", "start_time_str": "06:00", "end_time_str": "06:30", "price": 75000}
    ],
    "vietqr_url": "https://img.vietqr.io/image/mb-0123456789-compact.png?amount=150000&addInfo=BKQECE6DLM"
  }
}
```

### 2.4 Yêu thích, thông báo

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/favorites/` | Danh sách sân yêu thích |
| POST | `/api/favorites/` | Thêm (`{"facility_id": "<uuid>"}`) |
| DELETE | `/api/favorites/<uuid>/` | Xóa |
| POST | `/api/favorites/toggle/` | Bật/tắt (`{"facility_id": "<uuid>"}`) |
| GET | `/api/notifications/` | Trung tâm thông báo |
| GET | `/api/notifications/unread_count/` | Số thông báo chưa đọc |
| POST | `/api/notifications/mark-read/` | Đánh dấu đã xem (một hoặc tất cả) |
| POST | `/api/notifications/mark-unread/` | Đánh dấu chưa đọc |

### 2.5 Chủ sân — `/api/owner/`

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/owner/facilities/` | Cụm sân của tôi (`?status=PENDING_REVIEW`) |
| POST | `/api/owner/facilities/` | **Đăng ký cụm sân mới** → `PENDING_REVIEW`, tự sinh sân con + bảng giá + slot 14 ngày |
| GET | `/api/owner/facilities/<uuid>/` | Chi tiết cụm sân |
| PUT/PATCH | `/api/owner/facilities/<uuid>/` | Cập nhật thông tin |
| GET | `/api/owner/bookings/` | Đơn đặt sân tới cụm sân của tôi (`?status=WAITING_APPROVAL`) |
| GET | `/api/owner/bookings/stats/` | Thống kê: tổng đơn, doanh thu, phân bố trạng thái |

**Body đăng ký cụm sân:**
```json
{
  "name": "CLB Cầu Lông XYZ",
  "address": "123 Nguyễn Huệ, Q1, TP.HCM",
  "phone_contact": "0912345678",
  "bank_name": "MBBank",
  "bank_account_no": "0123456789",
  "bank_account_name": "NGUYEN VAN A",
  "latitude": 10.7769,
  "longitude": 106.7009,
  "description": "Sân thảm PVC chuyên dụng...",
  "category_id": 1,
  "court_count": 4,
  "off_peak_price": "100000",
  "peak_price": "150000",
  "open_time": "06:00",
  "close_time": "22:00"
}
```

---

## 3. Ma trận nguyên tắc REST

| Nguyên tắc | Thực hiện |
|---|---|
| **Resource-based URL** | `/api/facilities/`, `/api/bookings/` (danh từ số nhiều) |
| **HTTP verbs** | GET đọc, POST tạo, PUT/PATCH sửa, DELETE xóa |
| **Stateless** | Mọi request mang `Authorization: Bearer <token>`; server không lưu session |
| **Mã trạng thái đúng** | 200 OK, 201 Created, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found |
| **Phân trang** | `?page=1&size=20` → `{count, next, previous, results}` |
| **Định dạng thống nhất** | JSON, ngày `YYYY-MM-DD`, giờ `HH:MM`, tiền tệ số nguyên (VNĐ) |

---

## 4. Máy trạng thái đơn đặt (State Machine)

```
PENDING_BILL ──(khách nộp bill)──► WAITING_APPROVAL
      │                                    │
      │(quá hạn 10' / khách hủy)          ├──(chủ sân duyệt)──► CONFIRMED
      ▼                                    │
  CANCELLED ◄──(chủ sân từ chối)───────────┘
                                            │
                                NEEDS_REUPLOAD (khách tải lại bill)
```

| Trạng thái | Ai chuyển | API |
|---|---|---|
| `PENDING_BILL` | Hệ thống (tạo đơn) | `POST /api/bookings/` |
| `WAITING_APPROVAL` | Khách (nộp bill) | `POST /api/bookings/<code>/upload-proof/` |
| `CONFIRMED` | Chủ sân (duyệt) | `POST /api/bookings/<code>/approve/` |
| `NEEDS_REUPLOAD` | Chủ sân (từ chối) | `POST /api/bookings/<code>/reject/` |
| `CANCELLED` | Khách / hệ thống | `POST /api/bookings/<code>/cancel/` |

---

## 5. An toàn thông tin

- **Không lộ số tài khoản ngân hàng** qua API công khai (`bank_account_no`, `bank_account_name` không có trong `FacilityListSerializer`).
- **Không lộ mật khẩu** — `UserSerializer` chỉ có field read-only an toàn.
- **Tra cứu đơn công khai** chỉ trả về: mã đơn, trạng thái, tổng tiền, tên cụm sân, hotline.
- **Phân quyền theo vai trò**: `CUSTOMER` / `OWNER` / `ADMIN`; chỉ chủ sân sở hữu cụm sân mới duyệt/từ chối được đơn.
- **Chống đặt trùng**: `BookingEngineService` dùng `transaction.atomic()` + `select_for_update()`, giữ chỗ 10 phút.
- **Cụm sân chờ duyệt** bị ẩn khỏi API công khai và bị chặn khi đặt lịch.

---

## 6. Kiểm thử

```bash
# Toàn bộ test (97 test)
python manage.py test

# Riêng test API + JWT (54 test)
python manage.py test api -v 2
```

| Nhóm test | Số lượng | Nội dung |
|---|---|---|
| `ApiAuthenticationTests` | 11 | Đăng ký, đăng nhập, refresh, bảo vệ token |
| `ApiPublicDataTests` | 9 | Endpoint công khai, lọc & tìm kiếm |
| `ApiBookingTests` | 14 | Đặt sân, chống trùng, duyệt/từ chối/hủy |
| `ApiEngagementTests` | 9 | Yêu thích, thông báo, coupon |
| `ApiOwnerTests` | 7 | Phân quyền & đăng ký cụm sân của chủ sân |
| `ApiSecurityTests` | 4 | Không rò rỉ dữ liệu nhạy cảm |
