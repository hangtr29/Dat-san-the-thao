"""
cleanup_addon_duplicates.py
===========================
Dọn dẹp dịch vụ bổ sung bị TRÙNG tên trong từng cụm sân.

Sau khi seed, mỗi cụm sân có thể bị trùng do:
- Dữ liệu cũ đã có sẵn dịch vụ (vợt, nước uống) từ trước.
- Script seed tạo thêm bản "chuẩn hóa" với tên khác (VD: "Thuê vợt" vs "Vợt Pickleball...").

Script này:
1. Gộp các bản ghi trùng (giữ bản có giá hợp lý nhất & đang active).
2. Xoá các bản ghi "Thuê vợt" / "Thuê cầu lông (tube)" bị trùng chức năng với
   bản ghi chi tiết hơn đã có sẵn (vợt theo loại, cầu lông theo tube).

Cách chạy:
    python cleanup_addon_duplicates.py
"""
import os
from collections import defaultdict

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from facilities.models import Facility, AddonService  # noqa: E402


def normalize(name):
    """Chuẩn hoá tên để so sánh trùng lặp (bỏ dấu tiếng Việt, ký tự đặc biệt)."""
    import unicodedata

    text = unicodedata.normalize('NFD', name or '')
    text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn')
    text = text.lower()
    for ch in '()[]{}/-–—_,.:;':
        text = text.replace(ch, ' ')
    return ' '.join(text.split())


def find_duplicates(services):
    """Gom các dịch vụ trùng nhau theo tên đã chuẩn hoá."""
    groups = defaultdict(list)
    for svc in services:
        groups[normalize(svc.name)].append(svc)
    return {k: v for k, v in groups.items() if len(v) > 1}


def merge_group(group):
    """
    Gộp nhóm trùng:
    - Giữ lại bản ghi "đại diện": ưu tiên active, giá cao, sort_order cao.
    - Xoá các bản ghi còn lại (chuyển BookingAddon liên kết sang bản giữ lại).
    """
    group_sorted = sorted(
        group,
        key=lambda s: (s.is_active, s.unit_price, s.sort_order),
        reverse=True,
    )
    keeper = group_sorted[0]
    removed = []
    for svc in group_sorted[1:]:
        try:
            svc.booking_addons.update(service=keeper)
        except Exception:
            pass
        svc.delete()
        removed.append(svc.name)
    return keeper, removed


# Các tên "generic" bị trùng chức năng với bản ghi chi tiết hơn đã tồn tại
GENERIC_NAMES = {
    'thue vot', 'thue vot badminton', 'thue vot pickleball',
    'thue cau long', 'thue cau long tube',
}


def remove_redundant_generic(services):
    """
    Nếu cụm sân đã có dịch vụ vợt chi tiết (VD: "Vợt gỗ", "Vợt Pickleball...")
    thì bản "Thuê vợt" generic là thừa -> chuyển BookingAddon sang bản chi tiết
    có giá gần nhất rồi xoá.
    """
    from bookings.models import BookingAddon

    removed_names = []
    for svc in list(services):
        key = normalize(svc.name)
        if key not in GENERIC_NAMES:
            continue

        alternatives = [
            s for s in services
            if s.pk != svc.pk
            and normalize(s.name) not in GENERIC_NAMES
            and ('vot' in normalize(s.name) if 'vot' in key else 'cau long' in normalize(s.name))
        ]
        if not alternatives:
            continue

        alt = min(alternatives, key=lambda s: abs(int(s.unit_price) - int(svc.unit_price)))
        BookingAddon.objects.filter(service=svc).update(service=alt)
        removed_names.append(svc.name)
        svc.delete()

    return removed_names


def main():
    total_removed = 0
    for facility in Facility.objects.all().order_by('name'):
        services = list(facility.addon_services.all())
        before = len(services)

        # 1. Gộp các bản ghi trùng tên
        for key, group in list(find_duplicates(services).items()):
            keeper, removed = merge_group(group)
            print(f"   🔗 Gộp trùng '{keeper.name}' — đã xoá: {removed}")
            total_removed += len(removed)

        # 2. Xoá bản generic trùng chức năng
        services = list(facility.addon_services.all())
        redundant = remove_redundant_generic(services)
        if redundant:
            print(f"   🧹 Xoá dịch vụ generic trùng chức năng: {redundant}")
            total_removed += len(redundant)

        after = facility.addon_services.count()
        print(f"✅ {facility.name}: {before} → {after} dịch vụ")
        for s in facility.addon_services.order_by('sort_order', 'name'):
            print(f"      • {s.name} — {int(s.unit_price):,} đ ({s.get_unit_type_display()})")
        print()

    print(f"🎉 Đã dọn dẹp {total_removed} bản ghi trùng lặp.")


if __name__ == '__main__':
    main()
