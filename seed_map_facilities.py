"""
Script bổ sung 5 cụm sân mẫu với tọa độ GPS thực tế ở TP.HCM
(tọa độ nằm gần cụm sân gốc để trên bản đồ các marker nằm gần nhau).

Dùng: python seed_map_facilities.py
"""
import os
import sys
import django
from datetime import time

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from users.models import UserRole
from facilities.models import SportCategory, Facility, Court, PricingRule
from bookings.models import BookingSlot
from bookings.services import SlotGeneratorService
from django.utils import timezone
from decimal import Decimal

User = get_user_model()

# Danh sách 5 cụm sân mới: tọa độ nằm trong bán kính ~1-3km quanh khu vực Bình Thạnh, TP.HCM
NEW_FACILITIES = [
    {
        'name': 'Cụm Sân Cầu Lông Thanh Đa',
        'address': 'Số 145 Đường Bình Quới, Phường 27, Quận Bình Thạnh, TP.HCM',
        'phone_contact': '0912887766',
        'hotline': '0912887766',
        'latitude': 10.7812,
        'longitude': 106.7069,
        'bank_name': 'MBBank',
        'bank_account_no': '0912887766',
        'bank_account_name': 'NGUYEN VAN SAN THANH DA',
        'courts': [
            ('Cầu lông', 'Sân 1', 'Sân trong nhà', 'Thảm PVC Yonex'),
            ('Cầu lông', 'Sân 2', 'Sân trong nhà', 'Thảm PVC Yonex'),
            ('Cầu lông', 'Sân 3', 'Sân trong nhà', 'Thảm PVC Yonex'),
            ('Pickleball', 'Sân 4', 'Sân ngoài trời', 'Sơn chống trượt ngoài trời'),
        ],
    },
    {
        'name': 'CLB Pickleball Hoa Lư',
        'address': 'Số 8 Đường Hoa Lư, Phường 2, Quận Bình Thạnh, TP.HCM',
        'phone_contact': '0909554433',
        'hotline': '0909554433',
        'latitude': 10.7903,
        'longitude': 106.6873,
        'bank_name': 'Techcombank',
        'bank_account_no': '1903554433',
        'bank_account_name': 'TRAN THI HOA LU',
        'courts': [
            ('Pickleball', 'Sân 1', 'Sân trong nhà', 'Mặt sân Acrylic'),
            ('Pickleball', 'Sân 2', 'Sân trong nhà', 'Mặt sân Acrylic'),
            ('Pickleball', 'Sân 3', 'Sân trong nhà', 'Mặt sân Acrylic'),
            ('Pickleball', 'Sân 4', 'Sân trong nhà', 'Mặt sân Acrylic'),
            ('Cầu lông', 'Sân 5', 'Sân trong nhà', 'Thảm PVC Yonex'),
        ],
    },
    {
        'name': 'Nhà thi đấu Cầu Lông Bạch Đằng',
        'address': 'Số 350 Đường Bạch Đằng, Phường 14, Quận Bình Thạnh, TP.HCM',
        'phone_contact': '0977665544',
        'hotline': '0977665544',
        'latitude': 10.7698,
        'longitude': 106.6897,
        'bank_name': 'Vietcombank',
        'bank_account_no': '0077665544',
        'bank_account_name': 'NGUYEN VAN BACH DANG',
        'courts': [
            ('Cầu lông', 'Sân 1', 'Sân trong nhà', 'Thảm PVC Yonex'),
            ('Cầu lông', 'Sân 2', 'Sân trong nhà', 'Thảm PVC Yonex'),
            ('Cầu lông', 'Sân 3', 'Sân trong nhà', 'Thảm PVC Yonex'),
            ('Bóng bàn', 'Sân 4', 'Sân trong nhà', 'Sàn gỗ công nghiệp'),
            ('Bóng bàn', 'Sân 5', 'Sân trong nhà', 'Sàn gỗ công nghiệp'),
        ],
    },
    {
        'name': 'CLB Thể Thao Phú Nhuận Sky Garden',
        'address': 'Số 42 Đường Hoàng Văn Thụ, Phường 9, Quận Phú Nhuận, TP.HCM',
        'phone_contact': '0908112233',
        'hotline': '0908112233',
        'latitude': 10.7935,
        'longitude': 106.6723,
        'bank_name': 'VPBank',
        'bank_account_no': '1908112233',
        'bank_account_name': 'LE THI PHU NHUAN',
        'courts': [
            ('Pickleball', 'Sân 1', 'Sân ngoài trời', 'Sơn chống trượt ngoài trời'),
            ('Pickleball', 'Sân 2', 'Sân ngoài trời', 'Sơn chống trượt ngoài trời'),
            ('Cầu lông', 'Sân 3', 'Sân trong nhà', 'Thảm Enlio trong nhà'),
            ('Cầu lông', 'Sân 4', 'Sân trong nhà', 'Thảm Enlio trong nhà'),
        ],
    },
    {
        'name': 'Sân Bóng Bàn & Pickleball Thảo Điền',
        'address': 'Số 25 Đường Thảo Điền, Phường Thảo Điền, Quận 3, TP.HCM',
        'phone_contact': '0987321456',
        'hotline': '0987321456',
        'latitude': 10.7742,
        'longitude': 106.7138,
        'bank_name': 'BIDV',
        'bank_account_no': '1897321456',
        'bank_account_name': 'PHAM THI THAO DIEN',
        'courts': [
            ('Bóng bàn', 'Sân 1', 'Sân trong nhà', 'Sàn gỗ công nghiệp'),
            ('Bóng bàn', 'Sân 2', 'Sân trong nhà', 'Sàn gỗ công nghiệp'),
            ('Pickleball', 'Sân 3', 'Sân trong nhà', 'Mặt sân Acrylic'),
            ('Cầu lông', 'Sân 4', 'Sân ngoài trời', 'Thảm Enlio ngoài trời'),
            ('Cầu lông', 'Sân 5', 'Sân ngoài trời', 'Thảm Enlio ngoài trời'),
        ],
    },
]


