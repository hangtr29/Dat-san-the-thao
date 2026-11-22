import uuid
import string
import random
from datetime import timedelta
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from facilities.models import Court

class BookingStatus(models.TextChoices):
    PENDING_BILL = 'PENDING_BILL', 'Chờ tải bill thanh toán'
    WAITING_APPROVAL = 'WAITING_APPROVAL', 'Chờ chủ sân duyệt'
    CONFIRMED = 'CONFIRMED', 'Đã xác nhận đặt sân thành công'
    REJECTED = 'REJECTED', 'Đã bị từ chối'
    CANCELLED = 'CANCELLED', 'Đã hủy'

    # Đơn bị từ chối nhưng khách được phép tải lại bill (chưa mất slot)
    NEEDS_REUPLOAD = 'NEEDS_REUPLOAD', 'Cần tải lại bill thanh toán'

def generate_booking_code():
    chars = string.ascii_uppercase + string.digits
    return 'BK' + ''.join(random.choices(chars, k=8))

class Booking(models.Model):
    """
    State Machine & Encapsulation:
    Quản lý luồng chuyển đổi trạng thái đơn đặt và quy trình xét duyệt bill thanh toán.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking_code = models.CharField(
        max_length=12,
        unique=True,
        default=generate_booking_code,
        editable=False,
        db_index=True,
        verbose_name="Mã đơn đặt"
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
        verbose_name="Khách hàng"
    )
    customer_name = models.CharField(max_length=150, verbose_name="Tên khách hàng", blank=True, default="")
    customer_phone = models.CharField(max_length=20, verbose_name="Số điện thoại", blank=True, default="")
    customer_note = models.TextField(blank=True, default="", verbose_name="Ghi chú cho chủ sân")
    student_card_image = models.ImageField(
        upload_to='student_cards/%Y/%m/',
        null=True,
        blank=True,
        verbose_name="Thẻ HSSV"
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Tổng tiền (VNĐ)")
    court_amount = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=0,
        verbose_name="Tổng tiền sân (VNĐ)"
    )
    addon_amount = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=0,
        verbose_name="Tổng tiền dịch vụ (VNĐ)"
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=0,
        verbose_name="Số tiền được giảm (VNĐ)"
    )
    coupon = models.ForeignKey(
        'facilities.Coupon',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
        verbose_name="Mã giảm giá đã dùng"
    )
    coupon_code = models.CharField(max_length=30, blank=True, default='', verbose_name="Mã giảm giá (snapshot)")
    is_recurring = models.BooleanField(default=False, verbose_name="Thuộc lịch đặt cố định theo tuần")
    recurring_group_id = models.CharField(
        max_length=40,
        blank=True,
        default='',
        db_index=True,
        verbose_name="Mã nhóm lịch cố định"
    )
    recurrence_end_date = models.DateField(null=True, blank=True, verbose_name="Ngày kết thúc lịch cố định")
    payment_proof = models.ImageField(
        upload_to='payment_proofs/%Y/%m/',
        null=True,
        blank=True,
        verbose_name="Ảnh chuyển khoản (Bill)"
    )
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING_BILL,
        db_index=True,
        verbose_name="Trạng thái đơn"
    )
    reject_reason = models.TextField(blank=True, null=True, verbose_name="Lý do từ chối")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian tạo")

    class Meta:
        verbose_name = "Đơn đặt sân"
        verbose_name_plural = "Danh sách đơn đặt sân"
        ordering = ['-created_at']

    @property
    def display_customer_name(self) -> str:
        """Tên hiển thị an toàn của khách hàng (không bị lỗi khi customer là None)"""
        if self.customer_name:
            return self.customer_name
        if self.customer:
            return self.customer.get_full_name() or self.customer.username
        return "Khách vãng lai"

    @property
    def display_customer_phone(self) -> str:
        """Số điện thoại an toàn của khách hàng"""
        if self.customer_phone:
            return self.customer_phone
        if self.customer and hasattr(self.customer, 'phone_number') and self.customer.phone_number:
            return self.customer.phone_number
        return "Chưa có SĐT"

    @property
    def facility(self):
        """Cụm sân của đơn đặt (lấy từ slot đầu tiên)"""
        slot = self.slots.select_related('court__facility').first()
        return slot.court.facility if slot else None

    @property
    def court(self):
        """Sân thi đấu của đơn đặt (lấy từ slot đầu tiên)"""
        slot = self.slots.select_related('court').first()
        return slot.court if slot else None

    def upload_proof_and_submit(self, proof_image):
        """
        Tính đóng gói (Encapsulation): Khách hàng nộp ảnh bill và hệ thống
        chuyển trạng thái sang Chờ duyệt (WAITING_APPROVAL).
        """
        self.payment_proof = proof_image
        self.status = BookingStatus.WAITING_APPROVAL
        self.save()

    def reupload_proof_and_submit(self, proof_image):
        """
        Tính đóng gói (Encapsulation): Khách tải lại bill khi bị chủ sân từ chối.
        Giữ nguyên khung giờ đã giữ (không phải đặt lại từ đầu),
        chuyển trạng thái về WAITING_APPROVAL để chủ sân duyệt lại.
        """
        if self.status not in [BookingStatus.REJECTED, BookingStatus.NEEDS_REUPLOAD]:
            return False
        self.payment_proof = proof_image
        self.reject_reason = ''
        self.status = BookingStatus.WAITING_APPROVAL
        self.save()
        # Giữ lại các slot đã giữ chỗ (không release)
        for slot in self.slots.all():
            slot.booking = self
            slot.locked_by = None
            slot.locked_session = None
            slot.lock_time = None
            slot.save()
        return True

    def recalculate_totals(self):
        """
        Tính đóng gói (Encapsulation): Tính lại tổng tiền dựa trên:
        tiền sân + tiền dịch vụ bổ sung - tiền giảm giá (mã giảm giá).
        """
        court_amount = sum((s.price for s in self.slots.all()), Decimal('0'))
        addon_amount = sum((a.subtotal for a in self.addons.all()), Decimal('0'))

        discount = Decimal('0')
        if self.coupon_id and self.coupon:
            discount = Decimal(str(self.coupon.calculate_discount(court_amount + addon_amount)))

        self.court_amount = court_amount
        self.addon_amount = addon_amount
        self.discount_amount = discount
        self.total_amount = court_amount + addon_amount - discount
        self.save()
        return self.total_amount

    def get_addon_summary(self) -> str:
        """Tóm tắt dịch vụ bổ sung để hiển thị ngắn gọn"""
        names = [a.name for a in self.addons.all()]
        if not names:
            return ''
        return ', '.join(names)

    def approve_by_owner(self, owner_user) -> bool:
        """
        Tính đóng gói (Encapsulation): Chủ sân xác nhận đã nhận đủ tiền và chốt đơn (CONFIRMED).
        """
        if self.status == BookingStatus.WAITING_APPROVAL:
            self.status = BookingStatus.CONFIRMED
            self.save()
            return True
        return False

    def reject_by_owner(self, reason: str = "", allow_reupload: bool = True) -> bool:
        """
        Tính đóng gói (Encapsulation): Chủ sân từ chối đơn đặt do bill giả mạo/sai lệch.

        Nếu allow_reupload=True (mặc định): đơn chuyển sang NEEDS_REUPLOAD,
        GIỮ NGUYÊN các khung giờ đã giữ để khách chỉ cần tải lại bill
        thay vì phải đặt lại từ đầu.
        Nếu allow_reupload=False: từ chối hẳn và giải phóng toàn bộ slot.
        """
        if self.status in [BookingStatus.PENDING_BILL, BookingStatus.WAITING_APPROVAL]:
            self.reject_reason = reason
            if allow_reupload:
                self.status = BookingStatus.NEEDS_REUPLOAD
                self.save()
                # Giữ nguyên slot (chỉ bỏ khóa giữ chỗ tạm thời)
                for slot in self.slots.all():
                    slot.locked_by = None
                    slot.locked_session = None
                    slot.lock_time = None
                    slot.save()
                return True
            self.status = BookingStatus.REJECTED
            self.save()
            # Giải phóng tất cả các slot thuộc đơn này
            for slot in self.slots.all():
                slot.release_slot()
            return True
        return False

    def cancel_booking(self) -> bool:
        """Khách hàng hủy đơn hoặc hệ thống hủy khi hết thời gian chờ bill"""
        if self.status == BookingStatus.PENDING_BILL:
            self.status = BookingStatus.CANCELLED
            self.save()
            for slot in self.slots.all():
                slot.release_slot()
            return True
        return False

    def is_expired(self, timeout_minutes=10) -> bool:
        """Kiểm tra đơn PENDING_BILL có bị quá hạn thanh toán hay chưa"""
        if self.status == BookingStatus.PENDING_BILL:
            return timezone.now() > (self.created_at + timedelta(minutes=timeout_minutes))
        return False

    def __str__(self):
        return f"[{self.booking_code}] - {self.display_customer_name} ({self.get_status_display()})"

class BookingSlot(models.Model):
    """
    Quản lý nguyên tử (Atomic unit) của từng khung giờ.
    Giúp chống đặt trùng lịch (Conflict Protection & Temporary Lock).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    court = models.ForeignKey(Court, on_delete=models.CASCADE, related_name='slots', verbose_name="Sân")
    booking = models.ForeignKey(
        Booking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='slots',
        verbose_name="Đơn đặt sân"
    )
    date = models.DateField(db_index=True, verbose_name="Ngày đặt")
    start_time = models.TimeField(verbose_name="Giờ bắt đầu")
    end_time = models.TimeField(verbose_name="Giờ kết thúc")
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Giá tiền (VNĐ)")
    
    # Cơ chế Khóa giữ chỗ tạm thời (Temporary Slot Locking)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='locked_slots',
        verbose_name="Người đang giữ chỗ"
    )
    locked_session = models.CharField(max_length=64, null=True, blank=True, verbose_name="Session giữ chỗ")
    lock_time = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="Thời điểm bắt đầu giữ chỗ")

    class Meta:
        verbose_name = "Slot giờ đặt"
        verbose_name_plural = "Danh sách Slot giờ"
        constraints = [
            models.UniqueConstraint(fields=['court', 'date', 'start_time', 'end_time'], name='unique_court_slot')
        ]
        ordering = ['date', 'start_time']

    def lock_slot(self, user=None, session_key=None):
        """Khóa giữ chỗ trong 10 phút để khách thực hiện thanh toán"""
        self.locked_by = user if (user and user.is_authenticated) else None
        self.locked_session = session_key
        self.lock_time = timezone.now()
        self.save()

    def release_slot(self):
        """Giải phóng khóa giữ chỗ"""
        self.locked_by = None
        self.locked_session = None
        self.lock_time = None
        self.booking = None
        self.save()

    def is_locked(self, timeout_minutes=10) -> bool:
        """
        Kiểm tra slot có đang trong thời gian giữ chỗ hợp lệ hay không.

        LƯU Ý (đã sửa): Hàm này thuần khiết (read-only) - KHÔNG tự gỡ khóa.
        Trước đây hàm tự gọi release_slot() khi quá hạn, khiến việc đọc dữ liệu
        lại làm thay đổi dữ liệu và âm thầm gỡ slot ra khỏi đơn đang đặt.
        Việc dọn dẹp khóa hết hạn được giao cho CleanExpiredLocksService.
        """
        if not self.lock_time:
            return False
        # Còn hiệu lực nếu chưa quá thời gian giữ chỗ
        return (timezone.now() - self.lock_time) < timedelta(minutes=timeout_minutes)

    def is_past(self) -> bool:
        """Kiểm tra khung giờ đã trôi qua so với thời gian hiện tại thực tế"""
        now = timezone.localtime()
        if self.date < now.date():
            return True
        if self.date == now.date() and self.start_time <= now.time():
            return True
        return False

    @property
    def is_available(self) -> bool:
        """Slot khả dụng khi chưa trôi qua, không có booking xác nhận/chờ duyệt và không bị lock"""
        if self.is_past():
            return False
        if self.booking and self.booking.status in [
            BookingStatus.WAITING_APPROVAL,
            BookingStatus.CONFIRMED,
            BookingStatus.NEEDS_REUPLOAD,
        ]:
            return False
        return not self.is_locked()

    def __str__(self):
        return f"{self.court.court_name} | {self.date} {self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"


