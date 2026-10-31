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

    def upload_proof_and_submit(self, proof_image):
        """
        Tính đóng gói (Encapsulation): Khách hàng nộp ảnh bill và hệ thống
        chuyển trạng thái sang Chờ duyệt (WAITING_APPROVAL).
        """
        self.payment_proof = proof_image
        self.status = BookingStatus.WAITING_APPROVAL
        self.save()

    def approve_by_owner(self, owner_user) -> bool:
        """
        Tính đóng gói (Encapsulation): Chủ sân xác nhận đã nhận đủ tiền và chốt đơn (CONFIRMED).
        """
        if self.status == BookingStatus.WAITING_APPROVAL:
            self.status = BookingStatus.CONFIRMED
            self.save()
            return True
        return False

    def reject_by_owner(self, reason: str = "") -> bool:
        """
        Tính đóng gói (Encapsulation): Chủ sân từ chối đơn đặt do bill giả mạo/sai lệch,
        tự động giải phóng các slot đang giữ chỗ.
        """
        if self.status in [BookingStatus.PENDING_BILL, BookingStatus.WAITING_APPROVAL]:
            self.status = BookingStatus.REJECTED
            self.reject_reason = reason
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
        name = self.customer_name or (self.customer.get_full_name() or self.customer.username if self.customer else "Khách vãng lai")
        return f"[{self.booking_code}] - {name} ({self.get_status_display()})"

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
        """Kiểm tra slot có đang trong thời gian giữ chỗ hợp lệ hay không"""
        if not self.lock_time:
            return False
        # Nếu đã quá 10 phút thì xem như hết hạn lock
        is_active_lock = (timezone.now() - self.lock_time) < timedelta(minutes=timeout_minutes)
        if not is_active_lock:
            # Tự dọn dẹp nếu đã quá hạn mà chưa gắn vào đơn thành công
            if self.booking is None or self.booking.status == BookingStatus.PENDING_BILL:
                self.release_slot()
                return False
        return is_active_lock

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
        if self.booking and self.booking.status in [BookingStatus.WAITING_APPROVAL, BookingStatus.CONFIRMED]:
            return False
        return not self.is_locked()

    def __str__(self):
        return f"{self.court.court_name} | {self.date} {self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
