"""
SEED: Biểu giá khác nhau cho từng cụm sân + Dịch vụ bổ sung mặc định.

Mục tiêu:
1. Mỗi cụm sân có BẢNG GIÁ RIÊNG (không còn dùng chung một giá cho tất cả).
   - Giá theo khung giờ: Sáng / Chiều / Tối / Cuối tuần
2. Mỗi cụm sân có DỊCH VỤ BỔ SUNG riêng:
   - Thuê vợt (các loại vợt)
   - Thức uống (nước, trà, cà phê, nước tăng cường...)
3. Thêm mô tả & điểm nổi bật cho cụm sân.

Cách chạy:  python seed_pricing_addons.py
"""
import os
import django
from datetime import time
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from facilities.models import (  # noqa: E402
    Facility, PricingRule, AddonService, SportCategory, Court,
)


# ---------------------------------------------------------------------------
# 1. BẢNG GIÁ RIÊNG CHO TỪNG CỤM SÂN
#    Cấu trúc: tên sân -> [(mô tả khung giờ, giờ bắt đầu, giờ kết thúc, giá/giờ)]
#    Thứ 2 -> Thứ 6 dùng giá ngày thường, Thứ 7 & CN dùng giá cuối tuần.
# ---------------------------------------------------------------------------
PRICING_PLANS = {
    'Cụm Sân Pickleball Thanh Đa': {
        'description': (
            "Cụm sân Pickleball tiêu chuẩn quốc tế tại Thanh Đa, TP.HCM với 9 sân trong nhà & ngoài trời. "
            "Sàn chống trượt thếp hạng chuyên nghiệp, hệ thống đèn LED tiết kiệm điện, "
            "không gian thoáng mát và có bãi giữ xe rộng. Phù hợp cho cả tập luyện lẫn thi đấu giao hữu."
        ),
        'highlights': [
            "9 sân tiêu chuẩn (7 trong nhà, 2 ngoài trời)",
            "Sàn PVC chống trượt đạt chuẩn",
            "Đèn LED 1500lux không chói mắt",
            "Bãi xe máy & ô tô riêng",
            "Có thuê vợt & nước uống tại chỗ",
        ],
        'rackets': [
            ("Vợt Pickleball nhựa Tiêu chuẩn", 45000, "fa-table-tennis"),
            ("Vợt Pickleball carbon cao cấp", 120000, "fa-table-tennis"),
            ("Vợt gỗ (gỗ tự nhiên)", 90000, "fa-table-tennis"),
        ],
        'drinks': [
            ("Nước suối (Chai 500ml)", 15000, "fa-bottle-water"),
            ("Nước khoáng Lavie", 20000, "fa-bottle-water"),
            ("Trà xanh Không Độ 0 đ", 20000, "fa-mug-hot"),
            ("Sting Vàng (250ml)", 22000, "fa-bolt"),
            ("Cà phê đen sữa (ly)", 25000, "fa-mug-saucer"),
        ],
        'weekday': [('05:00 - 09:00', time(5, 0), time(9, 0), 90000),
                    ('09:00 - 17:00', time(9, 0), time(17, 0), 120000),
                    ('17:00 - 21:00', time(17, 0), time(21, 0), 160000),
                    ('21:00 - 23:30', time(21, 0), time(23, 30), 110000)],
        'weekend': [('05:00 - 09:00', time(5, 0), time(9, 0), 110000),
                    ('09:00 - 17:00', time(9, 0), time(17, 0), 150000),
                    ('17:00 - 21:00', time(17, 0), time(21, 0), 190000),
                    ('21:00 - 23:30', time(21, 0), time(23, 30), 130000)],
    },
    'Sân Cầu Lông Trịnh Đình': {
        'description': (
            "Sân cầu lông chất lượng cao tại Trịnh Đình, Hà Nội với 6 sân thảm Enlio tiêu chuẩn. "
            "Trần cao thoáng, ánh sáng đèn chuyên dụng không chói, khán đài đặt kín góc và căng tin phục vụ nước."
        ),
        'highlights': [
            "6 sàn thảm Enlio chuyên dụng",
            "Ánh sáng chống chói mắt",
            "Không gian yên tĩnh, điều hòa thông gió",
            "Có căng tin & chỗ để giày",
        ],
        'rackets': [
            ("Vợt cầu lông Yonex Nanostring", 180000, "fa-table-tennis"),
            ("Vợt cầu lông liên hợp (Lining)", 220000, "fa-table-tennis"),
            ("Vợt cầu lông cho thuê (lướt tạp)", 80000, "fa-table-tennis"),
        ],
        'drinks': [
            ("Nước suối (Chai 500ml)", 12000, "fa-bottle-water"),
            ("Nước khoáng Aquafina", 15000, "fa-bottle-water"),
            ("Trà đá ly (Trà xanh)", 15000, "fa-mug-hot"),
            ("Cà phê đen (ly)", 18000, "fa-mug-saucer"),
            ("Bia Lon 330ml", 25000, "fa-beer-mug-empty"),
            ("Nước tăng cường Red Bull", 25000, "fa-bolt"),
        ],
        'weekday': [('05:00 - 09:00', time(5, 0), time(9, 0), 100000),
                    ('09:00 - 17:00', time(9, 0), time(17, 0), 140000),
                    ('17:00 - 21:00', time(17, 0), time(21, 0), 200000),
                    ('21:00 - 23:30', time(21, 0), time(23, 30), 130000)],
        'weekend': [('05:00 - 09:00', time(5, 0), time(9, 0), 120000),
                    ('09:00 - 17:00', time(9, 0), time(17, 0), 170000),
                    ('17:00 - 21:00', time(17, 0), time(21, 0), 220000),
                    ('21:00 - 23:30', time(21, 0), time(23, 30), 150000)],
    },
    'Cụm Sân Bóng Bàn Đại học Bách Khoa': {
        'description': (
            "Cụm sân bóng bàn 12 bàn tại Đại học Bách Khoa, TP.HCM. Sàn thảm ITTF chuyên dụng, "
            "vành bàn nhựa chịu lực cao, rèm chắn gió và bóng đèn LED chuyên dụng cho thi đấu. "
            "Phù hợp cho luyện tập hằng ngày, học lớp và giải đấu giao hữu."
        ),
        'highlights': [
            "12 bàn thảm ITTF chuyên dụng",
            "Vành bàn chịu lực, bóng LED chuyên dụng",
            "Rèm chắn gió & bụi",
            "Có bảng điện tử đếm số",
        ],
        'rackets': [
            ("Vợt bóng bàn phủ (cầu tay)", 60000, "fa-table-tennis"),
            ("Vợt bóng bàn gỗ (STIGA)", 180000, "fa-table-tennis"),
            ("Vợt bóng bàn cao cấp (Butterfly)", 320000, "fa-table-tennis"),
            ("Bóng tập luyện (hộp 3 quả)", 45000, "fa-futbol"),
        ],
        'drinks': [
            ("Nước suối (Chai 500ml)", 10000, "fa-bottle-water"),
            ("Nước khoáng Aquafina", 12000, "fa-bottle-water"),
            ("Trà xanh Không Độ 0 đ", 15000, "fa-mug-hot"),
            ("Cà phê sữa đá (ly)", 18000, "fa-mug-saucer"),
            ("Nước tăng cường", 20000, "fa-bolt"),
        ],
        'weekday': [('05:00 - 09:00', time(5, 0), time(9, 0), 50000),
                    ('09:00 - 17:00', time(9, 0), time(17, 0), 70000),
                    ('17:00 - 21:00', time(17, 0), time(21, 0), 95000),
                    ('21:00 - 23:30', time(21, 0), time(23, 30), 70000)],
        'weekend': [('05:00 - 09:00', time(5, 0), time(9, 0), 65000),
                    ('09:00 - 17:00', time(9, 0), time(17, 0), 90000),
                    ('17:00 - 21:00', time(17, 0), time(21, 0), 110000),
                    ('21:00 - 23:30', time(21, 0), time(23, 30), 85000)],
    },
    'Sân Thể Thao Hồ Xuân Hưng': {
        'description': (
            "Trung tâm thể thao Hồ Xuân Hưng, Hà Nội với 5 sân bóng đá mini và 4 sân bóng bàn, "
            "kết hợp nhiều môn thể thao trong một khu liên hợp. Sân cỏ tổng hợp chất lượng cao, "
            "đèn chiếu sân tốt cho luyện tập tối."
        ),
        'highlights': [
            "5 sân bóng đá cỏ tổng hợp",
            "4 bàn bóng bàn tiêu chuẩn",
            "Hệ thống đèn chiếu sân ban đêm",
            "Khu vực khán đài có mái che",
        ],
        'rackets': [
            ("Vợt bóng bàn phủ cầu tay", 50000, "fa-table-tennis"),
            ("Vợt bóng bàn gỗ", 160000, "fa-table-tennis"),
        ],
        'drinks': [
            ("Nước suối (Chai 500ml)", 10000, "fa-bottle-water"),
            ("Nước khoáng", 13000, "fa-bottle-water"),
            ("Trà xanh", 12000, "fa-mug-hot"),
            ("Cà phê sữa", 15000, "fa-mug-saucer"),
            ("Nước tăng cường", 20000, "fa-bolt"),
        ],
        'weekday': [('05:00 - 09:00', time(5, 0), time(9, 0), 70000),
                    ('09:00 - 17:00', time(9, 0), time(17, 0), 100000),
                    ('17:00 - 21:00', time(17, 0), time(21, 0), 140000),
                    ('21:00 - 23:30', time(21, 0), time(23, 30), 100000)],
        'weekend': [('05:00 - 09:00', time(5, 0), time(9, 0), 90000),
                    ('09:00 - 17:00', time(9, 0), time(17, 0), 120000),
                    ('17:00 - 21:00', time(17, 0), time(21, 0), 160000),
                    ('21:00 - 23:30', time(21, 0), time(23, 30), 120000)],
    },
    'Cụm Sân Thể Thao Mỹ Đình': {
        'description': (
            "Cụm sân Mỹ Đình, Hà Nội - điểm đến thể thao cao cấp với 4 sân bóng bàn thi đấu và "
            "3 sân cầu lông chất lượng giải đấu. Sàn thảm thi đấu, hệ thống bảng điện tử chuyên nghiệp "
            "và dịch vụ đào tạo theo nhóm."
        ),
        'highlights': [
            "4 sân bóng bàn cấp thi đấu",
            "3 sân cầu lông tiêu chuẩn quốc tế",
            "Bảng điện tử chuyên nghiệp",
            "Có dịch vụ đào tạo theo nhóm",
        ],
        'rackets': [
            ("Vợt bóng bàn thi đấp STIGA Carbon", 480000, "fa-table-tennis"),
            ("Vợt bóng bàn Butterfly Viscaria", 850000, "fa-table-tennis"),
            ("Vợt cầu lông Yonex Astrox", 420000, "fa-table-tennis"),
            ("Vợt cầu lông liên hợp Lining", 380000, "fa-table-tennis"),
        ],
        'drinks': [
            ("Nước suối Crystal (Chai 500ml)", 15000, "fa-bottle-water"),
            ("Nước khoáng Thiên Minh", 18000, "fa-bottle-water"),
            ("Trà ô long", 20000, "fa-mug-hot"),
            ("Cà phê Arabica (ly)", 35000, "fa-mug-saucer"),
            ("Nước tăng cường", 28000, "fa-bolt"),
            ("Sữa tươi Sữa chua", 25000, "fa-mug-hot"),
        ],
        'weekday': [('05:00 - 09:00', time(5, 0), time(9, 0), 150000),
                    ('09:00 - 17:00', time(9, 0), time(17, 0), 200000),
                    ('17:00 - 21:00', time(17, 0), time(21, 0), 280000),
                    ('21:00 - 23:30', time(21, 0), time(23, 30), 200000)],
        'weekend': [('05:00 - 09:00', time(5, 0), time(9, 0), 180000),
                    ('09:00 - 17:00', time(9, 0), time(17, 0), 250000),
                    ('17:00 - 21:00', time(17, 0), time(21, 0), 320000),
                    ('21:00 - 23:30', time(21, 0), time(23, 30), 240000)],
    },
    'Sân Cầu Lông Quận 7': {
        'description': (
            "Sân cầu lông Quận 7, TP.HCM với 5 sân trong nhà. Vị trí thuận tiện gần trung tâm, "
            "sân mới, thảm Enlio và hệ thống chiếu sáng chuyên nghiệp. Rất tiện cho dân văn phòng "
            "chơi sau giờ làm hoặc cuối tuần."
        ),
        'highlights': [
            "5 sân trong nhà mới đầu tư",
            "Thảm Enlio chuyên dụng",
            "Chiếu sáng chuyên nghiệp",
            "Có chỗ gửi xe & căng tin",
        ],
        'rackets': [
            ("Vợt cầu lông phổ thông", 150000, "fa-table-tennis"),
            ("Vợt cầu lông Yonex", 320000, "fa-table-tennis"),
            ("Vợt cầu lông Lining", 280000, "fa-table-tennis"),
        ],
        'drinks': [
            ("Nước suối Aquafina", 12000, "fa-bottle-water"),
            ("Nước khoáng Lavie", 15000, "fa-bottle-water"),
            ("Trà tắc xanh", 18000, "fa-mug-hot"),
            ("Cà phê đen", 15000, "fa-mug-saucer"),
            ("Nước tăng cường", 22000, "fa-bolt"),
        ],
        'weekday': [('05:00 - 09:00', time(5, 0), time(9, 0), 110000),
                    ('09:00 - 17:00', time(9, 0), time(17, 0), 150000),
                    ('17:00 - 21:00', time(17, 0), time(21, 0), 210000),
                    ('21:00 - 23:30', time(21, 0), time(23, 30), 150000)],
        'weekend': [('05:00 - 09:00', time(5, 0), time(9, 0), 140000),
                    ('09:00 - 17:00', time(9, 0), time(17, 0), 180000),
                    ('17:00 - 21:00', time(17, 0), time(21, 0), 230000),
                    ('21:00 - 23:30', time(21, 0), time(23, 30), 170000)],
    },
}


