# HỆ THỐNG TÌM KIẾM & ĐẶT SÂN THỂ THAO TRỰC TUYẾN (OOP DJANGO MONOLITH)

> **Môn học:** Phát triển ứng dụng Hướng Đối Tượng (HTTT14)  
> **Tech Stack:** Python 3.11+ / Django 5.x / Tailwind CSS  
> **Mô hình kiến trúc:** Django Monolith (HTML/MVT) kết hợp Service Layer & State Machine  
> **Cơ chế thanh toán:** Chuyển khoản QR (VietQR cá nhân của Chủ sân) + Upload Bill đối soát  

---

## 1. TỔNG QUAN HỆ THỐNG & CƠ CHẾ TRUNG GIAN

Hệ thống đóng vai trò **Nền tảng Trung gian kết nối (Broker Platform)** giữa Khách hàng (Customer) và Chủ sân (Court Owner) dành cho các môn thể thao: **Cầu lông, Pickleball, Bóng bàn**.

### Các đặc trưng chính:
1. **Không giữ tiền trung gian (Direct-to-Owner):** Dòng tiền chuyển thẳng từ tài khoản ngân hàng của Khách hàng đến Ngân hàng của Chủ sân qua chuẩn VietQR tự động.
2. **Quản lý lịch chống trùng (Conflict Lock):** Áp dụng kỹ thuật khóa giữ chỗ tạm thời (Temporary Atomic Slot Lock) trong 10 phút để triệt tiêu race condition (hai người cùng đặt một slot giờ).
3. **Ma trận đặt sân trực quan (Alobo Style):** Lưới Grid 2D (Hàng = Khung giờ, Cột = Sân thi đấu) trực quan, cập nhật trạng thái thời gian thực.
4. **Đối soát minh chứng:** Lưu trữ ảnh chụp màn hình chuyển khoản (Bill), hỗ trợ Chủ sân duyệt nhanh hoặc từ chối và giải phóng slot ngay trên Dashboard.
5. **Liên hệ trực tiếp:** Hiển thị Hotline/Zalo của Chủ sân trên từng phiếu đặt chỗ để hai bên tự giải quyết sự cố phát sinh.

---

## 2. ÁP DỤNG 4 NGUYÊN LÝ HƯỚNG ĐỐI TƯỢNG (OOP PILLARS)

* **Kế thừa (Inheritance):**  
  Lớp `User` kế thừa trực tiếp từ `django.contrib.auth.models.AbstractUser`, tái sử dụng toàn bộ cơ chế xác thực, mã hóa mật khẩu và mở rộng phân quyền 3 roles: `CUSTOMER`, `OWNER`, `ADMIN`.
* **Đóng gói (Encapsulation):**  
  Toàn bộ dữ liệu trạng thái và logic xử lý nghiệp vụ được đóng gói trực tiếp bên trong các phương thức của Model:
  * `Facility.generate_vietqr_url(amount, memo)`: Tự động đóng gói logic định dạng chuẩn ảnh VietQR API.
  * `Booking.upload_proof_and_submit(proof_image)`: Nhận file bill và kích hoạt chuyển trạng thái đơn.
  * `Booking.approve_by_owner(owner_user)` & `Booking.reject_by_owner(reason)`: Kiểm tra nghiệp vụ và chuyển trạng thái State Machine.
  * `BookingSlot.lock_slot(user)` & `release_slot()`: Kiểm soát giữ chỗ nguyên tử.
* **Đa hình (Polymorphism):**  
  Áp dụng trong lớp `PricingRule.calculate_price(start_time, end_time)`. Hỗ trợ các chiến lược tính giá linh hoạt theo giờ Cao điểm, giờ Thường, ngày Cuối tuần hoặc theo thời lượng slot.
* **Trừu tượng hóa (Abstraction):**  
  Trừu tượng hóa đơn vị lịch trình phức tạp thành các đơn vị nguyên tử `BookingSlot`, tách biệt hoàn toàn giữa việc quản trị của Chủ sân và thao tác chọn slot đơn giản của Khách hàng.

---

## 3. MÁY TRẠNG THÁI ĐẶT SÂN (BOOKING STATE MACHINE)

```
[ AVAILABLE ] 
     │
     │ Khách hàng chọn slot & Bấm Đặt (Lock 10 phút)
     ▼
[ PENDING_BILL ] 
     │
     ├──(Khách quét VietQR & Tải ảnh Bill)──► [ WAITING_APPROVAL ]
     │                                                │
     │ (Quá hạn 10 phút)                              ├──(Chủ sân duyệt)──► [ CONFIRMED ]
     ▼                                                │
[ CANCELLED ] ◄─────────(Chủ sân từ chối)─────────────┘
     │
     ▼ (Tự động giải phóng Slot về AVAILABLE)
```

---

## 4. TÀI KHOẢN TRẢI NGHIỆM ĐƯỢC CẤP SẴN (SEED DATA)

| Vai trò | Tên đăng nhập | Mật khẩu | Quyền hạn & Chức năng |
| :--- | :--- | :--- | :--- |
| **Quản trị viên (Admin)** | `admin` | `admin123` | Quản trị toàn bộ hệ thống qua `/admin/` |
| **Chủ sân (Court Owner)** | `chusan1` | `owner123` | Xem Bảng điều khiển `/bookings/dashboard/`, soi bill và duyệt đơn |
| **Khách hàng (Customer)** | `khachhang1` | `customer123` | Tìm sân, chọn slot trên ma trận, quét VietQR, nộp bill |

---

## 5. HƯỚNG DẪN CÀI ĐẶT & CHẠY ỨNG DỤNG

### 5.1. Cài đặt môi trường
Đảm bảo máy đã cài đặt Python 3.11 trở lên:
```bash
# Kiểm tra Python
python --version
```

### 5.2. Chạy Migration & Nạp dữ liệu mẫu
```bash
# Áp dụng cơ sở dữ liệu
python manage.py migrate

# Nạp dữ liệu mẫu (Cụm sân, Sân đơn, Môn thể thao, Tài khoản & Slot)
python seed_data.py
```

### 5.3. Chạy Unit Tests kiểm thử
Hệ thống đi kèm bộ kiểm thử tự động kiểm tra tính chất OOP, cơ chế chống trùng slot (Concurrency Lock) và luồng duyệt State Machine:
```bash
python manage.py test
```

### 5.4. Khởi động Web Server
```bash
python manage.py runserver
```
Truy cập trình duyệt tại: **http://127.0.0.1:8000/**

---

## 6. DANH SÁCH ĐƯỜNG DẪN (SITEMAP)

* **Trang chủ & Danh sách sân:** `http://127.0.0.1:8000/facilities/`
* **Ma trận đặt sân Alobo Grid 2D:** `http://127.0.0.1:8000/facilities/<facility_id>/`
* **Bảng điều khiển duyệt bill của Chủ sân:** `http://127.0.0.1:8000/bookings/dashboard/`
* **Tra cứu mã đơn đặt:** `http://127.0.0.1:8000/bookings/lookup/`
* **Lịch sử đặt sân của tôi:** `http://127.0.0.1:8000/bookings/history/`
* **Đăng nhập:** `http://127.0.0.1:8000/users/login/`
* **Đăng ký:** `http://127.0.0.1:8000/users/register/`
* **Django Admin:** `http://127.0.0.1:8000/admin/`

