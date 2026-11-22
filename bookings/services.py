from datetime import datetime, date, time, timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from facilities.models import Facility, Court, PricingRule, FacilityStatus
from .models import Booking, BookingSlot, BookingStatus

class SlotGeneratorService:
    """
    Service tự động sinh BookingSlot theo khung giờ mở/đóng cửa
    và quy tắc định giá PricingRule của Cụm Sân.

    Mặc định chia khung giờ 30 PHÚT (nửa giờ) để khách có thể đặt linh hoạt:
    ví dụ khung 06:00-22:00 sẽ sinh các slot 06:00-06:30, 06:30-07:00, ...
    Giá mỗi slot được PricingRule.calculate_price() tính theo đúng thời lượng
    nên slot 30 phút tự động bằng 1/2 giá giờ của khung giờ đó.
    """

    # Khung giờ chuẩn (phút) dùng để chia lịch
    DEFAULT_SLOT_MINUTES = 30

    @staticmethod
    def generate_slots_for_court(court: Court, target_date: date,
                                 slot_minutes: int = DEFAULT_SLOT_MINUTES):
        """Sinh các slot giờ cho 1 sân cụ thể trong 1 ngày"""
        facility = court.facility
        day_of_week = target_date.weekday() # 0 = Thứ 2, 6 = Chủ nhật

        # Lấy quy tắc giá phù hợp cho ngày này
        pricing_rule = facility.pricing_rules.filter(day_of_week=day_of_week).first()
        default_price = Decimal('100000') # Mặc định 100k nếu chưa set

        start_dt = datetime.combine(target_date, facility.open_time)
        end_dt = datetime.combine(target_date, facility.close_time)

        current_dt = start_dt
        created_count = 0

        while current_dt + timedelta(minutes=slot_minutes) <= end_dt:
            slot_start = current_dt.time()
            slot_end = (current_dt + timedelta(minutes=slot_minutes)).time()

            # Tính giá slot
            slot_price = default_price
            if pricing_rule:
                slot_price = pricing_rule.calculate_price(slot_start, slot_end)

            # Tạo slot nếu chưa tồn tại
            slot, created = BookingSlot.objects.get_or_create(
                court=court,
                date=target_date,
                start_time=slot_start,
                end_time=slot_end,
                defaults={'price': slot_price}
            )
            if created:
                created_count += 1

            current_dt += timedelta(minutes=slot_minutes)

        return created_count

    @classmethod
    def generate_slots_for_facility(cls, facility: Facility, target_date: date):
        """Sinh slot cho tất cả các sân trong cụm sân"""
        total = 0
        for court in facility.courts.filter(is_active=True):
            total += cls.generate_slots_for_court(court, target_date)
        return total