def seed():
    print("--- ĐANG BỔ SUNG 5 CỤM SÂN MỚI CHO BẢN ĐỒ (TP.HCM) ---")

    # Lấy chủ sân hiện có (ưu tiên 'chusan')
    owner = User.objects.filter(username='chusan').first() or \
        User.objects.filter(role=UserRole.OWNER).first()

    if not owner:
        owner = User.objects.create_user(
            username='chusan',
            first_name='Chủ Sân',
            last_name='SportBook',
            email='chusan@sportbook.vn',
            role=UserRole.OWNER,
            is_staff=True,
            is_superuser=True,
            password='chusan123',
        )

    # Lấy danh mục môn thể thao
    cats = {c.name: c for c in SportCategory.objects.all()}

    created_count = 0
    for data in NEW_FACILITIES:
        existing = Facility.objects.filter(name=data['name']).first()
        if existing:
            print(f" -> BỎ QUA (đã tồn tại): {data['name']}")
            continue

        fac = Facility.objects.create(
            owner=owner,
            name=data['name'],
            address=data['address'],
            phone_contact=data['phone_contact'],
            hotline=data['hotline'],
            bank_name=data['bank_name'],
            bank_account_no=data['bank_account_no'],
            bank_account_name=data['bank_account_name'],
            open_time=time(5, 0),
            close_time=time(23, 30),
            active_status=True,
            is_verified=True,
            status='ACTIVE',
            reputation_score=5.0,
            latitude=data['latitude'],
            longitude=data['longitude'],
        )

        # Tạo các sân thi đấu
        for sport_name, court_name, area, surface in data['courts']:
            cat = cats.get(sport_name)
            if not cat:
                cat = SportCategory.objects.create(
                    name=sport_name,
                    slug=sport_name.lower().replace(' ', '-').replace('đ', 'd').replace('á', 'a'),
                    icon_url='🏸' if 'Cầu' in sport_name else ('🏓' if 'Pickle' in sport_name else '🏓'),
                )
                cats[sport_name] = cat
            Court.objects.create(
                facility=fac,
                category=cat,
                court_name=court_name,
                court_area=area,
                surface_type=surface,
                is_active=True,
            )

        # Quy tắc tính giá 7 ngày trong tuần
        for day in range(7):
            PricingRule.objects.create(
                facility=fac,
                day_of_week=day,
                start_time=time(5, 0),
                end_time=time(23, 30),
                price_per_hour=Decimal('120000') if day < 5 else Decimal('150000'),
            )

        # Sinh slot cho hôm nay + 7 ngày tới
        today = timezone.localdate()
        for i in range(8):
            SlotGeneratorService.generate_slots_for_facility(fac, today + timezone.timedelta(days=i))

        created_count += 1
        print(f" -> ĐÃ TẠO: {data['name']} ({len(data['courts'])} sân) @ {data['latitude']}, {data['longitude']}")

    print(f"--- HOÀN TẤT! Tổng cụm sân trong hệ thống: {Facility.objects.count()} ---")


if __name__ == '__main__':
    seed()
