"""
seed_facility_pricing.py
=======================
Script seed giá sân KHÁC NHAU cho từng cụm sân + dịch vụ bổ sung mặc định
(thuê vợt, thức uống) với giá riêng cho từng sân.

Vấn đề giải quyết:
- Trước đây TẤT CẢ 6 cụm sân dùng chung một bộ giá (90.000/110.000/120.000/
  130.000/150.000/160.000/190.000 đ/h) -> người dùng báo "hiện tại đang cùng
  một giá". Script này gán biểu giá riêng theo đẳng cấp & vị trí từng cụm sân.
- Bổ sung dịch vụ thuê vợt & thức uống mặc định để khách chọn ngay trong
  modal "Thêm dịch vụ" ở trang xác nhận đặt sân.

Cách chạy:
    python seed_facility_pricing.py
"""
import os
from datetime import time
from decimal import Decimal

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from facilities.models import Facility, PricingRule, AddonService  # noqa: E402


# -----------------------------------------------------------------------------
# BIỂU GIÁ RIÊNG CHO TỪNG CỤM SÂN
#   off_peak : giờ thường (mở cửa -> 17:00), ngày trong tuần
#   peak     : giờ cao điểm (17:00 -> đóng cửa), ngày trong tuần
#   weekend  : giá cả ngày cho Thứ Bảy & Chủ Nhật
# -----------------------------------------------------------------------------
PRICING_PLAN = {
    # Cụm sân lớn, đa môn (cầu lông + pickleball + bóng bàn) - trung tâm Q1
    'CLB Thể Thao Sài Gòn Star': {
        'off_peak': 150000,
        'peak': 220000,
        'weekend': 240000,
    },
    # Nhà thi đấu lớn - Q1, sân đẹp & đông khách
    'Nhà thi đấu Cầu Lông Bạch Đằng': {
        'off_peak': 165000,
        'peak': 240000,
        'weekend': 260000,
    },
    # Cụm sân cầu lông chuyên nghiệp - Q4
    'Cụm Sân Cầu Lông Thanh Đa': {
        'off_peak': 140000,
        'peak': 205000,
        'weekend': 225000,
    },
    # CLB thể thao khu vực Phú Nhuận - Q.Phú Nhuận
    'CLB Thể Thao Phú Nhuận Sky Garden': {
        'off_peak': 125000,
        'peak': 185000,
        'weekend': 200000,
    },
    # CLB Pickleball - Bình Thạnh
    'CLB Pickleball Hoa Lư': {
        'off_peak': 110000,
        'peak': 165000,
        'weekend': 180000,
    },
    # Bóng bàn & Pickleball - Quận 2 (khu dân cư, giá mềm hơn)
    'Sân Bóng Bàn & Pickleball Thảo Điền': {
        'off_peak': 95000,
        'peak': 140000,
        'weekend': 155000,
    },
    # ===== 6 CỤM SÂN HIỆN TẠI TRONG DATABASE =====
    'CLB Thể Thao Sài Gòn Star': {
        'off_peak': 150000,
        'peak': 220000,
        'weekend': 240000,
    },
    'Nhà thi đấu Cầu Lông Bạch Đằng': {
        'off_peak': 165000,
        'peak': 240000,
        'weekend': 260000,
    },
    'Cụm Sân Cầu Lông Thanh Đa': {
        'off_peak': 140000,
        'peak': 205000,
        'weekend': 225000,
    },
    'CLB Thể Thao Phú Nhuận Sky Garden': {
        'off_peak': 125000,
        'peak': 185000,
        'weekend': 200000,
    },
    'CLB Pickleball Hoa Lư': {
        'off_peak': 110000,
        'peak': 165000,
        'weekend': 180000,
    },
    # Fallback cho cụm sân mới thêm vào
    '_default': {
        'off_peak': 120000,
        'peak': 175000,
        'weekend': 190000,
    },
}

# Bảng giá dịch vụ bổ sung mặc định theo đẳng cấp cụm sân
ADDON_PLAN = {
    'premium': {
        'racket': 35000,
        'drinks': [
            ('Nước suối (Chai 500ml)', 10000),
            ('Trà xanh khô (Chai 500ml)', 12000),
            ('Nước điện giải', 18000),
            ('Cà phê đen', 20000),
            ('Trà đá chanh', 25000),
        ],
        'shuttlecock': 80000,
    },
    'standard': {
        'racket': 25000,
        'drinks': [
            ('Nước suối (Chai 500ml)', 8000),
            ('Trà xanh khô (Chai 500ml)', 10000),
            ('Nước điện giải', 15000),
            ('Cà phê đen', 15000),
            ('Trà đá chanh', 20000),
        ],
        'shuttlecock': 65000,
    },
    'budget': {
        'racket': 20000,
        'drinks': [
            ('Nước suối (Chai 500ml)', 6000),
            ('Trà xanh khô (Chai 500ml)', 8000),
            ('Nước điện giải', 12000),
            ('Cà phê đen', 12000),
            ('Trà đá chanh', 15000),
        ],
        'shuttlecock': 55000,
    },
}

# Phân loại đẳng cấp của từng cụm sân
FACILITY_TIER = {
    'CLB Thể Thao Sài Gòn Star': 'premium',
    'Nhà thi đấu Cầu Lông Bạch Đằng': 'premium',
    'Cụm Sân Cầu Lông Thanh Đa': 'standard',
    'CLB Thể Thao Phú Nhuận Sky Garden': 'standard',
    'CLB Pickleball Hoa Lư': 'standard',
    'Sân Bóng Bàn & Pickleball Thảo Điền': 'budget',
}


