"""
Dịch vụ nghiệp vụ (Service Layer) cho các tính năng mới:
1. Quản lý dịch vụ bổ sung (thuê vợt, thức uống) theo từng cụm sân.
2. Áp dụng mã giảm giá / khuyến mãi.
3. Đặt lịch cố định theo tuần (Recurring booking).
4. Trung tâm thông báo nội bộ (Notification).
"""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from .models import (
    Booking, BookingAddon, BookingSlot, BookingStatus,
    Notification, RecurringBooking,
)
from facilities.models import AddonService, Coupon, Facility


class AddonServiceService:
    """
    Tính đóng gói (Encapsulation): Nghiệp vụ dịch vụ bổ sung.
    """

    @staticmethod
    def get_services_for_facility(facility):
        """Danh sách dịch vụ đang cung cấp, chia theo nhóm cho giao diện"""
        if not facility:
            return {'equipment': [], 'drink': [], 'food': [], 'other': []}
        services = facility.addon_services.filter(is_active=True)
        grouped = {'equipment': [], 'drink': [], 'food': [], 'other': []}
        key_map = {
            'EQUIPMENT': 'equipment',
            'DRINK': 'drink',
            'FOOD': 'food',
            'OTHER': 'other',
        }
        for svc in services:
            grouped[key_map.get(svc.category, 'other')].append(svc)
        return grouped

    @staticmethod
    def apply_to_booking(booking, selections, hours=1.0, people=1):
        """
        Áp dụng các dịch vụ khách chọn vào đơn đặt sân.
        selections: dict {service_id: quantity}
        Trả về (total_addon_amount, list_addon_objects)
        """
        booking.addons.all().delete()
        total = Decimal('0')
        created = []
        for service_id, qty in (selections or {}).items():
            try:
                qty = int(qty)
            except (TypeError, ValueError):
                qty = 0
            if qty <= 0:
                continue
            svc = AddonService.objects.filter(id=service_id, facility=booking.facility, is_active=True).first()
            if not svc:
                continue
            price = svc.calculate_price(quantity=qty, hours=hours, people=people)
            addon = BookingAddon.objects.create(
                booking=booking,
                service=svc,
                name=svc.name,
                unit_price=svc.unit_price,
                quantity=qty,
                subtotal=price,
            )
            total += Decimal(price)
            created.append(addon)
        return total, created

    @staticmethod
    def booking_hours(booking):
        """Tính tổng số giờ của đơn (dùng cho dịch vụ tính theo giờ)"""
        total_minutes = 0
        for s in booking.slots.all():
            start = s.start_time.hour * 60 + s.start_time.minute
            end = s.end_time.hour * 60 + s.end_time.minute
            total_minutes += max(0, end - start)
        return round(total_minutes / 60.0, 2) or 1

    @staticmethod
    def booking_people(booking):
        """Ước lượng số người chơi (mặc định 2 người / sân)"""
        try:
            court_count = booking.slots.values('court_id').distinct().count()
        except Exception:
            court_count = 1
        return max(2, court_count * 2)


class CouponService:
    """
    Tính đóng gói (Encapsulation): Nghiệp vụ mã giảm giá & khuyến mãi.
    """

    @staticmethod
    def validate(code, order_value, facility=None):
        """
        Kiểm tra mã giảm giá. Trả về (coupon hoặc None, thông báo lỗi/thành công)
        """
        code = (code or '').strip().upper()
        if not code:
            return None, ''
        coupon = Coupon.objects.filter(code__iexact=code).first()
        if not coupon:
            return None, "Mã giảm giá không tồn tại hoặc đã hết hạn sử dụng."
        ok, msg = coupon.is_valid_for(order_value, facility)
        if not ok:
            return None, msg
        return coupon, f"Áp dụng mã {coupon.code}: giảm {coupon.calculate_discount(order_value):,} đ."

    @staticmethod
    def apply(booking, code, facility=None):
        """Áp dụng mã giảm giá cho đơn. Trả về (thành công, thông báo)"""
        coupon, msg = CouponService.validate(code, booking.total_amount, facility)
        if not coupon:
            booking.coupon = None
            booking.coupon_code = ''
            return False, msg
        booking.coupon = coupon
        booking.coupon_code = coupon.code
        coupon.used_count += 1
        coupon.save(update_fields=['used_count'])
        return True, msg


