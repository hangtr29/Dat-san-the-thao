# Hướng dẫn cấu hình Google Maps API Key (miễn phí)

## 1. Tạo API key

1. Truy cập: https://console.cloud.google.com/apis/credentials
2. Đăng nhập bằng tài khoản Google (Gmail).
3. Ở trên cùng, chọn **Select a project** → nếu chưa có project, bấm **New Project**:
   - Project name: `SportBook Map`
   - Billing: chọn **No billing account** (miễn phí vẫn đủ dùng cho mức sử dụng thấp)
4. Bấm **Create credentials** → **API key**.
5. Màn hình hiện key dạng `AIza...` → **Copy** và lưu lại.

## 2. Bật các API cần thiết

Vào https://console.cloud.google.com/apis/library, tìm và bấm **Enable** cho từng API:

| API | Bắt buộc? | Dùng để |
|---|---|---|
| **Maps JavaScript API** | Có | Nạp thư viện Google Maps (Places autocomplete, Geocoder) |
| **Maps Static API** | Không bắt buộc | Chỉ dùng nếu bạn render ảnh bản đồ tĩnh |
| **Geocoding API** | Nên bật | Chuyển địa chỉ → toạ độ |

> **Lưu ý về billing:** Từ 2022, Google yêu cầu gắn **Billing account** (thẻ Visa/PayPal miễn phí)
> để sử dụng Google Maps Platform, kể cả bản miễn phí. Họ cấp **$200/tháng** credit miễn phí,
> và Google Maps JS API tính ~$7/1000 lượt tải. Nếu không muốn gắn thẻ, hãy bỏ qua API key
> và dùng chế độ **keyless tiles** (mặc định của dự án) — hoạt động tốt, không cần key.

## 3. Hạn chế API key (BẮT BUỘC về mặt an toàn)

Ngay sau khi tạo key, bấm **Edit API key** và thiết lập:

### Application restrictions → HTTP referrers (Websites)
Thêm các domain sẽ chạy website:
```
http://127.0.0.1:8000/*
http://localhost:8000/*
https://your-domain.com/*
https://*.your-domain.com/*
```

### API restrictions → Restrict key
Chọn **Restrict key** → tick:
- ✅ Maps JavaScript API
- ✅ Maps Static API (nếu dùng)
- ✅ Geocoding API (nếu dùng)

> ⚠️ **Không bao giờ** dùng key không có restriction. Nếu bị lạm dụng, Google sẽ ngắt key và tính tiền vào thẻ của bạn.

## 4. Đưa key vào dự án

Dự án đọc key từ **biến môi trường** `GOOGLE_MAPS_API_KEY` (không hardcode vào code).

### Windows (PowerShell) — chạy 1 lần cho phiên hiện tại:
```powershell
$env:GOOGLE_MAPS_API_KEY = "AIzaSy...your-key-here"
python manage.py runserver
```

### Windows — chạy vĩnh viễn cho user hiện tại:
```powershell
setx GOOGLE_MAPS_API_KEY "AIzaSy...your-key-here"
```
(đóng & mở lại terminal sau khi chạy `setx`)

### Linux / macOS:
```bash
export GOOGLE_MAPS_API_KEY="AIzaSy...your-key-here"
python manage.py runserver
```

### Dùng file `.env` (khuyến nghị cho production)
Thêm dòng sau vào file `.env` ở thư mục gốc dự án:
```
GOOGLE_MAPS_API_KEY=AIzaSy...your-key-here
```

> `.env` đã nằm trong `.gitignore` nên key **không bị push lên GitHub**.

## 5. Xác nhận hoạt động

1. Khởi động lại server: `python manage.py runserver`
2. Mở http://127.0.0.1:8000/facilities/map/
3. Hard refresh (`Ctrl + Shift + R`)
4. Kiểm tra:
   - Badge dưới bản đồ hiện **"Google Maps"** → đang dùng key chính thức
   - DevTools → Console: không có lỗi `RefererNotAllowedMapError` hay `InvalidKeyMapError`
   - DevTools → Network: request `maps.googleapis.com/maps/api/tile?key=AIza...` trả **200**

## 6. Nếu gặp lỗi thường gặp

| Lỗi trong Console | Nguyên nhân | Cách sửa |
|---|---|---|
| `RefererNotAllowedMapError` | Referrer chưa được whitelist | Thêm domain vào **HTTP referrers** (mục 3) |
| `InvalidKeyMapError` | Key sai hoặc đã bị xoá | Tạo lại key |
| `REQUEST_DENIED` | API chưa được Enable | Bật Maps JavaScript API (mục 2) |
| `BillingNotEnabledMapError` | Chưa gắn billing account | Gắn thẻ miễn phí, hoặc bỏ key & dùng keyless mode |

## 7. Chế độ không cần key (mặc định)

Nếu **không** đặt `GOOGLE_MAPS_API_KEY`, dự án vẫn chạy bình thường:
- Dùng tile Google Maps công khai (`mt0..mt3.google.com`) — **không cần key**
- Tự động probe & fallback qua 6 nhà cung cấp nếu provider hiện tại bị chặn (403)
- Nút **"Đổi nền bản đồ"** cho phép chuyển thủ công

Có thể tắt tile Google công khai bằng cách đặt:
```
GOOGLE_MAPS_KEYLESS_TILES=false
```
