"""
seed_addons_per_facility.py
===========================
Tao lai DICH VU PHU cho tung cum san, moi cum san mot bo rieng (gia khac nhau),
phu hop voi mon the thao va dang cap cua cum san do.

Vi du: 6 cum san hien tai trong DB
  - CLB Thể Thao Sài Gòn Star          : 7 san, 3 mon  -> gia cao nhat
  - Nhà thi đấu Cầu Lông Bạch Đằng   : 5 san, 2 mon  -> gia cao
  - Cụm Sân Cầu Lông Thanh Đa        : 4 san, 2 mon  -> gia trung cao
  - CLB Thể Thao Phú Nhuận Sky Garden : 4 san, 2 mon  -> gia trung binh
  - CLB Pickleball Hoa Lư             : 5 san, 2 mon  -> gia trung binh
  - Sân Bóng Bàn & Pickleball Thao Dien: 5 san, 3 mon -> gia re nhat

Cach chay:
    python seed_addons_per_facility.py
"""
import os
from decimal import Decimal

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from facilities.models import Facility, AddonService  # noqa: E402


# ---------------------------------------------------------------------------
# BANG DICH VU PHU RIENG CHO TUNG CUM SAN
#   'rackets' : danh sach (ten, gia, icon) - thue vat
#   'drinks'  : danh sach (ten, gia, icon) - thuc uong
#   'food'    : danh sach (ten, gia, icon) - do an nhe
# Gia phu thuoc toi vung gia cua tung cum san (cao hon = dat cap hon).
# ---------------------------------------------------------------------------
ADDON_PLANS = {
    'CLB Thể Thao Sài Gòn Star': {
        'rackets': [
            ('Vợt cầu lông Yonex Nanostring', 180000, 'fa-table-tennis'),
            ('Vợt cầu lông liên hợp Lining', 220000, 'fa-table-tennis'),
            ('Vợt Pickleball carbon cao cấp', 120000, 'fa-table-tennis'),
            ('Vợt bóng bàn gỗ STIGA', 180000, 'fa-table-tennis'),
        ],
        'drinks': [
            ('Nước suối Crystal (Chai 500ml)', 15000, 'fa-bottle-water'),
            ('Nước khoáng Thiên Minh', 18000, 'fa-bottle-water'),
            ('Trà ô long', 20000, 'fa-mug-hot'),
            ('Cà phê Arabica (ly)', 35000, 'fa-mug-saucer'),
            ('Sting Vàng (250ml)', 22000, 'fa-bolt'),
        ],
        'food': [
            ('Bánh bao nóng', 20000, 'fa-bowl-food'),
            ('Xúc xích chiên', 25000, 'fa-bowl-food'),
        ],
    },
    'Nhà thi đấu Cầu Lông Bạch Đằng': {
        'rackets': [
            ('Vợt cầu lông Yonex Astrox', 420000, 'fa-table-tennis'),
            ('Vợt cầu lông liên hợp Lining', 380000, 'fa-table-tennis'),
            ('Vợt bóng bàn phủ (cầu tay)', 60000, 'fa-table-tennis'),
        ],
        'drinks': [
            ('Nước suối Aquafina', 12000, 'fa-bottle-water'),
            ('Nước khoáng Lavie', 15000, 'fa-bottle-water'),
            ('Trà đá ly (Trà xanh)', 15000, 'fa-mug-hot'),
            ('Cà phê đen (ly)', 18000, 'fa-mug-saucer'),
            ('Nước tăng cường Red Bull', 25000, 'fa-bolt'),
        ],
        'food': [
            ('Mì ăn liền', 30000, 'fa-bowl-food'),
        ],
    },
    'Cụm Sân Cầu Lông Thanh Đa': {
        'rackets': [
            ('Vợt cầu lông Yonex', 320000, 'fa-table-tennis'),
            ('Vợt cầu lông Lining', 280000, 'fa-table-tennis'),
            ('Vợt Pickleball nhựa Tiêu chuẩn', 45000, 'fa-table-tennis'),
        ],
        'drinks': [
            ('Nước suối Aquafina', 12000, 'fa-bottle-water'),
            ('Nước khoáng Lavie', 15000, 'fa-bottle-water'),
            ('Trà tắc xanh', 18000, 'fa-mug-hot'),
            ('Cà phê đen', 15000, 'fa-mug-saucer'),
            ('Nước tăng cường', 22000, 'fa-bolt'),
        ],
        'food': [
            ('Bánh mì thịt', 25000, 'fa-bowl-food'),
        ],
    },
    'CLB Thể Thao Phú Nhuận Sky Garden': {
        'rackets': [
            ('Vợt cầu lông phổ thông', 150000, 'fa-table-tennis'),
            ('Vợt Pickleball carbon cao cấp', 120000, 'fa-table-tennis'),
            ('Vợt Pickleball gỗ (gỗ tự nhiên)', 90000, 'fa-table-tennis'),
        ],
        'drinks': [
            ('Nước suối (Chai 500ml)', 12000, 'fa-bottle-water'),
            ('Nước khoáng Aquafina', 12000, 'fa-bottle-water'),
            ('Trà xanh Không Độ 0 đ', 15000, 'fa-mug-hot'),
            ('Cà phê sữa đá (ly)', 18000, 'fa-mug-saucer'),
            ('Nước tăng cường', 20000, 'fa-bolt'),
        ],
        'food': [
            ('Bánh bao nóng', 18000, 'fa-bowl-food'),
        ],
    },
    'CLB Pickleball Hoa Lư': {
        'rackets': [
            ('Vợt Pickleball nhựa Tiêu chuẩn', 45000, 'fa-table-tennis'),
            ('Vợt Pickleball carbon cao cấp', 120000, 'fa-table-tennis'),
            ('Vợt Pickleball gỗ (gỗ tự nhiên)', 90000, 'fa-table-tennis'),
        ],
        'drinks': [
            ('Nước suối (Chai 500ml)', 10000, 'fa-bottle-water'),
            ('Nước khoáng', 13000, 'fa-bottle-water'),
            ('Trà xanh', 12000, 'fa-mug-hot'),
            ('Cà phê sữa', 15000, 'fa-mug-saucer'),
            ('Nước tăng cường', 20000, 'fa-bolt'),
        ],
        'food': [
            ('Bánh chuoi', 15000, 'fa-bowl-food'),
        ],
    },
    'Sân Bóng Bàn & Pickleball Thảo Điền': {
        'rackets': [
            ('Vợt bóng bàn phủ (cầu tay)', 60000, 'fa-table-tennis'),
            ('Vợt bóng bàn gỗ (STIGA)', 180000, 'fa-table-tennis'),
            ('Vợt bóng bàn cao cấp (Butterfly)', 320000, 'fa-table-tennis'),
            ('Vợt Pickleball nhựa Tiêu chuẩn', 45000, 'fa-table-tennis'),
        ],
        'drinks': [
            ('Nước suối (Chai 500ml)', 8000, 'fa-bottle-water'),
            ('Nước khoáng Aquafina', 10000, 'fa-bottle-water'),
            ('Trà xanh Không Độ 0 đ', 12000, 'fa-mug-hot'),
            ('Cà phê sữa đá (ly)', 15000, 'fa-mug-saucer'),
            ('Nước tăng cường', 18000, 'fa-bolt'),
        ],
        'food': [
            ('Bánh bao nóng', 12000, 'fa-bowl-food'),
        ],
    },
}

