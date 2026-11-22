"""
Script đồng bộ dữ liệu BookingSlot sang khung giờ 30 PHÚT.

- Tách các slot 60 phút ĐÃ CÓ BOOKING thành 2 slot 30 phút con (giữ booking, chia đều giá).
- Xóa các slot 60 phút CHƯA CÓ BOOKING.
- Sinh lại toàn bộ slot 30 phút cho mọi cụm sân trong 14 ngày tới.

Chạy:  python manage.py shell < migrate_slots_to_30min.py
"""
import os
import django
from datetime import timedelta, time as dtime
from decimal import Decimal
from collections import Counter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from bookings.models import BookingSlot
from bookings.services import SlotGeneratorService
from facilities.models import Facility

SLOT_MINUTES = 30
DAYS_AHEAD = 14


def duration_minutes(slot):
    return ((slot.end_time.hour * 60 + slot.end_time.minute)
            - (slot.start_time.hour * 60 + slot.start_time.minute))


def to_time(total_minutes):
    return dtime((total_minutes // 60) % 24, total_minutes % 60)


def split_booking_slot(slot):
    """Tách 1 slot 60 phút (có booking) thành N slot 30 phút, giữ booking, chia đều giá."""
    booking = slot.booking
    parts = duration_minutes(slot) // SLOT_MINUTES
    if parts <= 1:
        return 0

    price_each = (slot.price / parts).quantize(Decimal('1'))

    created = 0
    start_min = slot.start_time.hour * 60 + slot.start_time.minute
    for _ in range(parts):
        end_min = start_min + SLOT_MINUTES
        if end_min >= 24 * 60:
            break
        _, made = BookingSlot.objects.get_or_create(
            court=slot.court,
            date=slot.date,
            start_time=to_time(start_min),
            end_time=to_time(end_min),
            defaults={'price': price_each, 'booking': booking},
        )
        if made:
            created += 1
        start_min = end_min

    return created


def main():
    today = timezone.localdate()

    # 1. Tách slot đang CÓ booking
    booked = list(BookingSlot.objects.filter(booking__isnull=False).select_related('booking', 'court'))
    split_total = 0
    for s in booked:
        if duration_minutes(s) > SLOT_MINUTES:
            split_total += split_booking_slot(s)
    print(f'[1] Da tach {split_total} slot 30 phut tu cac slot da co booking.')

    # 2. Xoa slot > 30 phut CHUA co booking
    delete_ids = [s.id for s in BookingSlot.objects
                  .filter(booking__isnull=True).iterator()
                  if duration_minutes(s) > SLOT_MINUTES]
    deleted = 0
    if delete_ids:
        deleted = BookingSlot.objects.filter(id__in=delete_ids).delete()[0]
    print(f'[2] Da xoa {deleted} slot 60 phut chua co booking.')

    # 3. Sinh lai slot 30 phut cho 14 ngay toi
    created = 0
    for facility in Facility.objects.all():
        for court in facility.courts.filter(is_active=True):
            for i in range(DAYS_AHEAD):
                created += SlotGeneratorService.generate_slots_for_court(
                    court=court,
                    target_date=today + timedelta(days=i),
                    slot_minutes=SLOT_MINUTES,
                )
    print(f'[3] Da sinh {created} slot moi 30 phut cho {DAYS_AHEAD} ngay.')

    # 4. Bao cao
    c = Counter()
    for s in BookingSlot.objects.all():
        c[duration_minutes(s)] += 1
    print(f'[4] Phan bo duration hien tai: {dict(c)}')
    print(f'    Tong slot       : {BookingSlot.objects.count()}')
    print(f'    Slot co booking : {BookingSlot.objects.filter(booking__isnull=False).count()}')


if __name__ == '__main__':
    main()