class BookingAddon(models.Model):
    """
    Tính đóng gói (Encapsulation): Dịch vụ bổ sung đã chọn cho một đơn đặt sân.
    Lưu snapshot tên/giá tại thời điểm đặt để chủ sân đổi giá sau này không làm thay đổi đơn cũ.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='addons',
        verbose_name="Đơn đặt sân"
    )
    service = models.ForeignKey(
        'facilities.AddonService',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='booking_addons',
        verbose_name="Dịch vụ gốc"
    )
    name = models.CharField(max_length=120, verbose_name="Tên dịch vụ (snapshot)")
    unit_price = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Đơn giá (VNĐ)")
    quantity = models.IntegerField(default=1, verbose_name="Số lượng")
    subtotal = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Thành tiền (VNĐ)")
    note = models.CharField(max_length=150, blank=True, default='', verbose_name="Ghi chú")

    class Meta:
        verbose_name = "Dịch vụ bổ sung của đơn"
        verbose_name_plural = "Danh sách dịch vụ bổ sung của đơn"
        ordering = ['name']

    def save(self, *args, **kwargs):
        """Tính đóng gói (Encapsulation): tự tính thành tiền khi lưu."""
        if not self.unit_price and self.service_id:
            self.unit_price = self.service.unit_price
        if not self.name and self.service_id:
            self.name = self.service.name
        self.subtotal = Decimal(str(self.unit_price or 0)) * (self.quantity or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} x{self.quantity} - {int(self.subtotal):,} đ"


class RecurringBooking(models.Model):
    """
    Tính đóng gói (Encapsulation): Lịch đặt sân CỐ ĐỊNH THEO TUẦN.
    Mỗi nhóm lịch (recurring_group) gồm nhiều Booking con, mỗi tuần một đơn,
    tự động sinh đến ngày kết thúc. Khi một tuần bị từ chối, các tuần sau vẫn giữ nguyên.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group_id = models.CharField(max_length=40, unique=True, verbose_name="Mã nhóm lịch")
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='recurring_bookings',
        verbose_name="Khách hàng"
    )
    facility = models.ForeignKey(
        'facilities.Facility',
        on_delete=models.CASCADE,
        related_name='recurring_bookings',
        verbose_name="Cụm sân"
    )
    court = models.ForeignKey(
        Court,
        on_delete=models.CASCADE,
        related_name='recurring_bookings',
        verbose_name="Sân thi đấu"
    )
    weekday = models.IntegerField(verbose_name="Thứ trong tuần (0=Thứ 2 ... 6=Chủ Nhật)")
    start_time = models.TimeField(verbose_name="Giờ bắt đầu")
    end_time = models.TimeField(verbose_name="Giờ kết thúc")
    start_date = models.DateField(verbose_name="Ngày bắt đầu")
    end_date = models.DateField(verbose_name="Ngày kết thúc")
    total_amount = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Tổng tiền mỗi tuần")
    is_active = models.BooleanField(default=True, verbose_name="Đang hiệu lực")

    class Meta:
        verbose_name = "Lịch đặt cố định theo tuần"
        verbose_name_plural = "Danh sách lịch đặt cố định theo tuần"
        ordering = ['-id']

    def __str__(self):
        return f"{self.court.court_name} - {self.weekday} {self.start_time.strftime('%H:%M')} đến {self.end_date}"


