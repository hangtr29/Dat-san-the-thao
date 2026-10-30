from datetime import datetime, date, time, timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from facilities.models import Facility, Court, PricingRule
from .models import Booking, BookingSlot, BookingStatus

class SlotGeneratorService:
    """
    Service tự động sinh BookingSlot theo khung giờ mở/đóng cửa
    và quy tắc định giá PricingRule của Cụm sân.
    """
    @staticmethod
    def generate_slots_for_court(court: Court, target_date: date, slot_minutes: int = 60):
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
    def lock_slots_and_create_booking(cls, user, slot_ids) -> tuple[bool, str, Booking | None]:
        """
        Khóa giữ chỗ đồng thời nhiều slot và tạo đơn đặt PENDING_BILL.
        Sử dụng transaction.atomic() và select_for_update() để loại trừ race condition.
        """
        if not slot_ids:
            return False, "Vui lòng chọn ít nhất 1 khung giờ.", None

        with transaction.atomic():
            # Khóa các hàng slot trong Database
            slots = list(BookingSlot.objects.select_for_update().filter(id__in=slot_ids))
            
            if len(slots) != len(slot_ids):
                return False, "Một số slot đã chọn không hợp lệ.", None

            now = timezone.now()
            threshold = now - timedelta(minutes=cls.LOCK_TIMEOUT_MINUTES)

            # Kiểm tra trạng thái từng slot
            for slot in slots:
                # 0. Khung giờ đã trôi qua
                if slot.is_past():
                    return False, f"Khung giờ {slot.start_time.strftime('%H:%M')} sân {slot.court.court_name} đã trôi qua.", None

                # 1. Đã được đặt và xác nhận / chờ duyệt
                if slot.booking and slot.booking.status in [BookingStatus.WAITING_APPROVAL, BookingStatus.CONFIRMED]:
                    return False, f"Khung giờ {slot.start_time.strftime('%H:%M')} sân {slot.court.court_name} đã có người đặt.", None
                
                # 2. Đang bị người khác giữ chỗ trong thời gian hiệu lực
                if slot.locked_by and slot.locked_by != user and slot.lock_time and slot.lock_time > threshold:
                    return False, f"Khung giờ {slot.start_time.strftime('%H:%M')} sân {slot.court.court_name} đang được người khác giữ chỗ.", None

            # Tính tổng tiền
            total_amount = sum(slot.price for slot in slots)

            # Tạo đơn đặt PENDING_BILL
            booking = Booking.objects.create(
                customer=user,
                total_amount=total_amount,
                status=BookingStatus.PENDING_BILL
            )

            # Cập nhật lock và liên kết slot với booking
            for slot in slots:
                slot.locked_by = user
                slot.lock_time = now
                slot.booking = booking
                slot.save()

            return True, "Khóa slot thành công! Vui lòng hoàn tất thanh toán.", booking


class CleanExpiredLocksService:
    """Dọn dẹp các đơn PENDING_BILL quá hạn 10 phút để giải phóng slot"""
    @staticmethod
    def cleanup():
        expired_time = timezone.now() - timedelta(minutes=10)
        expired_bookings = Booking.objects.filter(
            status=BookingStatus.PENDING_BILL,
            created_at__lt=expired_time
        )
        count = 0
        for b in expired_bookings:
            b.cancel_booking()
            count += 1
        return count

