import uuid
import re
from datetime import timedelta
from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils import timezone

class UserRole(models.TextChoices):
    CUSTOMER = 'CUSTOMER', 'Khách hàng'
    OWNER = 'OWNER', 'Chủ sân'
    ADMIN = 'ADMIN', 'Quản trị viên'

class KYCStatus(models.TextChoices):
    KYC_PENDING = 'KYC_PENDING', 'Chờ xác minh'
    KYC_VERIFIED = 'KYC_VERIFIED', 'Đã xác minh (Tích xanh)'
    KYC_REJECTED = 'KYC_REJECTED', 'Bị từ chối'

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

    @property
    def is_subscription_active(self) -> bool:
        """Kiểm tra chủ sân có gói dịch vụ duy trì nền tảng còn hạn hay không"""
        if hasattr(self, 'owner_profile'):
            return self.owner_profile.is_subscription_active()
        return False

    @property
    def is_kyc_verified(self) -> bool:
        """Kiểm tra chủ sân đã được xác minh danh tính KYC hay chưa"""
        if hasattr(self, 'owner_profile'):
            return self.owner_profile.is_kyc_approved()
        return False

    def __str__(self):
        role_label = self.get_role_display()
        display_name = self.get_full_name() or self.username
        return f"{display_name} ({role_label})"


class OwnerProfile(models.Model):
    """
    Mục tiêu 1: Hồ sơ xác minh Chủ sân (KYC) & Chống sân ma.
    Liên kết 1-1 với User (Role = OWNER).
    Đóng gói thông tin CCCD, giấy phép kinh doanh, tài khoản ngân hàng và gói duy trì.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owner_profile',
        verbose_name="Tài khoản chủ sân"
    )
    
    # 1. Định danh cá nhân (CCCD / Hộ chiếu)
    id_card_number = models.CharField(max_length=25, blank=True, default='', verbose_name="Số CCCD / Hộ chiếu")
    id_card_front = models.ImageField(upload_to='kyc/id_cards/', null=True, blank=True, verbose_name="Ảnh CCCD mặt trước")
    id_card_back = models.ImageField(upload_to='kyc/id_cards/', null=True, blank=True, verbose_name="Ảnh CCCD mặt sau")

    # 2. Pháp lý hoạt động (Giấy phép KD / Hợp đồng thuê mặt bằng)
    business_license = models.ImageField(upload_to='kyc/licenses/', null=True, blank=True, verbose_name="Giấy phép KD / Hợp đồng thuê đất")

    # 3. Tài khoản nhận tiền (Đối soát trực tiếp)
    bank_name = models.CharField(max_length=50, blank=True, default='', verbose_name="Tên ngân hàng (VD: MBBank, VCB)")
    bank_account_number = models.CharField(max_length=50, blank=True, default='', verbose_name="Số tài khoản ngân hàng")
    bank_account_holder = models.CharField(max_length=150, blank=True, default='', verbose_name="Tên chủ tài khoản")
    bank_qr_image = models.ImageField(upload_to='kyc/qrcodes/', null=True, blank=True, verbose_name="Ảnh mã VietQR")

    # 4. Trạng thái kiểm duyệt KYC
    kyc_status = models.CharField(
        max_length=20,
        choices=KYCStatus.choices,
        default=KYCStatus.KYC_PENDING,
        verbose_name="Trạng thái xác minh KYC"
    )
    kyc_rejection_reason = models.TextField(blank=True, null=True, verbose_name="Lý do từ chối KYC")

    # 5. Quản lý gói phí dịch vụ duy trì
    subscription_expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời hạn gói dịch vụ duy trì")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày đăng ký")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        verbose_name = "Hồ sơ xác minh chủ sân (KYC)"
        verbose_name_plural = "Danh sách hồ sơ chủ sân (KYC)"

    def is_subscription_active(self) -> bool:
        """
        Tính đóng gói (Encapsulation): Kiểm tra thời hạn gói dịch vụ còn hiệu lực hay không.
        """
        if not self.subscription_expires_at:
            return False
        return self.subscription_expires_at > timezone.now()

    def is_kyc_approved(self) -> bool:
        """Kiểm tra đã được Ban quản trị duyệt KYC hay chưa"""
        return self.kyc_status == KYCStatus.KYC_VERIFIED

    def extend_subscription(self, days: int):
        """
        Tính đóng gói (Encapsulation): Cộng dồn thêm số ngày vào thời hạn gói dịch vụ duy trì.
        Nếu gói đã hết hạn thì tính mốc bắt đầu từ thời điểm hiện tại.
        """
        now = timezone.now()
        base_time = self.subscription_expires_at if (self.subscription_expires_at and self.subscription_expires_at > now) else now
        self.subscription_expires_at = base_time + timedelta(days=days)
        self.save()

    def __str__(self):
        return f"KYC: {self.user.get_full_name() or self.user.username} [{self.get_kyc_status_display()}]"


class SubscriptionPlan(models.Model):
    """
    Mục tiêu 3: Danh mục các gói thu phí duy trì nền tảng (1 tháng, 3 tháng, 1 năm).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name="Tên gói dịch vụ")
    duration_days = models.IntegerField(default=30, verbose_name="Thời lượng (ngày)")
    price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Giá gói (VNĐ)")
    description = models.TextField(blank=True, verbose_name="Mô tả quyền lợi")
    is_active = models.BooleanField(default=True, verbose_name="Đang mở bán")

    class Meta:
        verbose_name = "Gói phí duy trì"
        verbose_name_plural = "Danh mục gói phí duy trì"
        ordering = ['price']

    def __str__(self):
        return f"{self.name} ({self.duration_days} ngày) - {int(self.price):,} đ"


