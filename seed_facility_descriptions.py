"""
seed_facility_descriptions.py
=============================
Sua lai MO TA & DIEM NOI BAT cho tung cum san cho dung voi vi tri,
mon the thao va quy mo ta thuc te cua tung cum san.

Cach chay: python seed_facility_descriptions.py
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

from facilities.models import Facility  # noqa: E402


# ---------------------------------------------------------------------------
# MO TA & DIEM NOI BAT DUNG VOI TUNG CUM SAN
# ---------------------------------------------------------------------------
DESCRIPTIONS = {
    'CLB Thể Thao Sài Gòn Star': {
        'description': (
            "CLB Thể Thao Sài Gòn Star tọa lạc tại Số 12 Đường D2, Phường 25, Quận Bình Thạnh, "
            "TP.HCM - cụm sân đa môn hội tụ cả cầu lông, Pickleball và bóng bàn trong một không gian. "
            "Sàn thảm PVC chuyên nghiệp chống trượt, hệ thống đèn LED không chói mắt, đầy đủ tiện ích "
            "thay vợt và căng tin phục vụ nước. Phù hợp cho cả tập luyện lẫn thi đấu giao hữu."
        ),
        'highlights': [
            "7 sân đa môn (cầu lông, Pickleball, bóng bàn)",
            "Sàn PVC chuyên dụng chống trượt",
            "Đèn LED 1500lux không chói mắt",
            "Có thuê vợt & nước uống tại chỗ",
            "Bãi xe máy & ô tô riêng",
        ],
    },
    'Nhà thi đấu Cầu Lông Bạch Đằng': {
        'description': (
            "Nhà thi đấu Cầu Lông Bạch Đằng nằm tại Số 350 Đường Bạch Đằng, Phường 14, Quận Bình Thạnh, "
            "TP.HCM - điểm đến cho môn cầu lông và bóng bàn với trần nhà cao thoáng. "
            "Sàn thảm Enlio chuyên dụng, ánh sáng đèn chống chói, khán đài đặt kín góc và chỗ để giày "
            "riêng biệt. Không gian phù hợp cho tập luyện hằng ngày lẫn tổ chức giải giao hữu."
        ),
        'highlights': [
            "5 sân cầu lông & bóng bàn trong nhà",
            "Thảm Enlio chuyên dụng cho cầu lông",
            "Ánh sáng chống chói mắt",
            "Có căng tin & chỗ để giày",
            "Không gian yên tĩnh, điều hoà thông gió",
        ],
    },
    'Cụm Sân Cầu Lông Thanh Đa': {
        'description': (
            "Cụm Sân Cầu Lông Thanh Đa tọa lạc tại Số 145 Đường Bình Quới, Phường 27, Quận Bình Thạnh, "
            "TP.HCM - sân cầu lông chuyên nghiệp kèm khu Pickleball ngoài trời. "
            "Mặt sân thảm chuyên dụng, hệ thống chiếu sáng đồng đều và bãi giữ xe rộng rãi. "
            "Địa điểm dễ tiếp cận, thuận tiện cho người chơi sau giờ làm và cả cuối tuần."
        ),
        'highlights': [
            "4 sân cầu lông tiêu chuẩn",
            "Sân Pickleball ngoài trời ánh sáng tốt",
            "Hệ thống chiếu sân chuyên dụng",
            "Bãi giữ xe rộng",
            "Có dịch vụ thuê vợt & nước uống",
        ],
    },
    'CLB Thể Thao Phú Nhuận Sky Garden': {
        'description': (
            "CLB Thể Thao Phú Nhuận Sky Garden nằm tại Số 42 Đường Hoàng Văn Thụ, Phường 9, "
            "Quận Phú Nhuận, TP.HCM - không gian thi đấu Pickleball hiện đại kết hợp sân cầu lông "
            "mở với sân vườn. Mặt sàn chống trượt chuyên dụng, đèn LED tiết kiệm điện, "
            "không gian thoáng mát và bãi giữ xe riêng. Rất tiện cho dân văn phòng chơi sau giờ làm."
        ),
        'highlights': [
            "4 sân Pickleball & cầu lông",
            "Sân cầu lông mở với sân vườn",
            "Mặt sàn chống trượt chuyên dụng",
            "Đèn LED tiết kiệm điện",
            "Bãi xe máy & ô tô riêng",
        ],
    },
    'CLB Pickleball Hoa Lư': {
        'description': (
            "CLB Pickleball Hoa Lư tọa lạc tại Số 8 Đường Hoa Lư, Phường 2, Quận Bình Thạnh, TP.HCM - "
            "cụm sân chuyên biệt về môn Pickleball với cả sân trong nhà lẫn ngoài trời. "
            "Mặt sân Acrylic chống trượt đạt tiêu chuẩn thi đấu, hệ thống đèn LED 1500lux không chói mắt, "
            "vạch sân và lưới đúng quy cách. Phù hợp cho cả tập luyện lẫn thi đấu giao hữu."
        ),
        'highlights': [
            "5 sân Pickleball tiêu chuẩn",
            "Mặt sân Acrylic chống trượt",
            "Đèn LED 1500lux không chói mắt",
            "Vạch sân & lưới đúng quy cách thi đấu",
            "Có thuê vợt & nước uống tại chỗ",
        ],
    },
    'Sân Bóng Bàn & Pickleball Thảo Điền': {
        'description': (
            "Sân Bóng Bàn & Pickleball Thảo Điền nằm tại Số 25 Đường Thảo Điền, Phường Thảo Điền, "
            "Quận 3, TP.HCM - điểm đến giá mềm cho người chơi bóng bàn và Pickleball tại khu dân cư. "
            "Bàn bóng bàn thảm ITTF chuyên dụng, vành bàn nhựa chịu lực cao và sân Pickleball trong nhà. "
            "Không gian gọn gàng, thuận tiện cho người chơi tập luyện hằng ngày."
        ),
        'highlights': [
            "5 sân bóng bàn & Pickleball",
            "Bàn thảm ITTF chuyên dụng",
            "Vành bàn chịu lực cao",
            "Sân Pickleball trong nhà",
            "Giá thân thiện, phù hợp tập luyện hằng ngày",
        ],
    },
}


def main():
    facilities = list(Facility.objects.all().order_by('name'))
    print(f'--- CẬP NHẬT MÔ TẢ & ĐIỂM NỔI BẬT CHO {len(facilities)} CỤM SÂN ---\n')

    for facility in facilities:
        config = DESCRIPTIONS.get(facility.name)
        if not config:
            print(f' -> BỎ QUA (chưa cấu hình): {facility.name}')
            continue

        facility.description = config['description']
        facility.highlights = ' | '.join(config['highlights'])
        facility.save(update_fields=['description', 'highlights'])
        print(f' -> ĐÃ CẬP NHẬT: {facility.name}')

    print('\n--- HOÀN TẤT! ---')


if __name__ == '__main__':
    main()
