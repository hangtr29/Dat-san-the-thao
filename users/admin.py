from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

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
