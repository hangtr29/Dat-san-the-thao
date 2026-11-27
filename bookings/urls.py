from django.urls import path
from . import views, views_admin

app_name = 'bookings'

urlpatterns = [
    path('lock-slots/', views.lock_and_book_slots, name='lock_slots'),
    path('confirm/<str:booking_code>/', views.booking_confirm, name='booking_confirm'),
    path('checkout/<str:booking_code>/', views.checkout_view, name='checkout'),
    path('upload-proof/<str:booking_code>/', views.upload_payment_proof, name='upload_proof'),
    path('detail/<str:booking_code>/', views.booking_detail, name='booking_detail'),
    path('api/status/<str:booking_code>/', views.booking_status_api, name='booking_status_api'),
    path('history/', views.booking_history, name='booking_history'),
    path('lookup/', views.booking_lookup, name='booking_lookup'),
    path('terms/', views.booking_terms, name='booking_terms'),
    path('refund-policy/', views.booking_refund_policy, name='booking_refund_policy'),

    # Đánh giá chất lượng sân (Review & Rating)
    path('review/<str:booking_code>/', views.submit_court_review, name='submit_review'),
    # Khách hủy đơn -> chủ sân nhận thông báo & giải phóng khung giờ
    path('cancel/<str:booking_code>/', views.customer_cancel_booking, name='customer_cancel'),

    # ---- Tính năng mới cho KHÁCH ĐẶT SÂN ----
    # Tải lại bill khi bị chủ sân từ chối (không phải đặt lại từ đầu)
    path('reupload-proof/<str:booking_code>/', views.upload_payment_proof_retry, name='reupload_proof'),
    # In / lưu phiếu đặt sân
    path('print/<str:booking_code>/', views.booking_print, name='booking_print'),
    # Đặt lịch cố định theo tuần
    path('recurring/create/', views.recurring_booking_create, name='recurring_create'),
    path('recurring/', views.recurring_booking_list, name='recurring_list'),
    # Mã giảm giá & khuyến mãi
    path('api/coupon/', views.coupon_validate_api, name='coupon_validate'),
    # Trung tâm thông báo
    path('notifications/', views.notification_list, name='notification_list'),
    path('api/notifications/', views.notification_api, name='notification_api'),
    path('api/notifications/read/', views.notification_mark_read, name='notification_mark_read'),
    # Chế độ "đã xem" kiểu Gmail: đánh dấu tất cả / bật-tắt từng thông báo
    path('api/notifications/mark-all-read/', views.notification_mark_all_read, name='notification_mark_all_read'),
    path('api/notifications/<uuid:notification_id>/toggle-read/',
         views.notification_toggle_read, name='notification_toggle_read'),

    # ---- Khu vực dành cho Admin trung gian (Giao diện trực quan) ----
    path('admin-panel/', views_admin.admin_platform_hub, name='admin_hub'),

    # ---- Khu vực dành cho Chủ sân (Owner) ----
    path('dashboard/', views.owner_dashboard, name='owner_dashboard'),
    path('owner/approve/<str:booking_code>/', views.owner_approve_booking, name='owner_approve'),
    path('owner/reject/<str:booking_code>/', views.owner_reject_booking, name='owner_reject'),
    path('owner/facility/update/', views.owner_update_facility, name='owner_update_facility'),
    path('owner/review/<uuid:review_id>/reply/', views.owner_reply_review, name='owner_reply_review'),
    path('owner/export/csv/', views.owner_export_revenue_csv, name='owner_export_revenue_csv'),
    path('owner/export/pdf/', views.owner_export_revenue_pdf, name='owner_export_revenue_pdf'),
    # ---- Tính năng mới cho CHỦ SÂN ----
    # Chi tiết đầy đủ một đơn
    path('owner/booking/<str:booking_code>/', views.owner_booking_detail, name='owner_booking_detail'),
    # Lịch xem nhanh sân trống/đã đặt theo ngày & tuần
    path('owner/calendar/', views.owner_calendar, name='owner_calendar'),
    # Xuất báo cáo Excel thật (.xlsx) tách theo sân và môn
    path('owner/export/excel/', views.owner_export_excel, name='owner_export_excel'),
    # Quản lý giá dịch vụ (thuê vợt, thức uống) theo từng sân
    path('owner/services/', views.owner_manage_addons, name='owner_services'),
    # Quản lý mô tả & thư viện ảnh cụm sân
    path('owner/gallery/', views.owner_manage_gallery, name='owner_gallery'),
    # KYC + gói duy trì nền tảng
    path('owner/kyc/', views.owner_kyc, name='owner_kyc'),
    # API polling đơn mới cho chủ sân
    path('owner/api/pending/', views.owner_pending_orders_api, name='owner_pending_api'),
]
