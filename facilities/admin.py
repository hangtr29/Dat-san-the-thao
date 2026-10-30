from django.contrib import admin
from .models import SportCategory, Facility, Court, PricingRule

class CourtInline(admin.TabularInline):
    model = Court
    extra = 2

class PricingRuleInline(admin.TabularInline):
    model = PricingRule
    extra = 1

@admin.register(SportCategory)
class SportCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'court_count_display')
    prepopulated_fields = {'slug': ('name',)}

    def court_count_display(self, obj):
        return obj.count_courts()
    court_count_display.short_description = "Số lượng sân khả dụng"

@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'phone_contact', 'bank_name', 'bank_account_no', 'bank_account_name', 'active_status')
    list_filter = ('active_status', 'bank_name')
    search_fields = ('name', 'address', 'phone_contact', 'bank_account_no', 'bank_account_name')
    inlines = [CourtInline, PricingRuleInline]

@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    list_display = ('court_name', 'facility', 'category', 'surface_type', 'is_active')
    list_filter = ('facility', 'category', 'is_active')
    search_fields = ('court_name', 'facility__name')

@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ('facility', 'day_of_week', 'start_time', 'end_time', 'price_per_hour')
    list_filter = ('facility', 'day_of_week')
