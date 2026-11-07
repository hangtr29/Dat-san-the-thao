from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils import timezone
from .models import User, OwnerProfile, KYCStatus, SubscriptionPlan, SubscriptionOrder, SubscriptionOrderStatus

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'phone', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Thông tin bổ sung (OOP Extends)', {'fields': ('phone', 'role', 'avatar')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Thông tin bổ sung (OOP Extends)', {'fields': ('phone', 'role', 'avatar')}),
    )
    search_fields = ('username', 'phone', 'email', 'first_name', 'last_name')


@admin.register(OwnerProfile)
class OwnerProfileAdmin(admin.ModelAdmin):
    """
    Mục tiêu 1 & 3: Giao diện Quản trị viên duyệt KYC hồ sơ chủ sân & Gia hạn gói duy trì.
    """
    list_display = (
        'user', 'id_card_number', 'kyc_status_badge', 
        'subscription_status_badge', 'subscription_expires_at', 'bank_info_display'
    )
    list_filter = ('kyc_status', 'bank_name')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'id_card_number', 'bank_account_number')
    readonly_fields = ('created_at', 'updated_at', 'front_card_preview', 'back_card_preview', 'license_preview')

    fieldsets = (
        ("Tài khoản Chủ sân", {
            'fields': ('user', 'kyc_status', 'kyc_rejection_reason', 'subscription_expires_at')
        }),
        ("Định danh CCCD (Ảnh thực địa)", {
            'fields': ('id_card_number', 'id_card_front', 'front_card_preview', 'id_card_back', 'back_card_preview')
        }),
        ("Giấy phép kinh doanh / Hợp đồng mặt bằng", {
            'fields': ('business_license', 'license_preview')
        }),
        ("Thông tin Ngân hàng & VietQR", {
            'fields': ('bank_name', 'bank_account_number', 'bank_account_holder', 'bank_qr_image')
        }),
        ("Thời gian hệ thống", {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['approve_kyc_selected', 'reject_kyc_selected', 'extend_30_days', 'extend_365_days']

    def kyc_status_badge(self, obj):
        colors = {
            KYCStatus.KYC_VERIFIED: 'green',
            KYCStatus.KYC_PENDING: 'orange',
            KYCStatus.KYC_REJECTED: 'red',
        }
        color = colors.get(obj.kyc_status, 'gray')
        return format_html(
            f'<span style="background-color: {color}; color: white; padding: 3px 8px; border-radius: 10px; font-weight: bold; font-size: 11px;">{obj.get_kyc_status_display()}</span>'
        )
    kyc_status_badge.short_description = "Trạng thái KYC"

    def subscription_status_badge(self, obj):
        if obj.is_subscription_active():
            return format_html('<span style="color: green; font-weight: bold;">✓ Còn hạn</span>')
        return format_html('<span style="color: red; font-weight: bold;">✕ Hết hạn</span>')
    subscription_status_badge.short_description = "Gói duy trì"

    def bank_info_display(self, obj):
        return f"{obj.bank_name}: {obj.bank_account_number} ({obj.bank_account_holder})"
    bank_info_display.short_description = "Ngân hàng nhận tiền"

    def front_card_preview(self, obj):
        if obj.id_card_front:
            return format_html(f'<a href="{obj.id_card_front.url}" target="_blank"><img src="{obj.id_card_front.url}" style="max-height: 120px; border-radius: 8px;" /></a>')
        return "Chưa tải ảnh"
    front_card_preview.short_description = "Xem trước CCCD mặt trước"

    def back_card_preview(self, obj):
        if obj.id_card_back:
            return format_html(f'<a href="{obj.id_card_back.url}" target="_blank"><img src="{obj.id_card_back.url}" style="max-height: 120px; border-radius: 8px;" /></a>')
        return "Chưa tải ảnh"
    back_card_preview.short_description = "Xem trước CCCD mặt sau"

    def license_preview(self, obj):
        if obj.business_license:
            return format_html(f'<a href="{obj.business_license.url}" target="_blank"><img src="{obj.business_license.url}" style="max-height: 120px; border-radius: 8px;" /></a>')
        return "Chưa tải ảnh"
    license_preview.short_description = "Xem trước Giấy phép KD"

    @admin.action(description="✓ Phê duyệt KYC (Cấp tích xanh xác minh)")
    def approve_kyc_selected(self, request, queryset):
        count = queryset.update(kyc_status=KYCStatus.KYC_VERIFIED, kyc_rejection_reason='')
        self.message_user(request, f"Đã duyệt KYC thành công cho {count} hồ sơ chủ sân!")

    @admin.action(description="✕ Từ chối KYC các hồ sơ đã chọn")
    def reject_kyc_selected(self, request, queryset):
        count = queryset.update(kyc_status=KYCStatus.KYC_REJECTED)
        self.message_user(request, f"Đã từ chối {count} hồ sơ KYC.")

    @admin.action(description="+ Gia hạn thêm 30 ngày dịch vụ duy trì")
    def extend_30_days(self, request, queryset):
        for profile in queryset:
            profile.extend_subscription(30)
        self.message_user(request, f"Đã cộng thêm 30 ngày duy trì cho {queryset.count()} chủ sân.")

    @admin.action(description="+ Gia hạn thêm 365 ngày (1 năm) duy trì")
    def extend_365_days(self, request, queryset):
        for profile in queryset:
            profile.extend_subscription(365)
        self.message_user(request, f"Đã cộng thêm 365 ngày duy trì cho {queryset.count()} chủ sân.")


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration_days', 'price_display', 'is_active')
    list_filter = ('is_active',)

    def price_display(self, obj):
        return f"{int(obj.price):,} đ"
    price_display.short_description = "Đơn giá (VNĐ)"


@admin.register(SubscriptionOrder)
class SubscriptionOrderAdmin(admin.ModelAdmin):
    """
    Mục tiêu 3: Giao diện kiểm tra đối soát biên lai & Phê duyệt đơn nộp phí duy trì nền tảng.
    """
    list_display = (
        'order_code', 'owner', 'plan', 'amount_display', 
        'payment_proof_display', 'status_badge', 'created_at', 'approved_at'
    )
    list_filter = ('status', 'plan')
    search_fields = ('order_code', 'owner__username', 'owner__first_name')
    readonly_fields = ('order_code', 'owner', 'plan', 'amount', 'created_at', 'approved_at', 'approved_by', 'proof_preview')
    actions = ['approve_orders_action', 'reject_orders_action']

    def amount_display(self, obj):
        return f"{int(obj.amount):,} đ"
    amount_display.short_description = "Số tiền"

    def status_badge(self, obj):
        colors = {
            SubscriptionOrderStatus.APPROVED: 'green',
            SubscriptionOrderStatus.PENDING: 'orange',
            SubscriptionOrderStatus.REJECTED: 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            f'<span style="background-color: {color}; color: white; padding: 3px 8px; border-radius: 10px; font-weight: bold; font-size: 11px;">{obj.get_status_display()}</span>'
        )
    status_badge.short_description = "Trạng thái đơn"

    def payment_proof_display(self, obj):
        if obj.payment_proof:
            return format_html(f'<a href="{obj.payment_proof.url}" target="_blank">🔍 Soi biên lai</a>')
        return "Chưa có ảnh"
    payment_proof_display.short_description = "Biên lai"

    def proof_preview(self, obj):
        if obj.payment_proof:
            return format_html(f'<a href="{obj.payment_proof.url}" target="_blank"><img src="{obj.payment_proof.url}" style="max-height: 250px; border-radius: 12px;" /></a>')
        return "Chưa tải ảnh"
    proof_preview.short_description = "Ảnh biên lai chuyển khoản gốc"

    @admin.action(description="✓ Duyệt đơn đóng tiền & Tự động cộng ngày duy trì")
    def approve_orders_action(self, request, queryset):
        success_count = 0
        for order in queryset:
            if order.approve_order(request.user):
                success_count += 1
        self.message_user(request, f"Đã duyệt thành công {success_count} đơn và tự động cộng ngày duy trì cho Chủ sân!")

    @admin.action(description="✕ Từ chối đơn nộp tiền")
    def reject_orders_action(self, request, queryset):
        for order in queryset:
            order.reject_order("Biên lai không hợp lệ hoặc chưa nhận được tiền.")
        self.message_user(request, f"Đã từ chối {queryset.count()} đơn nộp phí.")