class RecurringBookingService:
    """
    Tính đóng gói (Encapsulation): Đặt lịch cố định theo tuần.
    """

    @staticmethod
    def create_weekly_series(user, facility, court, start_date, end_date,
                             start_time, end_time, weekday=None, note=''):
        """
        Tạo chuỗi đơn đặt cố định hàng tuần.
        Trả về (danh sách booking, thông báo lỗi)
        """
        from bookings.services import BookingEngineService

        if end_date < start_date:
            return [], "Ngày kết thúc phải sau ngày bắt đầu."

        if weekday is None:
            weekday = start_date.weekday()

        # Giới hạn tối đa 12 tuần để tránh tạo quá nhiều đơn
        max_weeks = 12
        group_id = f"REC{uuid.uuid4().hex[:12].upper()}"
        bookings = []
        current = start_date
        weeks_created = 0

        while current <= end_date and weeks_created < max_weeks:
            if current.weekday() == weekday:
                slot = BookingSlot.objects.filter(
                    court=court, date=current, start_time=start_time, end_time=end_time
                ).first()
                if not slot:
                    # Tự sinh slot nếu chưa có
                    from bookings.services import SlotGeneratorService
                    SlotGeneratorService.generate_slots_for_court(court, current)
                    slot = BookingSlot.objects.filter(
                        court=court, date=current, start_time=start_time, end_time=end_time
                    ).first()

                if slot is None or slot.booking is not None:
                    current += timedelta(days=1)
                    continue

                booking = Booking.objects.create(
                    customer=user if (user and user.is_authenticated) else None,
                    customer_name=(user.get_full_name() or user.username) if (user and user.is_authenticated) else '',
                    customer_phone=(getattr(user, 'phone', '') or '') if (user and user.is_authenticated) else '',
                    customer_note=note,
                    total_amount=slot.price,
                    court_amount=slot.price,
                    status=BookingStatus.PENDING_BILL,
                    is_recurring=True,
                    recurring_group_id=group_id,
                    recurrence_end_date=end_date,
                )
                slot.booking = booking
                slot.locked_by = None
                slot.locked_session = None
                slot.lock_time = None
                slot.save()
                bookings.append(booking)
                weeks_created += 1
            current += timedelta(days=1)

        if not bookings:
            return [], "Không có tuần nào phù hợp còn trống sân. Vui lòng chọn lịch khác."

        RecurringBooking.objects.create(
            group_id=group_id,
            customer=user if (user and user.is_authenticated) else None,
            facility=facility,
            court=court,
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
            start_date=start_date,
            end_date=end_date,
            total_amount=bookings[0].total_amount,
        )
        return bookings, f"Đã tạo {len(bookings)} đơn cố định theo tuần."

    @staticmethod
    def get_user_series(user):
        """Danh sách nhóm lịch cố định của khách"""
        if not (user and user.is_authenticated):
            return []
        return (
            RecurringBooking.objects.filter(customer=user, is_active=True)
            .select_related('facility', 'court')
            .order_by('-id')
        )