# Cụm sân chưa có trong kế hoạch -> dùng bộ mặc định (đa môn, giá tầm trung)
DEFAULT_PLAN = ADDON_PLANS['Sân Bóng Bàn & Pickleball Thảo Điền']


def get_plan(facility):
    """Lấy bộ dịch vụ phụ theo tên cụm sân, fallback về bộ mặc định."""
    return ADDON_PLANS.get(facility.name.strip(), DEFAULT_PLAN)


def apply_addons(facility, plan):
    """
    Xoá toàn bộ dịch vụ phụ cũ của cụm sân rồi tạo lại theo bộ riêng.
    Mỗi mục có đơn giá khác nhau tùy theo cụm sân.
    """
    facility.addon_services.all().delete()

    order = 0
    groups = [
        ('EQUIPMENT', 'Thuê dụng cụ dùng riêng cho buổi đặt sân.', plan.get('rackets', [])),
        ('DRINK', 'Đồ uống phục vụ tại quầy.', plan.get('drinks', [])),
        ('FOOD', 'Đồ ăn nhanh phục vụ tại chỗ.', plan.get('food', [])),
    ]

    created = 0
    for category, description, items in groups:
        for name, price, icon in items:
            AddonService.objects.create(
                facility=facility,
                name=name,
                description=description,
                category=category,
                unit_type='PER_ITEM',
                unit_price=Decimal(str(price)),
                icon=icon,
                is_active=True,
                sort_order=order,
            )
            order += 1
            created += 1

    return created


def main():
    facilities = list(Facility.objects.all().order_by('name'))
    if not facilities:
        print('Chưa có cụm sân nào trong database. Hãy chạy seed_data.py trước.')
        return

    print(f'Bắt đầu tạo lại dịch vụ phụ cho {len(facilities)} cụm sân...\n')

    for facility in facilities:
        plan = get_plan(facility)
        count = apply_addons(facility, plan)
        prices = sorted({int(s.unit_price) for s in facility.addon_services.all()})
        print(f'[OK] {facility.name}')
        print(f'     {count} dịch vụ | giá từ {prices[0]:,} đ -> {prices[-1]:,} đ')
        print()

    print('Hoàn tất! Mỗi cụm sân đã có bộ dịch vụ phụ riêng với giá khác nhau.')
    print('   → Chủ sân sửa tại : /bookings/owner/services/')
    print('   → Khách chọn tại  : /bookings/confirm/<ma_don>/')


if __name__ == '__main__':
    main()