def get_pricing_plan(facility):
    """Lấy bộ giá theo tên cụm sân, fallback về giá mặc định."""
    return PRICING_PLAN.get(facility.name.strip(), PRICING_PLAN['_default'])


def get_tier(facility):
    """Xác định đẳng cấp của cụm sân để áp bảng giá dịch vụ."""
    return FACILITY_TIER.get(facility.name.strip(), 'standard')


def apply_pricing(facility, plan):
    """
    Xoá PricingRule cũ (đang dùng chung giá) rồi tạo lại theo bảng giá riêng.
    Cấu trúc mỗi ngày:
      - Ngày trong tuần: open->17:00 (off_peak) + 17:00->close (peak)
      - Cuối tuần (T7, CN): open->close (weekend, áp dụng cả ngày)
    """
    facility.pricing_rules.all().delete()

    open_time = facility.open_time or time(6, 0)
    close_time = facility.close_time or time(22, 0)
    peak_start = time(17, 0)

    # Bảo đảm peak_start nằm giữa open & close
    if not (open_time < peak_start < close_time):
        peak_start = open_time

    created = 0
    for day in range(7):
        is_weekend = day in (5, 6)  # 5 = Thứ Bảy, 6 = Chủ Nhật

        if is_weekend:
            PricingRule.objects.create(
                facility=facility,
                day_of_week=day,
                start_time=open_time,
                end_time=close_time,
                price_per_hour=Decimal(plan['weekend']),
            )
            created += 1
            continue

        if peak_start > open_time:
            PricingRule.objects.create(
                facility=facility,
                day_of_week=day,
                start_time=open_time,
                end_time=peak_start,
                price_per_hour=Decimal(plan['off_peak']),
            )
            created += 1

        if close_time > peak_start:
            PricingRule.objects.create(
                facility=facility,
                day_of_week=day,
                start_time=peak_start,
                end_time=close_time,
                price_per_hour=Decimal(plan['peak']),
            )
            created += 1

    return created


def apply_addons(facility, tier):
    """
    Tạo dịch vụ bổ sung mặc định cho cụm sân (nếu chưa có).
    KHÔNG xoá các dịch vụ chủ sân đã tự tạo/sửa trước đó.
    """
    plan = ADDON_PLAN[tier]
    created = 0

    # 1. Thuê vợt
    if not facility.addon_services.filter(name__icontains='vợt').exists():
        AddonService.objects.create(
            facility=facility,
            name='Thuê vợt',
            description='Vợt tiêu chuẩn dùng cho buổi tập, đã căng sẵn dây.',
            category='EQUIPMENT',
            unit_type='PER_PERSON',
            unit_price=Decimal(plan['racket']),
            icon='fa-table-tennis',
            is_active=True,
            sort_order=1,
        )
        created += 1

    # 2. Thuê cầu lông (chỉ cho cụm sân có môn cầu lông)
    has_badminton = facility.courts.filter(category__name__icontains='cầu lông').exists()
    if has_badminton:
        if not facility.addon_services.filter(name__icontains='cầu lông').exists():
            AddonService.objects.create(
                facility=facility,
                name='Thuê cầu lông (tube)',
                description='1 tube cầu lông dùng cho cả buổi tập.',
                category='EQUIPMENT',
                unit_type='PER_BOOKING',
                unit_price=Decimal(plan['shuttlecock']),
                icon='fa-feather-pointed',
                is_active=True,
                sort_order=2,
            )
            created += 1

    # 3. Thức uống
    sort_order = 10
    for drink_name, price in plan['drinks']:
        if facility.addon_services.filter(name__iexact=drink_name).exists():
            continue
        AddonService.objects.create(
            facility=facility,
            name=drink_name,
            description='Nước uống phục vụ tại quầy.',
            category='DRINK',
            unit_type='PER_ITEM',
            unit_price=Decimal(price),
            icon='fa-bottle-water',
            is_active=True,
            sort_order=sort_order,
        )
        sort_order += 1
        created += 1

    return created


def main():
    facilities = list(Facility.objects.all().order_by('name'))
    if not facilities:
        print("⚠️  Chưa có cụm sân nào trong database. Hãy chạy seed_data.py trước.")
        return

    print(f"📦 Bắt đầu seed giá & dịch vụ cho {len(facilities)} cụm sân...\n")

    for facility in facilities:
        plan = get_pricing_plan(facility)
        tier = get_tier(facility)

        rules = apply_pricing(facility, plan)
        addons = apply_addons(facility, tier)

        print(f"✅ {facility.name}")
        print(f"   • Biểu giá: {rules} khung "
              f"(Thường {plan['off_peak']:,}đ/h | Cao điểm {plan['peak']:,}đ/h "
              f"| Cuối tuần {plan['weekend']:,}đ/h)")
        print(f"   • Dịch vụ bổ sung: +{addons} mục (đẳng cấp: {tier})")
        print()

    print("🎉 Hoàn tất! Mỗi cụm sân giờ có biểu giá riêng và dịch vụ thuê vợt/thức uống riêng.")
    print("   → Chủ sân sửa tại: /bookings/owner/services/")
    print("   → Khách chọn dịch vụ tại: /bookings/confirm/<mã_đơn>/")


if __name__ == '__main__':
    main()