class NotificationService:
    """
    Tính đóng gói (Encapsulation): Trung tâm thông báo nội bộ.
    """

    @staticmethod
    def notify(user, notification_type, title, message='', link=''):
        """Tạo thông báo cho người dùng (bỏ qua nếu user là None)"""
        if not user or not getattr(user, 'pk', None):
            return None
        return Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
        )

    @staticmethod
    def notify_booking_status(booking, status):
        """Gửi thông báo cho khách khi trạng thái đơn thay đổi"""
        customer = booking.customer
        if not customer:
            return None
        detail_url = f"/bookings/detail/{booking.booking_code}/"
        if status == BookingStatus.CONFIRMED:
            return NotificationService.notify(
                customer, 'BOOKING_APPROVED',
                f"Đơn #{booking.booking_code} đã được duyệt",
                "Chủ sân đã xác nhận đơn đặt của bạn. Hẹn gặp bạn tại sân!",
                detail_url,
            )
        if status == BookingStatus.NEEDS_REUPLOAD:
            return NotificationService.notify(
                customer, 'BOOKING_NEEDS_REUPLOAD',
                f"Đơn #{booking.booking_code} cần tải lại bill",
                f"Bill bị từ chối: {booking.reject_reason or ''}. Bạn có thể tải lại bill mà không cần đặt lại.",
                detail_url,
            )
        if status == BookingStatus.REJECTED:
            return NotificationService.notify(
                customer, 'BOOKING_REJECTED',
                f"Đơn #{booking.booking_code} bị từ chối",
                booking.reject_reason or "Chủ sân đã từ chối đơn đặt của bạn.",
                detail_url,
            )
        if status == BookingStatus.CANCELLED:
            return NotificationService.notify(
                customer, 'BOOKING_CANCELLED',
                f"Đơn #{booking.booking_code} đã hủy",
                "Đơn đặt của bạn đã được hủy.",
                detail_url,
            )
        return None

    @staticmethod
    def notify_owner_new_booking(booking):
        """Thông báo cho chủ sân khi có đơn mới"""
        slots = booking.slots.select_related('court__facility').all()
        if not slots:
            return None
        facility = slots.first().court.facility
        owner = facility.owner
        return NotificationService.notify(
            owner, 'BOOKING_NEW',
            f"Đơn mới #{booking.booking_code}",
            f"{booking.display_customer_name} vừa đặt {slots.first().court.court_name} "
            f"tại {facility.name}.",
            "/bookings/dashboard/?tab=orders&status=WAITING_APPROVAL",
        )

    @staticmethod
    def notify_owner_booking_cancelled(booking, reason=""):
        """
        Thông báo cho CHỦ SÂN khi khách hàng hủy đơn đặt.
        Trước đây khách hủy đơn thì chủ sân không hề hay biết -> mất lịch âm thầm.
        """
        slots = booking.slots.select_related('court__facility').all()
        if not slots:
            return None
        facility = slots.first().court.facility
        owner = facility.owner
        extra = f" Lý do: {reason}" if reason else ""
        return NotificationService.notify(
            owner, 'BOOKING_CANCELLED',
            f"Khách hủy đơn #{booking.booking_code}",
            f"{booking.display_customer_name} đã hủy đơn đặt "
            f"{slots.first().court.court_name} tại {facility.name}.{extra}",
            "/bookings/dashboard/?tab=orders&status=ALL",
        )

    @staticmethod
    def notify_customer_owner_reply(review):
        """
        Thông báo cho KHÁCH HÀNG khi chủ sân phản hồi đánh giá của họ.
        Đóng gói logic thông báo 2 chiều trong hệ thống đánh giá.
        """
        customer = review.user
        if not customer:
            return None
        facility_name = review.facility.name
        return NotificationService.notify(
            customer, 'SYSTEM',
            "Chủ sân đã phản hồi đánh giá của bạn",
            f"{facility_name} đã trả lời đánh giá {review.rating}★ của bạn: "
            f"\"{(review.owner_reply or '')[:180]}\"",
            "/bookings/history/",
        )

    @staticmethod
    def notify_owner_new_review(review):
        """
        Thông báo cho CHỦ SÂN khi có đánh giá mới từ khách hàng.
        """
        owner = review.facility.owner
        stars = "★" * int(review.rating or 5)
        return NotificationService.notify(
            owner, 'SYSTEM',
            f"Đánh giá mới {stars} tại {review.facility.name}",
            f"{review.reviewer_name} vừa đánh giá {review.rating}★: "
            f"\"{(review.comment or '')[:180]}\"",
            "/bookings/dashboard/?tab=reviews",
        )

    @staticmethod
    def unread_count(user):
        if not (user and user.is_authenticated):
            return 0
        return Notification.objects.filter(user=user, is_read=False).count()

    @staticmethod
    def get_unread(user, limit=10):
        if not (user and user.is_authenticated):
            return []
        return list(
            Notification.objects.filter(user=user, is_read=False)[:limit]
        )
