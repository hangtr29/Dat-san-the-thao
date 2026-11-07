from django.contrib import admin
from django.utils.html import format_html
from .models import SportCategory, Facility, Court, PricingRule, FacilityReview, FacilityStatus

class CourtInline(admin.TabularInline):
    model = Court
    extra = 2

class PricingRuleInline(admin.TabularInline):
    model = PricingRule
    extra = 1

class FacilityReviewInline(admin.TabularInline):
    model = FacilityReview
    extra = 0
    readonly_fields = ('created_at',)

@admin.register(SportCategory)
class SportCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'court_count_display')
    prepopulated_fields = {'slug': ('name',)}

    def court_count_display(self, obj):
        return obj.count_courts()
    court_count_display.short_description = "Số lượng sân khả dụng"

@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'status_badge', 'verified_badge', 'hotline_display', 'reputation_score', 'average_rating_display', 'active_status')
    list_filter = ('status', 'is_verified', 'active_status', 'bank_name')
    search_fields = ('name', 'address', 'phone_contact', 'hotline', 'bank_account_no', 'bank_account_name')
    inlines = [CourtInline, PricingRuleInline, FacilityReviewInline]
    actions = ['verify_facility_action', 'suspend_facility_action']

    fieldsets = (
        ("Thông tin chung & Xác thực kiểm duyệt", {
            'fields': ('name', 'owner', 'status', 'is_verified', 'reputation_score', 'address', 'phone_contact', 'hotline', 'image', 'active_status')
        }),
        ("Cấu hình Ngân hàng & Mã QR Thanh toán (VietQR)", {
            'fields': ('bank_name', 'bank_account_no', 'bank_account_name', 'custom_qr_image'),
            'description': "Hệ thống tự động sinh VietQR chuẩn Napas 247 theo thông tin ngân hàng. Nếu tải lên 'Ảnh mã QR', hệ thống sẽ ưu tiên hiển thị ảnh đó."
        }),
        ("Khung giờ mở cửa & Tọa độ GPS", {
            'fields': ('open_time', 'close_time', 'latitude', 'longitude')
        }),
    )

    def status_badge(self, obj):
        if obj.status == FacilityStatus.ACTIVE:
            return format_html('<span style="background-color:#16a34a;color:white;padding:3px 8px;border-radius:4px;font-weight:600;font-size:11px;">Hoạt động</span>')
        elif obj.status == FacilityStatus.PENDING_REVIEW:
            return format_html('<span style="background-color:#d97706;color:white;padding:3px 8px;border-radius:4px;font-weight:600;font-size:11px;">Chờ duyệt</span>')
        return format_html('<span style="background-color:#dc2626;color:white;padding:3px 8px;border-radius:4px;font-weight:600;font-size:11px;">Tạm ngưng</span>')
    status_badge.short_description = "Trạng thái vận hành"

    def verified_badge(self, obj):
        if obj.is_verified:
            return format_html('<span style="color:#0284c7;font-weight:bold;">Tích xanh ✓</span>')
        return format_html('<span style="color:#94a3b8;">Chưa xác thực</span>')
    verified_badge.short_description = "Xác minh"

    def hotline_display(self, obj):
        return obj.get_display_hotline()
    hotline_display.short_description = "Hotline"

    def average_rating_display(self, obj):
        return f"{obj.get_average_rating()} ★ ({obj.get_total_reviews()})"
    average_rating_display.short_description = "Đánh giá"

    def verify_facility_action(self, request, queryset):
        updated = queryset.update(is_verified=True, status=FacilityStatus.ACTIVE, active_status=True)
        self.message_user(request, f"Đã cấp tích xanh và kích hoạt {updated} cụm sân thành công.")
    verify_facility_action.short_description = "Cấp tích xanh KYC & Kích hoạt cụm sân"

    def suspend_facility_action(self, request, queryset):
        updated = queryset.update(status=FacilityStatus.SUSPENDED)
        self.message_user(request, f"Đã chuyển {updated} cụm sân sang trạng thái tạm ngưng.")
    suspend_facility_action.short_description = "Tạm ngưng hoạt động cụm sân"

@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    list_display = ('court_name', 'facility', 'category', 'surface_type', 'is_active')
    list_filter = ('facility', 'category', 'is_active')
    search_fields = ('court_name', 'facility__name')

@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ('facility', 'day_of_week', 'start_time', 'end_time', 'price_per_hour')
    list_filter = ('facility', 'day_of_week')

@admin.register(FacilityReview)
class FacilityReviewAdmin(admin.ModelAdmin):
    list_display = ('facility', 'rating', 'reviewer_name', 'booking', 'has_owner_reply_display', 'created_at')
    list_filter = ('rating', 'facility')
    search_fields = ('reviewer_name', 'comment', 'owner_reply', 'facility__name', 'booking__booking_code')
    readonly_fields = ('created_at',)
    fields = ('facility', 'booking', 'user', 'reviewer_name', 'rating', 'comment', 'owner_reply', 'owner_reply_at', 'created_at')

    def has_owner_reply_display(self, obj):
        return "✅ Đã phản hồi" if obj.owner_reply else "⏳ Chưa phản hồi"
    has_owner_reply_display.short_description = "Phản hồi chủ sân"

    def save_model(self, request, obj, form, change):
        if obj.owner_reply and not obj.owner_reply_at:
            from django.utils import timezone
            obj.owner_reply_at = timezone.now()
        super().save_model(request, obj, form, change)

