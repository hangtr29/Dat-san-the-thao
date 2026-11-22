"""
Gán ảnh thật cho TỪNG cụm sân trong hệ thống (mỗi sân một bộ ảnh khác nhau).

Ảnh nguồn: Wikimedia Commons (giấy phép tự do CC/PD) - xem media/facilities/source/CREDITS.txt
Chạy: python seed_facility_images.py

Tính đóng gói (Encapsulation): Ảnh bìa được lưu vào Facility.image,
các ảnh còn lại nằm trong FacilityGalleryImage (thư viện ảnh của cụm sân).
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

from django.conf import settings
from django.core.files import File
from facilities.models import Facility, FacilityGalleryImage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(BASE_DIR, 'media', 'facilities', 'source')


def relative_media_path(filename: str) -> str:
    """Chuyển tên file trong media/source thành đường dẫn tương đối tính từ MEDIA_ROOT."""
    return os.path.join('facilities', 'source', filename).replace('\\', '/')


# Mỗi cụm sân có bộ ảnh RIÊNG (không trùng lặp giữa các cụm)
FACILITY_PHOTOS = {
    'CLB Thể Thao Sài Gòn Star': {
        'cover': 'bad_iitd.jpg',
        'gallery': [
            ('bad_thoddoo1.jpg', 'Sân cầu lông tiêu chuẩn trong nhà'),
            ('bad_thoddoo5.jpg', 'Thảm PVC chuyên dụng & hệ thống đèn chống chói'),
            ('pick_1_3.jpg', 'Khu vực Pickleball trong nhà'),
            ('tt_haikou.jpg', 'Bàn bóng bàn tiêu chuẩn thi đấu'),
        ],
    },
    'Cụm Sân Cầu Lông Thanh Đa': {
        'cover': 'bad_thoddoo3.jpg',
        'gallery': [
            ('bad_thoddoo9.jpg', 'Nhà thi đấu cầu lông với 3 sân tiêu chuẩn'),
            ('bad_view.jpg', 'Toàn cảnh khu vực sân trong nhà'),
            ('pick_7_9.jpg', 'Sân Pickleball ngoài trời'),
            ('tt_room.jpg', 'Phòng bóng bàn riêng biệt'),
        ],
    },
    # Ảnh do người dùng chỉ định:
    #   pick_1_3.jpg      -> sân Pickleball (Harry B. Anderson Tennis Center)
    #   tt_ching_tai.jpg  -> sân Bóng bàn (Ching Tai Court Table Tennis Zone)
    'CLB Pickleball Hoa Lư': {
        'cover': 'pick_1_3.jpg',
        'gallery': [
            ('pick_aerial.jpg', 'Toàn cảnh cụm sân Pickleball từ trên cao'),
            ('pick_10_12.jpg', 'Sân Pickleball ngoài trời ánh đèn LED'),
            ('pick_mckey.jpg', 'Mặt sân Acrylic chống trượt chuyên dụng'),
            ('pick_4_6.jpg', 'Cụm sân Pickleball tiêu chuẩn thi đấu'),
        ],
    },
    'Nhà thi đấu Cầu Lông Bạch Đằng': {
        'cover': 'bad_thoddoo5.jpg',
        'gallery': [
            ('bad_thoddoo1.jpg', 'Sân cầu lông trong nhà chuyên nghiệp'),
            ('tt_hirano.jpg', 'Nhà thi đấu bóng bàn tiêu chuẩn'),
            ('tt_china_01.jpg', 'Sàn gỗ công nghiệp cho môn bóng bàn'),
            ('tt_ching_wah.jpg', 'Khu vực bàn bóng bàn thi đấu'),
        ],
    },
    'CLB Thể Thao Phú Nhuận Sky Garden': {
        'cover': 'pick_milwaukee.jpg',
        'gallery': [
            ('pick_guangzhou.jpg', 'Không gian thi đấu Pickleball hiện đại'),
            ('bad_view.jpg', 'Sân cầu lông mở với sân vườn'),
            ('tt_china_05.jpg', 'Khu vực luyện tập bóng bàn'),
            ('pick_mckey.jpg', 'Mặt sân thi đấu chuyên nghiệp'),
        ],
    },
    'Sân Bóng Bàn & Pickleball Thảo Điền': {
        'cover': 'tt_ching_tai.jpg',
        'gallery': [
            ('tt_room.jpg', 'Phòng bóng bàn tiêu chuẩn thi đấu'),
            ('tt_hirano.jpg', 'Bàn bóng bàn chuyên nghiệp'),
            ('pick_4_6.jpg', 'Sân Pickleball trong nhà'),
            ('bad_thoddoo9.jpg', 'Sân cầu lông ngoài trời'),
        ],
    },
}


def assign_photos():
    print("--- ĐANG GÁN ẢNH THẬT CHO TỪNG CỤM SÂN ---")

    for facility in Facility.objects.all():
        config = FACILITY_PHOTOS.get(facility.name)
        if not config:
            print(f" -> BỎ QUA (chưa cấu hình ảnh): {facility.name}")
            continue

        # 1. Ảnh bìa (cover) - nằm trong Field Image của Facility
        cover_name = config['cover']
        cover_path = os.path.join(SOURCE_DIR, cover_name)
        if not os.path.exists(cover_path):
            print(f" -> THIẾU FILE ẢNH: {cover_name} (cho {facility.name})")
            continue

        if facility.image and os.path.basename(facility.image.name) == cover_name:
            pass  # đã gán đúng rồi
        else:
            with open(cover_path, 'rb') as fh:
                facility.image.save(cover_name, File(fh), save=True)

        # 2. Thư viện ảnh (gallery) - xoá ảnh cũ rồi tạo lại theo thứ tự
        facility.gallery_images.all().delete()
        for index, (filename, caption) in enumerate(config['gallery']):
            src = os.path.join(SOURCE_DIR, filename)
            if not os.path.exists(src):
                print(f" -> THIẾU FILE ẢNH: {filename}")
                continue
            gallery = FacilityGalleryImage(
                facility=facility,
                caption=caption,
                sort_order=index,
            )
            with open(src, 'rb') as fh:
                gallery.image.save(filename, File(fh), save=False)
            gallery.save()

        print(f" -> ĐÃ GÁN: {facility.name} | ảnh bìa + {len(config['gallery'])} ảnh thư viện")

    print("--- HOÀN TẤT! ---")


if __name__ == '__main__':
    assign_photos()
