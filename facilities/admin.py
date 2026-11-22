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
    list_display = ('name', 'owner', 'status_badge', 'verified_badge', 'hotline_display', 'court_count_display', 'reputation_score', 'average_rating_display', 'active_status')
    list_filter = ('status', 'is_verified', 'active_status', 'bank_name')
    search_fields = ('name', 'address', 'phone_contact', 'hotline', 'bank_account_no', 'bank_account_name')
    list_editable = ('active_status',)
    list_per_page = 25
    ordering = ('-created_at',)
    inlines = [CourtInline, PricingRuleInline, FacilityReviewInline]
    actions = ['verify_facility_action', 'suspend_facility_action', 'reactivate_facility_action']

    fieldsets = (
        ("Thông tin chung & Xác thực kiểm duyệt", {
            'fields': ('name', 'owner', 'status', 'is_verified', 'reputation_score', 'address', 'phone_contact', 'hotline', 'image', 'active_status'),
            'description': (
                "<b>Quy trình duyệt cụm sân:</b> Chủ sân đăng ký tại <code>/facilities/owner/facility/register/</code> "
                "→ hồ sơ ở trạng thái <i>Chờ duyệt hồ sơ</i> → chọn hồ sơ và bấm "
                "<b>\"Cấp tích xanh KYC & Kích hoạt cụm sân\"</b> để duyệt. "
                "Cụm sân chỉ hiển thị công khai cho khách hàng khi <b>Trạng thái = Đang hoạt động</b> và <b>Tích xanh = Có</b>."
            )
        }),
        ("Cấu hình Ngân hàng & Mã QR Thanh toán (VietQR)", {
            'fields': ('bank_name', 'bank_account_no', 'bank_account_name', 'custom_qr_image'),
            'description': "Hệ thống tự động sinh VietQR chuẩn Napas 247 theo thông tin ngân hàng. Nếu tải lên 'Ảnh mã QR', hệ thống sẽ ưu tiên hiển thị ảnh đó."
        }),
        ("Khung giờ mở cửa & Tọa độ GPS", {
            'fields': ('open_time', 'close_time', 'latitude', 'longitude')
        }),
        ("Mô tả & Điểm nổi bật", {
            'fields': ('description', 'highlights'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Sắp xếp ưu tiên hồ sơ CHỜ DUYỆT lên đầu để admin xử lý nhanh"""
        return super().get_queryset(request).select_related('owner')

    def save_model(self, request, obj, form, change):
        """
        Chống trạng thái mâu thuẫn khi Admin sửa trực tiếp trong form:
        - Bật `active_status` (Đang hoạt động) mà `status` vẫn chưa ACTIVE
          -> tự nâng lên ACTIVE (vì admin đang chủ động bật công khai).
        - Tắt `active_status` -> tự chuyển `status` sang SUSPENDED
          (sân bị ẩn khỏi khách hàng nhưng vẫn giữ lịch sử chờ duyệt).
        """
        if obj.active_status and obj.status != FacilityStatus.ACTIVE:
            obj.status = FacilityStatus.ACTIVE
            if not obj.is_verified:
                # Admin chủ động bật công khai -> cấp luôn tích xanh KYC
                obj.is_verified = True
        elif not obj.active_status and obj.status == FacilityStatus.ACTIVE:
            obj.status = FacilityStatus.SUSPENDED

        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

    def court_count_display(self, obj):
        return f"{obj.courts.count()} sân"
    court_count_display.short_description = "Số sân"

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

    @admin.action(description="✅ Cấp tích xanh KYC & Kích hoạt cụm sân (Duyệt hồ sơ)")
    def verify_facility_action(self, request, queryset):
        from bookings.services_extras import NotificationService
        updated = 0
        for facility in queryset:
            facility.is_verified = True
            facility.status = FacilityStatus.ACTIVE
            facility.active_status = True
            facility.save(update_fields=['is_verified', 'status', 'active_status', 'updated_at'])
            # Thông báo cho chủ sân biết cụm sân đã được duyệt & mở bán
            NotificationService.notify(
                facility.owner, 'SYSTEM',
                f"Cụm sân '{facility.name}' đã được duyệt",
                "Hồ sơ cụm sân của bạn đã được Ban quản trị phê duyệt và cấp tích xanh KYC. "
                "Cụm sân hiện đã hiển thị công khai cho khách hàng đặt sân.",
                "/bookings/dashboard/",
            )
            updated += 1
        self.message_user(request, f"Đã cấp tích xanh và kích hoạt {updated} cụm sân thành công.")

    @admin.action(description="⏸️ Tạm ngưng hoạt động cụm sân")
    def suspend_facility_action(self, request, queryset):
        from bookings.services_extras import NotificationService
        updated = 0
        for facility in queryset:
            facility.status = FacilityStatus.SUSPENDED
            facility.save(update_fields=['status', 'updated_at'])
            NotificationService.notify(
                facility.owner, 'SYSTEM',
                f"Cụm sân '{facility.name}' đã bị tạm ngưng",
                "Cụm sân của bạn đã tạm ngưng hoạt động và không hiển thị với khách hàng. "
                "Vui lòng liên hệ Ban quản trị để được hỗ trợ.",
                "/bookings/dashboard/",
            )
            updated += 1
        self.message_user(request, f"Đã chuyển {updated} cụm sân sang trạng thái tạm ngưng.")

    @admin.action(description="↩️ Kích hoạt lại cụm sân đã tạm ngưng")
    def reactivate_facility_action(self, request, queryset):
        from bookings.services_extras import NotificationService
        updated = 0
        for facility in queryset:
            facility.status = FacilityStatus.ACTIVE
            facility.active_status = True
            facility.save(update_fields=['status', 'active_status', 'updated_at'])
            NotificationService.notify(
                facility.owner, 'SYSTEM',
                f"Cụm sân '{facility.name}' đã được kích hoạt lại",
                "Cụm sân của bạn đã hoạt động trở lại và hiển thị công khai cho khách hàng.",
                "/bookings/dashboard/",
            )
            updated += 1
        self.message_user(request, f"Đã kích hoạt lại {updated} cụm sân.")

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

