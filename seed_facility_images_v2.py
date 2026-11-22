"""
seed_facility_images_v2.py
=========================
Gan lai anh cho tung cum san: MOI SAN MOT BO ANH RIENG, DAU DU va KHONG TRUNG LAP.

Nguon anh:
  - media/facilities/source/   : anh goc (Wikimedia Commons - CC/PD)
  - media/facilities/pool2/    : anh chat luong cao (pickleball, cau long, bong ban)
  - media/facilities/gallery/  : anh bien the da tai len

Moi cum san nhan 1 anh bia + 6 anh thu vien rieng biet.

Cach chay: python seed_facility_images_v2.py
"""
import os
import sys

import django

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.files import File  # noqa: E402
from facilities.models import Facility, FacilityGalleryImage  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = os.path.join(BASE_DIR, 'media', 'facilities')


# ---------------------------------------------------------------------------
# BO ANH RIENG CHO TUNG CUM SAN
#   'cover'   : anh bia (1 anh)
#   'gallery' : (duong dan tuong doi trong media/facilities, caption) - 6 anh
# Khong anh nao trung giua 2 cum san.
# ---------------------------------------------------------------------------
FACILITY_PHOTOS = {
    'CLB Thể Thao Sài Gòn Star': {
        'cover': 'pool2/bad1.jpg',
        'gallery': [
            ('pool2/bad3.jpg', 'Sân cầu lông trong nhà tiêu chuẩn thi đấu'),
            ('source/bad_thoddoo1.jpg', 'Thảm PVC chuyên dụng & hệ thống đèn chống chói'),
            ('pool2/pick1.jpg', 'Khu vực Pickleball trong nhà'),
            ('pool2/pick2.jpg', 'Mặt sân Pickleball chống trượt chuyên dụng'),
            ('pool2/tt1.jpg', 'Bàn bóng bàn tiêu chuẩn thi đấu'),
            ('pool2/tt2.jpg', 'Khu vực luyện tập bóng bàn'),
        ],
    },
    'Nhà thi đấu Cầu Lông Bạch Đằng': {
        'cover': 'pool/b_1554068865-24cecd4e34b8.jpg',
        'gallery': [
            ('pool/a_1626224583764-f87db24ac4ea.jpg', 'Nhà thi đấu cầu lông với 3 sân tiêu chuẩn'),
            ('pool2/bad3.jpg', 'Sân cầu lông trong nhà chuyên nghiệp'),
            ('pool/c_1595435934249-5df7ed86e1c0.jpg', 'Sàn thảm chuyên dụng & ánh sáng không chói'),
            ('pool2/tt1.jpg', 'Nhà thi đấu bóng bàn tiêu chuẩn'),
            ('pool2/tt2.jpg', 'Khu vực bàn bóng bàn thi đấu'),
            ('source/tt_ching_wah.jpg', 'Bàn bóng bàn chuyên nghiệp'),
        ],
    },
    'Cụm Sân Cầu Lông Thanh Đa': {
        'cover': 'pool/d_1546519638-68e109498ffc.jpg',
        'gallery': [
            ('pool/e_1571902943202-507ec2618e8f.jpg', 'Toàn cảnh khu vực sân trong nhà'),
            ('pool2/bad1.jpg', 'Sân cầu lông tiêu chuẩn thi đấu'),
            ('pool2/bad3.jpg', 'Hệ thống đèn chiếu sân chuyên dụng'),
            ('pool2/pick1.jpg', 'Sân Pickleball ngoài trời'),
            ('pool2/tt2.jpg', 'Phòng bóng bàn riêng biệt'),
            ('source/tt_room.jpg', 'Khu vực bàn bóng bàn thi đấu'),
        ],
    },
    'CLB Thể Thao Phú Nhuận Sky Garden': {
        'cover': 'pool/f_1461896836934-ffe607ba8211.jpg',
        'gallery': [
            ('pool/g_1551698618-1dfe5d97d256.jpg', 'Không gian thi đấu Pickleball hiện đại'),
            ('pool2/pick2.jpg', 'Sân Pickleball tiêu chuẩn thi đấu'),
            ('pool/h_1526232761682-d26e03ac148e.jpg', 'Sân cầu lông mở với sân vườn'),
            ('pool/i_1519861531473-9200262188bf.jpg', 'Mặt sân thi đấu chuyên nghiệp'),
            ('pool2/tt1.jpg', 'Khu vực luyện tập bóng bàn'),
            ('pool/j_1540747913346-19e32dc3e97e.jpg', 'Bàn bóng bàn trong nhà'),
        ],
    },
    'CLB Pickleball Hoa Lư': {
        'cover': 'pool/k_1574629810360-7efbbe195018.jpg',
        'gallery': [
            ('pool/l_1534438327276-14e5300c3a48.jpg', 'Toàn cảnh cụm sân Pickleball từ trên cao'),
            ('pool/m_1519861531473.jpg', 'Sân Pickleball ngoài trời ánh đèn LED'),
            ('pool2/pick1.jpg', 'Mặt sân Acrylic chống trượt chuyên dụng'),
            ('pool2/pick2.jpg', 'Cụm sân Pickleball tiêu chuẩn thi đấu'),
            ('pool/n_1600679472829-3044539ce8ed.jpg', 'Lưới và vạch sân thi đấu'),
            ('source/bad_view.jpg', 'Sân cầu lông mở với sân vườn'),
        ],
    },
    'Sân Bóng Bàn & Pickleball Thảo Điền': {
        'cover': 'pool2/tt1.jpg',
        'gallery': [
            ('pool2/tt2.jpg', 'Phòng bóng bàn tiêu chuẩn thi đấu'),
            ('pool/i_1519861531473-9200262188bf.jpg', 'Bàn bóng bàn chuyên nghiệp'),
            ('pool/j_1540747913346-19e32dc3e97e.jpg', 'Khu vực bàn bóng bàn thi đấu'),
            ('pool2/pick1.jpg', 'Sân Pickleball trong nhà'),
            ('pool2/bad1.jpg', 'Sân cầu lông ngoài trời'),
            ('pool/h_1526232761682-d26e03ac148e.jpg', 'Sân cầu lông mở với sân vườn'),
        ],
    },
}


