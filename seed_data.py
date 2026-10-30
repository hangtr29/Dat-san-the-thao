import os
import sys
import django
from datetime import time, date
from decimal import Decimal

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

User = get_user_model()

def seed():
    print("--- ĐANG CẬP NHẬT DỮ LIỆU SÂN & KHUNG GIỜ MẪU (SEED DATA) ---")

    # 1. Tạo Users
    admin_user, _ = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@sportbook.vn',
            'phone': '0909000000',
            'role': UserRole.ADMIN,
            'is_staff': True,
            'is_superuser': True,
            'first_name': 'Hệ Thống',
            'last_name': 'Quản Trị'
        }
    )
    admin_user.set_password('admin123')
    admin_user.save()

    owner_user, _ = User.objects.get_or_create(
        username='chusan1',
        defaults={
            'email': 'chusan@sportbook.vn',
            'phone': '0988112233',
            'role': UserRole.OWNER,
            'is_staff': True,
            'first_name': 'Hoàng',
            'last_name': 'Nguyễn Văn'
        }
    )
    owner_user.set_password('owner123')
    owner_user.save()

    customer_user, _ = User.objects.get_or_create(
        username='khachhang1',
        defaults={
            'email': 'khachhang@sportbook.vn',
            'phone': '0912345678',
            'role': UserRole.CUSTOMER,
            'first_name': 'Minh',
            'last_name': 'Trần Đức'
        }
    )
    customer_user.set_password('customer123')
    customer_user.save()

    customer_user2, _ = User.objects.get_or_create(
        username='khachhang2',
        defaults={
            'email': 'khachhang2@sportbook.vn',
            'phone': '0933333333',
            'role': UserRole.CUSTOMER,
            'first_name': 'Tuấn',
            'last_name': 'Lê Anh'
        }
    )
    customer_user2.set_password('customer123')
    customer_user2.save()

    # 2. Tạo Môn Thể Thao
    cat_caulong, _ = SportCategory.objects.get_or_create(
        name='Cầu lông',
        defaults={'slug': 'cau-long', 'icon_url': '🏸'}
    )
    cat_pickleball, _ = SportCategory.objects.get_or_create(
        name='Pickleball',
        defaults={'slug': 'pickleball', 'icon_url': '🏓'}
    )
    cat_bongban, _ = SportCategory.objects.get_or_create(
        name='Bóng bàn',
        defaults={'slug': 'bong-ban', 'icon_url': '🏓'}
    )

    # 3. Tạo Cụm Sân (Giờ mở cửa: 05:00 đến 23:30 để có đủ các slot 21h, 22h, 23h)
    fac1, _ = Facility.objects.get_or_create(
        name='CLB Thể Thao Sài Gòn Star',
        defaults={
            'owner': owner_user,
            'address': 'Số 12 Đường D2, Phường 25, Quận Bình Thạnh, TP.HCM',
            'phone_contact': '0988112233',
            'bank_name': 'MBBank',
            'bank_account_no': '098811223399',
            'bank_account_name': 'NGUYEN VAN HOANG',
            'open_time': time(5, 0),
            'close_time': time(23, 30),
            'active_status': True
        }
    )
    # Cập nhật giờ mở cửa nếu đã tồn tại
    fac1.open_time = time(5, 0)
    fac1.close_time = time(23, 30)
    fac1.save()

    # 4. Tạo Sân Thi Đấu phân theo Khu Vực: Sân trong nhà vs Sân ngoài trời (chuẩn như Alobo)
    # Xóa các sân cũ để thiết lập lại chuẩn cấu trúc phân nhóm
    Court.objects.filter(facility=fac1).delete()

    # Nhóm: Sân trong nhà
    Court.objects.create(facility=fac1, category=cat_caulong, court_name='Sân 1', court_area='Sân trong nhà', surface_type='Thảm PVC Yonex')
    Court.objects.create(facility=fac1, category=cat_caulong, court_name='Sân 2', court_area='Sân trong nhà', surface_type='Thảm PVC Yonex')
    Court.objects.create(facility=fac1, category=cat_pickleball, court_name='Sân 3', court_area='Sân trong nhà', surface_type='Mặt sân Acrylic')
    Court.objects.create(facility=fac1, category=cat_pickleball, court_name='Sân 4', court_area='Sân trong nhà', surface_type='Mặt sân Acrylic')
    Court.objects.create(facility=fac1, category=cat_bongban, court_name='Sân 5', court_area='Sân trong nhà', surface_type='Sàn gỗ công nghiệp')

    # Nhóm: Sân ngoài trời
    Court.objects.create(facility=fac1, category=cat_pickleball, court_name='Sân 6', court_area='Sân ngoài trời', surface_type='Sơn chống trượt ngoài trời')
    Court.objects.create(facility=fac1, category=cat_caulong, court_name='Sân 7', court_area='Sân ngoài trời', surface_type='Thảm Enlio ngoài trời')

    # 5. Quy tắc tính giá (PricingRules) từ 05:00 đến 23:30
    PricingRule.objects.filter(facility=fac1).delete()
    for day in range(7):
        PricingRule.objects.create(
            facility=fac1,
            day_of_week=day,
            start_time=time(5, 0),
            end_time=time(23, 30),
            price_per_hour=Decimal('120000') if day < 5 else Decimal('150000')
        )

    # 6. Tự động sinh slot cho ngày hôm nay và ngày mai
    today = timezone.localdate()
    # Xóa các slot cũ chưa có booking của fac1 để cập nhật lại khung giờ mới
    BookingSlot.objects.filter(court__facility=fac1, booking__isnull=True).delete()
    SlotGeneratorService.generate_slots_for_facility(fac1, today)

    print(f" -> Đã thiết lập xong 7 Sân phân nhóm (Trong nhà / Ngoài trời) và mở khung giờ từ 05:00 đến 23:30!")
    print("--- HOÀN TẤT! ---")

if __name__ == '__main__':
    seed()
