"""
seed_addons_price_differentiator.py
=====================================
Chuan hoa GIA DICH VU PHU de moi CUM SAN co gia RIENG BIET cho cung mot mon.

Nguyen tac:
  - Giu nguyen ten mon (khong doi ten) de khach doc de hieu.
  - Neu 2 cum san cung ten mon -> phai khac gia it nhat 1.000d.
  - Neu 1 mon chi xuat hien o 1 cum san -> giu nguyen gia.
  - Chi dinh chinh muc do pho bien (nuoc, ca phe, tra, vot) de gia "di theo vung".
"""
import os
import sys
from decimal import Decimal

import django

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from facilities.models import Facility  # noqa: E402


# ---------------------------------------------------------------------------
# He so nhan gia theo vung gia cua tung cum san (gia thuc te cua tung quan)
#   Thao Dien (re nhat) -> Bạch Đằng (dat nhat)
# ---------------------------------------------------------------------------
PRICE_TIER = {
    'Sân Bóng Bàn & Pickleball Thảo Điền': 0,
    'CLB Pickleball Hoa Lư': 1,
    'CLB Thể Thao Phú Nhuận Sky Garden': 2,
    'Cụm Sân Cầu Lông Thanh Đa': 3,
    'CLB Thể Thao Sài Gòn Star': 4,
    'Nhà thi đấu Cầu Lông Bạch Đằng': 5,
}

# Buoc nhay gia (VND) cho tung bac tuyen voi do pho bien cua mon do
STEP = {
    'DRINK': 1000,
    'FOOD': 2000,
    'EQUIPMENT': 10000,
    'OTHER': 5000,
}


def collect():
    """Gom tat ca mon theo ten -> danh sach (facility, addon)."""
    name_map = {}
    for f in Facility.objects.prefetch_related('addon_services').order_by('name'):
        for a in f.addon_services.all():
            name_map.setdefault(a.name, []).append((f, a))
    return name_map


def main():
    name_map = collect()
    changes = []

    for name, entries in name_map.items():
        if len(entries) < 2:
            continue

        # Sap xep theo bac gia: cum san re nhat dat gia thap nhat
        entries.sort(key=lambda fa: PRICE_TIER.get(fa[0].name, 99))

        # Buoc gia ban dau cho mon nay: lay gia cua cum san re nhat
        step = STEP.get(entries[0][1].category, 5000)
        base = Decimal(entries[0][1].unit_price)

        # Dam bao khac nhau it nhat 1 buoc
        for idx, (facility, addon) in enumerate(entries):
            tier = PRICE_TIER.get(facility.name, 99)
            target = base + step * tier

            if Decimal(addon.unit_price) != target:
                changes.append((facility.name, name, addon.unit_price, target))
                addon.unit_price = target
                addon.save(update_fields=['unit_price'])

    print('=' * 78)
    print(f'DA CHUAN HOA GIA: {len(changes)} DONG THAY DOI')
    print('=' * 78)
    for fname, name, old, new in changes:
        print(f'  {fname:<40} | {name:<32} | {old:>9,} -> {new:>9,} đ'.replace(',', '.'))

    # ---- Kiem tra lai ----
    print('\n' + '=' * 78)
    print('KIEM TRA LAI: TEN TRUNG CO GIA KHAC NHAU?')
    print('=' * 78)
    ok = True
    for name, entries in sorted(collect().items()):
        if len(entries) < 2:
            continue
        prices = {a.unit_price for _, a in entries}
        if len(prices) > 1:
            detail = ', '.join(
                f'{f.name.split()[0]}/{f.name.split()[-1]}:{a.unit_price:,}đ'.replace(',', '.')
                for f, a in entries
            )
            print(f'  OK  {name:<34} -> {detail}')
        else:
            ok = False
            print(f'  !!  {name:<34} -> VAN TRUNG GIA: {entries}')

    print('\n=> ' + ('PASS: Moi cum san co bang gia rieng cho tung mon.' if ok else 'FAIL: Con mon trung gia.'))


if __name__ == '__main__':
    main()