def relative_media_path(rel_path):
    """Chuyển 'pool2/pick1.jpg' thành đường dẫn tương đối tính từ MEDIA_ROOT."""
    return os.path.join('facilities', *rel_path.split('/')).replace('\\', '/')


def assign_photos():
    print('--- ĐANG GÁN ẢNH RIÊNG CHO TỪNG CỤM SÂN ---')

    for facility in Facility.objects.all().order_by('name'):
        config = FACILITY_PHOTOS.get(facility.name)
        if not config:
            print(f' -> BỎ QUA (chưa cấu hình ảnh): {facility.name}')
            continue

        # 1. Ảnh bìa (cover) - nằm trong Field Image của Facility
        cover_rel = config['cover']
        cover_path = os.path.join(MEDIA_DIR, *cover_rel.split('/'))
        if not os.path.exists(cover_path):
            print(f' -> THIẾU FILE ẢNH: {cover_rel} (cho {facility.name})')
            continue

        facility.image.save(os.path.basename(cover_rel), File(open(cover_path, 'rb')), save=True)

        # 2. Thư viện ảnh (gallery) - xoá ảnh cũ rồi tạo lại theo thứ tự
        facility.gallery_images.all().delete()
        count = 0
        for index, (rel_path, caption) in enumerate(config['gallery']):
            src = os.path.join(MEDIA_DIR, *rel_path.split('/'))
            if not os.path.exists(src):
                print(f' -> THIẾU FILE ẢNH: {rel_path}')
                continue
            gallery = FacilityGalleryImage(
                facility=facility,
                caption=caption,
                sort_order=index,
            )
            with open(src, 'rb') as fh:
                gallery.image.save(os.path.basename(rel_path), File(fh), save=False)
            gallery.save()
            count += 1

        print(f' -> ĐÃ GÁN: {facility.name} | ảnh bìa + {count} ảnh thư viện')

    print('--- HOÀN TẤT! ---')


def check_duplicates():
    """Kiểm tra không có ảnh nào bị dùng chung cho 2 cụm sân."""
    print('\n--- KIỂM TRA ẢNH TRÙNG LẶP ---')
    from collections import defaultdict

    usage = defaultdict(set)
    for f in Facility.objects.all():
        if f.image:
            usage[f.image.url].add(f.name)
        for g in f.gallery_images.all():
            usage[g.image.url].add(f.name)

    dup_found = False
    for url, names in usage.items():
        if len(names) > 1:
            dup_found = True
            print(f' -> TRÙNG: {url} <- {", ".join(sorted(names))}')
    if not dup_found:
        print(' -> OK! Mỗi ảnh chỉ thuộc về 1 cụm sân duy nhất.')
    print(f' -> Tổng số ảnh duy nhất: {len(usage)}')


if __name__ == '__main__':
    assign_photos()
    check_duplicates()
