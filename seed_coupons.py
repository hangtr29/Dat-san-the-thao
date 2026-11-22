"""
seed_coupons.py
===============
Tạo các mã giảm giá & khuyến mãi mẫu cho hệ thống.

Danh sách mã:
  - SPORT10    : Giảm 10% (tối đa 50.000đ) cho đơn từ 150.000đ
  - WELCOME20  : Giảm 20% (tối đa 100.000đ) cho đơn từ 200.000đ
  - FREESHIP   : Giảm cố định 30.000đ cho đơn từ 100.000đ
  - CHUYENCA   : Giảm 50.000đ cho khách hàng cũ đặt từ 300.000đ

Cách chạy:
    python seed_coupons.py
"""
import os
from datetime import timedelta
from decimal import Decimal

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone  # noqa: E402
from facilities.models import Coupon  # noqa: E402


COUPONS = [
    {
        'code': 'SPORT10',
        'description': 'Khuyến mãi thể thao - giảm 10% tối đa 50.000đ',
        'discount_type': 'PERCENT',
        'discount_value': Decimal('10'),
        'max_discount': Decimal('50000'),
        'min_order_value': Decimal('150000'),
        'usage_limit': 0,
        'valid_days': 90,
    },
    {
        'code': 'WELCOME20',
        'description': 'Chào mừng khách hàng mới - giảm 20% tối đa 100.000đ',
        'discount_type': 'PERCENT',
        'discount_value': Decimal('20'),
        'max_discount': Decimal('100000'),
        'min_order_value': Decimal('200000'),
        'usage_limit': 500,
        'valid_days': 60,
    },
    {
        'code': 'FREESHIP',
        'description': 'Miễn phí dịch vụ - giảm cố định 30.000đ',
        'discount_type': 'FIXED',
        'discount_value': Decimal('30000'),
        'max_discount': Decimal('30000'),
        'min_order_value': Decimal('100000'),
        'usage_limit': 0,
        'valid_days': 120,
    },
    {
        'code': 'CHUYENCA',
        'description': 'Ưu đãi khách hàng thân thiết - giảm 50.000đ',
        'discount_type': 'FIXED',
        'discount_value': Decimal('50000'),
        'max_discount': Decimal('50000'),
        'min_order_value': Decimal('300000'),
        'usage_limit': 200,
        'valid_days': 180,
    },
]


def main():
    now = timezone.now()
    print('📦 Tạo mã giảm giá & khuyến mãi...\n')

    for data in COUPONS:
        valid_days = data.pop('valid_days')
        defaults = {
            'description': data['description'],
            'discount_type': data['discount_type'],
            'discount_value': data['discount_value'],
            'max_discount': data['max_discount'],
            'min_order_value': data['min_order_value'],
            'usage_limit': data['usage_limit'],
            'is_active': True,
            'valid_from': now,
            'valid_to': now + timedelta(days=valid_days),
        }
        coupon, created = Coupon.objects.update_or_create(
            code=data['code'], defaults=defaults)
        tag = '🆕 ĐÃ TẠO MỚI' if created else '♻️  ĐÃ CẬP NHẬT'
        print(f"{tag}  {coupon.code}")
        print(f"    {coupon.description}")
        print(f"    Tối thiểu {int(coupon.min_order_value):,}đ | "
              f"Giảm tối đa {int(coupon.max_discount):,}đ | "
              f"Hết hạn {coupon.valid_to.strftime('%d/%m/%Y')}")
        print()

    # Xoá mã test tạm (nếu còn)
    deleted, _ = Coupon.objects.filter(code='TEST10').delete()
    if deleted:
        print('🧹 Đã xoá mã test TEST10.')

    print(f"🎉 Hiện có {Coupon.objects.filter(is_active=True).count()} mã giảm giá đang hoạt động.")
    print('   → Khách nhập mã ở trang xác nhận đặt sân (/bookings/confirm/<mã>/)')


if __name__ == '__main__':
    main()
