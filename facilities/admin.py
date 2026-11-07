from django.contrib import admin
from .models import SportCategory, Facility, Court, PricingRule, FacilityReview

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
    list_display = ('name', 'owner', 'phone_contact', 'bank_name', 'bank_account_no', 'bank_account_name', 'average_rating_display', 'active_status')
    list_filter = ('active_status', 'bank_name')
    search_fields = ('name', 'address', 'phone_contact', 'bank_account_no', 'bank_account_name')
    inlines = [CourtInline, PricingRuleInline, FacilityReviewInline]
    fieldsets = (
        ("Thông tin chung", {
            'fields': ('name', 'owner', 'address', 'phone_contact', 'image', 'active_status')
        }),
        ("Cấu hình Ngân hàng & Mã QR Thanh toán (VietQR)", {
            'fields': ('bank_name', 'bank_account_no', 'bank_account_name', 'custom_qr_image'),
            'description': "Hệ thống tự động sinh VietQR chuẩn Napas 247 theo thông tin ngân hàng. Nếu tải lên 'Ảnh mã QR', hệ thống sẽ ưu tiên hiển thị ảnh đó."
        }),
        ("Khung giờ mở cửa & Tọa độ", {
            'fields': ('open_time', 'close_time', 'latitude', 'longitude')
        }),
    )

    def average_rating_display(self, obj):
        return f"{obj.get_average_rating()} ★ ({obj.get_total_reviews()})"
    average_rating_display.short_description = "Đánh giá"

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