class BookingEngineService:
    """
    Core Booking Engine:
    Xử lý kiểm tra trùng lịch (Concurrency Lock) và giữ chỗ nguyên tử (Atomic Lock).
    """
    LOCK_TIMEOUT_MINUTES = 10

    @classmethod
    def lock_slots_and_create_booking(cls, user=None, slot_ids=None, session_key=None, customer_name="", customer_phone="") -> tuple[bool, str, Booking | None]:
        """
        Khóa giữ chỗ đồng thời nhiều slot và tạo đơn đặt PENDING_BILL (Hỗ trợ cả khách vãng lai không cần đăng nhập).
        Sử dụng transaction.atomic() và select_for_update() để loại trừ race condition.
        """
        if not slot_ids:
            return False, "Vui lòng chọn ít nhất 1 khung giờ.", None

        # Chuẩn hoá & lọc UUID hợp lệ (chống ValidationError 500 khi nhận sai định dạng)
        import uuid as _uuid
        clean_ids = []
        for raw in slot_ids:
            try:
                clean_ids.append(str(_uuid.UUID(str(raw).strip())))
            except (ValueError, AttributeError, TypeError):
                continue
        if not clean_ids:
            return False, "Khung giờ không hợp lệ. Vui lòng chọn lại trên bảng lịch.", None
        slot_ids = clean_ids

        with transaction.atomic():
            # Khóa các hàng slot trong Database
            slots = list(BookingSlot.objects.select_for_update().filter(id__in=slot_ids))

            if len(slots) != len(slot_ids):
                return False, "Một số slot đã chọn không hợp lệ.", None

            now = timezone.now()
            threshold = now - timedelta(minutes=cls.LOCK_TIMEOUT_MINUTES)

            is_auth = (user and user.is_authenticated)

            # Kiểm tra trạng thái từng slot
            for slot in slots:
                # 0. Khung giờ đã trôi qua
                if slot.is_past():
                    return False, f"Khung giờ {slot.start_time.strftime('%H:%M')} sân {slot.court.court_name} đã trôi qua.", None

                # 1. Đã được đặt và xác nhận / chờ duyệt
                if slot.booking and slot.booking.status in [BookingStatus.WAITING_APPROVAL, BookingStatus.CONFIRMED]:
                    return False, f"Khung giờ {slot.start_time.strftime('%H:%M')} sân {slot.court.court_name} đã có người đặt.", None
                
                # 2. Đang bị người khác giữ chỗ trong thời gian hiệu lực (10 phút)
                if slot.lock_time and slot.lock_time > threshold:
                    if is_auth and slot.locked_by and slot.locked_by != user:
                        return False, f"Khung giờ {slot.start_time.strftime('%H:%M')} sân {slot.court.court_name} đang được người khác giữ chỗ.", None
                    if not is_auth and slot.locked_session and session_key and slot.locked_session != session_key:
                        return False, f"Khung giờ {slot.start_time.strftime('%H:%M')} sân {slot.court.court_name} đang được người khác giữ chỗ.", None

            # 3. Kiểm tra tất cả slot phải thuộc CÙNG MỘT cụm sân
            # (nếu không, mã QR thanh toán sẽ chỉ chuyển tiền về 1 chủ sân duy nhất)
            facility_ids = {slot.court.facility_id for slot in slots}
            if len(facility_ids) > 1:
                facility_names = ', '.join(
                    Facility.objects.filter(id__in=facility_ids).values_list('name', flat=True)
                )
                return False, (
                    f"Không thể đặt khung giờ từ nhiều cụm sân khác nhau trong cùng một đơn "
                    f"({facility_names}). Vui lòng chỉ chọn khung giờ của một cụm sân."
                ), None

            # 3.1 Chốt chặn cuối cùng: cụm sân phải được Ban quản trị DUYỆT và đang hoạt động
            # -> ngăn chặn việc đặt lịch vào cụm sân còn chờ duyệt / bị tạm ngưng
            not_published = Facility.objects.filter(
                id__in=facility_ids
            ).exclude(
                status=FacilityStatus.ACTIVE,
                active_status=True,
                is_verified=True,
            ).values_list('name', flat=True)
            if not_published:
                return False, (
                    f"Cụm sân '{', '.join(not_published)}' hiện không nhận đặt lịch "
                    "(chờ duyệt hoặc đã tạm ngưng). Vui lòng chọn cụm sân khác."
                ), None

            # Tính tổng tiền
            total_amount = sum(slot.price for slot in slots)

            # Tạo đơn đặt PENDING_BILL
            booking_user = user if is_auth else None
            initial_name = customer_name or (user.get_full_name() or user.username if is_auth else "")
            initial_phone = customer_phone or (getattr(user, 'phone_number', '') if is_auth else "")

            booking = Booking.objects.create(
                customer=booking_user,
                customer_name=initial_name,
                customer_phone=initial_phone,
                total_amount=total_amount,
                status=BookingStatus.PENDING_BILL
            )

            # Cập nhật lock và liên kết slot với booking
            for slot in slots:
                slot.locked_by = booking_user
                slot.locked_session = session_key
                slot.lock_time = now
                slot.booking = booking
                slot.save()

            return True, "Khóa slot thành công! Vui lòng hoàn tất thông tin đặt sân.", booking


class CleanExpiredLocksService:
    """Dọn dẹp các đơn PENDING_BILL quá hạn 10 phút để giải phóng slot"""
    @classmethod
    def cleanup(cls):
        """
        Dọn dẹp các đơn PENDING_BILL quá hạn 10 phút để giải phóng slot.
        Việc dọn dẹp giờ khóa hết hạn (lock_time quá hạn) cũng nằm ở đây,
        để hàm is_locked() của Model giữ được tính thuần khiết (read-only).
        """
        expired_time = timezone.now() - timedelta(minutes=10)

        # 1. Giải phóng các slot bị khoá quá hạn mà KHÔNG gắn vào đơn nào.
        #    (Slot đã gắn đơn PENDING_BILL sẽ được xử lý ở bước 2 qua cancel_booking)
        BookingSlot.objects.filter(
            lock_time__lt=expired_time,
            booking__isnull=True,
        ).update(
            locked_by=None,
            locked_session=None,
            lock_time=None,
        )

        # 2. Hủy các đơn PENDING_BILL quá hạn (giải phóng toàn bộ slot của đơn)
        expired_bookings = Booking.objects.filter(
            status=BookingStatus.PENDING_BILL,
            created_at__lt=expired_time
        )
        count = 0
        for b in expired_bookings:
            b.cancel_booking()
            count += 1
        return count

