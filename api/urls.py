"""
Định tuyến RESTful API.

Cấu trúc URL chuẩn REST (danh từ số nhiều + động từ hành động):
    /api/auth/register/            POST   Đăng ký
    /api/auth/login/               POST   Đăng nhập -> trả access/refresh token
    /api/auth/logout/              POST   Đăng xuất (blacklist token)
    /api/auth/token/refresh/       POST   Lấy access token mới
    /api/auth/me/                  GET    Thông tin user hiện tại

    /api/categories/               GET    Danh mục môn thể thao
    /api/facilities/               GET    Danh sách cụm sân (tìm kiếm/lọc)
    /api/facilities/<id>/          GET    Chi tiết cụm sân
    /api/facilities/map/           GET    Dữ liệu marker bản đồ
    /api/courts/                   GET    Sân thi đấu
    /api/pricing-rules/            GET    Bảng giá
    /api/addons/                   GET    Dịch vụ bổ sung
    /api/coupons/                  GET    Mã giảm giá
    /api/coupons/validate_code/    GET    Kiểm tra mã giảm giá

    /api/slots/                    GET    Khung giờ trống theo ngày
    /api/bookings/                 GET/POST   Đơn đặt sân
    /api/bookings/<code>/          GET    Chi tiết đơn
    /api/bookings/<code>/upload-proof/  POST  Tải ảnh bill
    /api/bookings/<code>/cancel/   POST  Khách hủy đơn
    /api/bookings/<code>/approve/  POST  Chủ sân duyệt
    /api/bookings/<code>/reject/   POST  Chủ sân từ chối
    /api/bookings/lookup/<code>/   GET   Tra cứu đơn bằng mã

    /api/favorites/                GET/POST/DELETE  Sân yêu thích
    /api/favorites/toggle/         POST  Bật/tắt yêu thích
    /api/notifications/            GET    Trung tâm thông báo
    /api/notifications/mark-read/  POST  Đánh dấu đã xem

    /api/owner/facilities/         GET/POST  Cụm sân của chủ sân
    /api/owner/bookings/           GET    Đơn tới cụm sân của tôi
    /api/owner/bookings/stats/     GET    Thống kê dashboard
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

router = DefaultRouter()
router.register(r'categories', views.SportCategoryViewSet, basename='category')
router.register(r'facilities', views.FacilityViewSet, basename='facility')
router.register(r'courts', views.CourtViewSet, basename='court')
router.register(r'pricing-rules', views.PricingRuleViewSet, basename='pricing-rule')
router.register(r'addons', views.AddonServiceViewSet, basename='addon')
router.register(r'coupons', views.CouponViewSet, basename='coupon')
router.register(r'slots', views.SlotViewSet, basename='slot')
router.register(r'bookings', views.BookingViewSet, basename='booking')
router.register(r'favorites', views.FavoriteViewSet, basename='favorite')
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'owner/facilities', views.OwnerFacilityViewSet, basename='owner-facility')
router.register(r'owner/bookings', views.OwnerBookingViewSet, basename='owner-booking')

urlpatterns = [
    # ---- Xác thực ----
    path('auth/register/', views.RegisterView.as_view(), name='api-register'),
    path('auth/login/', views.LoginView.as_view(), name='api-login'),
    path('auth/logout/', views.LogoutView.as_view(), name='api-logout'),
    path('auth/me/', views.CurrentUserView.as_view(), name='api-me'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='api-token-refresh'),
    path('auth/token/', TokenObtainPairView.as_view(), name='api-token-obtain'),

    # ---- ViewSet tự động ----
    path('', include(router.urls)),
]
