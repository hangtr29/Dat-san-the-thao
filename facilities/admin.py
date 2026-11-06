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
    list_display = ('facility', 'rating', 'reviewer_name', 'booking', 'created_at')
    list_filter = ('rating', 'facility')
    search_fields = ('reviewer_name', 'comment', 'facility__name', 'booking__booking_code')
    readonly_fields = ('created_at',)