class Notification(models.Model):
    """
    Tính đóng gói (Encapsulation): Trung tâm thông báo nội bộ (In-App Notification).
    Dùng cho: khách nhận thông báo khi chủ sân duyệt/từ chối đơn,
    chủ sân nhận thông báo khi có đơn mới mà không cần tải lại trang.
    """
    NOTIFICATION_TYPES = [
        ('BOOKING_APPROVED', 'Đơn được duyệt'),
        ('BOOKING_REJECTED', 'Đơn bị từ chối'),
        ('BOOKING_NEW', 'Đơn đặt mới'),
        ('BOOKING_NEEDS_REUPLOAD', 'Cần tải lại bill'),
        ('BOOKING_CANCELLED', 'Đơn bị hủy'),
        ('SYSTEM', 'Thông báo hệ thống'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="Người nhận"
    )
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, default='SYSTEM', verbose_name="Loại")
    title = models.CharField(max_length=200, verbose_name="Tiêu đề")
    message = models.TextField(blank=True, default='', verbose_name="Nội dung")
    link = models.CharField(max_length=300, blank=True, default='', verbose_name="Đường dẫn")
    is_read = models.BooleanField(default=False, db_index=True, verbose_name="Đã đọc")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Thời gian")

    class Meta:
        verbose_name = "Thông báo"
        verbose_name_plural = "Danh sách thông báo"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.user.username})"
