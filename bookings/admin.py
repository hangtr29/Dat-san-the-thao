from django.contrib import admin
from django.utils.html import format_html
from .models import Booking, BookingSlot

class BookingSlotInline(admin.TabularInline):
    model = BookingSlot
    extra = 0
    readonly_fields = ('court', 'date', 'start_time', 'end_time', 'price')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_code', 'customer', 'total_amount_display', 'status_badge', 'created_at', 'proof_preview')
    list_filter = ('status', 'created_at')
    search_fields = ('booking_code', 'customer__username', 'customer__phone')
    readonly_fields = ('booking_code', 'created_at')
    inlines = [BookingSlotInline]

    def total_amount_display(self, obj):
        return f"{int(obj.total_amount):,} đ"
    total_amount_display.short_description = "Tổng tiền"

    def status_badge(self, obj):
        colors = {
            'PENDING_BILL': '#f59e0b',
            'WAITING_APPROVAL': '#3b82f6',
            'CONFIRMED': '#10b981',
            'REJECTED': '#ef4444',
            'CANCELLED': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            f'<span style="background-color: {color}; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;">{obj.get_status_display()}</span>'
        )
    status_badge.short_description = "Trạng thái"

    def proof_preview(self, obj):
        if obj.payment_proof:
            return format_html(f'<a href="{obj.payment_proof.url}" target="_blank"><img src="{obj.payment_proof.url}" style="height: 50px; border-radius: 4px;"/></a>')
        return "Chưa nộp bill"
    proof_preview.short_description = "Ảnh Bill"

@admin.register(BookingSlot)
class BookingSlotAdmin(admin.ModelAdmin):
    list_display = ('court', 'date', 'start_time', 'end_time', 'price', 'locked_by', 'is_locked_display', 'booking')
    list_filter = ('date', 'court__facility', 'court')
    search_fields = ('court__court_name', 'court__facility__name')

    def is_locked_display(self, obj):
        return "Đang giữ chỗ" if obj.is_locked() else "Trống / Mở"
    is_locked_display.short_description = "Tình trạng khóa"