def seed_pricing():
    """Đặt bảng giá khác nhau cho từng cụm sân."""
    print("\n=== 1. THIẾT LẬP BIỂU GIÁ RIÊNG CHO TỪNG CỤM SÂN ===")
    for facility in Facility.objects.all():
        plan = PRICING_PLANS.get(facility.name)
        if not plan:
            # Cụm sân chưa có trong kế hoạch -> dùng mức trung bình
            plan = PRICING_PLANS['Cụm Sân Pickleball Thanh Đa']

        PricingRule.objects.filter(facility=facility).delete()
        count = 0
        for day in range(7):
            is_weekend = day >= 5
            slots = plan['weekend'] if is_weekend else plan['weekday']
            for _label, start_t, end_t, price in slots:
                PricingRule.objects.create(
                    facility=facility,
                    day_of_week=day,
                    start_time=start_t,
                    end_time=end_t,
                    price_per_hour=Decimal(str(price)),
                )
                count += 1
        cheapest = min(p[3] for p in plan['weekday'])
        dearest = max(p[3] for p in plan['weekend'])
        print(f"  ✔ {facility.name}: {count} khung giá "
              f"({cheapest:,}đ - {dearest:,}đ/giờ)")


def seed_addons():
    """Tạo dịch vụ bổ sung (thuê vợt & thức uống) riêng cho từng cụm sân."""
    print("\n=== 2. TẠO DỊCH VỤ BỔ SUNG (THUÊ VỢT + THỨC UỐNG) ===")
    for facility in Facility.objects.all():
        plan = PRICING_PLANS.get(facility.name) or PRICING_PLANS['Cụm Sân Pickleball Thanh Đa']

        # Xóa dịch vụ cũ (giữ nguyên những dịch vụ chủ sân tự thêm)
        AddonService.objects.filter(facility=facility).delete()

        order = 0
        for name, price, icon in plan['rackets']:
            AddonService.objects.create(
                facility=facility,
                name=name,
                description="Thuê dụng cụ dùng riêng cho buổi đặt sân.",
                category='EQUIPMENT',
                unit_type='PER_ITEM',
                unit_price=Decimal(str(price)),
                icon=icon,
                is_active=True,
                sort_order=order,
            )
            order += 1

        for name, price, icon in plan['drinks']:
            AddonService.objects.create(
                facility=facility,
                name=name,
                description="Đồ uống phục vụ tại quầy.",
                category='DRINK',
                unit_type='PER_ITEM',
                unit_price=Decimal(str(price)),
                icon=icon,
                is_active=True,
                sort_order=order,
            )
            order += 1

        print(f"  ✔ {facility.name}: {len(plan['rackets'])} dịch vụ thuê dụng cụ + "
              f"{len(plan['drinks'])} món thức uống")


def seed_descriptions():
    """Ghi mô tả & điểm nổi bật cho cụm sân."""
    print("\n=== 3. CẬP NHẬT MÔ TẢ & ĐIỂM NỔI BẬT ===")
    for facility in Facility.objects.all():
        plan = PRICING_PLANS.get(facility.name) or PRICING_PLANS['Cụm Sân Pickleball Thanh Đa']
        facility.description = plan['description']
        # highlights là CharField, các điểm nổi bật ngăn cách bằng dấu |
        facility.highlights = ' | '.join(plan['highlights'])
        facility.save(update_fields=['description', 'highlights'])
        print(f"  ✔ {facility.name}")


def main():
    print("--- SEED BIỂU GIÁ & DỊCH VỤ BỔ SUNG ---")
    seed_pricing()
    seed_addons()
    seed_descriptions()
    print("\n--- HOÀN TẤT! Biểu giá & dịch vụ đã khác nhau theo từng cụm sân. ---")


if __name__ == '__main__':
    main()