class SubscriptionOrderStatus(models.TextChoices):
    PENDING = 'PENDING', 'Chờ Ban quản trị duyệt'
    APPROVED = 'APPROVED', 'Đã duyệt kích hoạt'
    REJECTED = 'REJECTED', 'Bị từ chối'


class SubscriptionOrder(models.Model):
    """
    Mục tiêu 3: Đơn đăng ký gia hạn gói duy trì nền tảng của Chủ sân.
    Chuyển khoản trực tiếp theo VietQR của Admin Web và upload biên lai (bill).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_code = models.CharField(max_length=30, unique=True, verbose_name="Mã đơn đăng ký")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscription_orders',
        verbose_name="Chủ sân"
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name="Gói dịch vụ"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Số tiền thanh toán (VNĐ)")
    payment_proof = models.ImageField(upload_to='subscription_proofs/', null=True, blank=True, verbose_name="Ảnh biên lai chuyển khoản")
    status = models.CharField(
        max_length=20,
        choices=SubscriptionOrderStatus.choices,
        default=SubscriptionOrderStatus.PENDING,
        verbose_name="Trạng thái đơn"
    )
    rejection_reason = models.TextField(blank=True, null=True, verbose_name="Lý do từ chối")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo đơn")
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm duyệt")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_subscriptions',
        verbose_name="Người duyệt"
    )

    class Meta:
        verbose_name = "Đơn đăng ký gói phí duy trì"
        verbose_name_plural = "Danh sách đơn đăng ký gói phí"
        ordering = ['-created_at']

    def approve_order(self, admin_user) -> bool:
        """
        Tính đóng gói (Encapsulation): Ban quản trị duyệt đơn đóng tiền ->
        Tự động gia hạn thời gian hoạt động trong OwnerProfile của Chủ sân.
        """
        if self.status == SubscriptionOrderStatus.APPROVED:
            return False
        self.status = SubscriptionOrderStatus.APPROVED
        self.approved_at = timezone.now()
        self.approved_by = admin_user
        self.save()

        profile, _ = OwnerProfile.objects.get_or_create(user=self.owner)
        profile.extend_subscription(self.plan.duration_days)
        return True

    def reject_order(self, reason: str = "") -> bool:
        """Từ chối đơn đóng phí"""
        self.status = SubscriptionOrderStatus.REJECTED
        self.rejection_reason = reason
        self.save()
        return True

    def __str__(self):
        return f"[{self.order_code}] {self.owner.username} - {self.plan.name} ({self.get_status_display()})"

