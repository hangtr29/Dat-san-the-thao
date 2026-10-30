import uuid
import re
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError

class UserRole(models.TextChoices):
    CUSTOMER = 'CUSTOMER', 'Khách hàng'
    OWNER = 'OWNER', 'Chủ sân'
    ADMIN = 'ADMIN', 'Quản trị viên'

class User(AbstractUser):
    """
    Kế thừa AbstractUser (Tính kế thừa - Inheritance).
    Mở rộng định danh bằng UUID, số điện thoại, vai trò nghiệp vụ (Role-based Access Control).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
        verbose_name="Vai trò"
    )
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name="Ảnh đại diện")

    class Meta:
        verbose_name = "Người dùng"
        verbose_name_plural = "Người dùng"

    def clean_phone(self):
        """Tính đóng gói (Encapsulation): Kiểm tra định dạng số điện thoại Việt Nam"""
        if self.phone:
            pattern = r'^(0|\+84)[3|5|7|8|9][0-9]{8}$'
            if not re.match(pattern, self.phone):
                raise ValidationError("Số điện thoại không đúng định dạng Việt Nam.")
        return self.phone

    def clean(self):
        super().clean()
        self.clean_phone()

    def is_owner(self) -> bool:
        """Kiểm tra có phải chủ sân"""
        return self.role == UserRole.OWNER

    def is_customer(self) -> bool:
        """Kiểm tra có phải khách hàng"""
        return self.role == UserRole.CUSTOMER

    def is_admin_role(self) -> bool:
        """Kiểm tra vai trò quản trị"""
        return self.role == UserRole.ADMIN or self.is_superuser

    def __str__(self):
        role_label = self.get_role_display()
        display_name = self.get_full_name() or self.username
        return f"{display_name} ({role_label})"
