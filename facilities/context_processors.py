"""
Context processor cấp phát thông tin ngày giờ thực tế cho toàn bộ template (header).
"""

from django.utils import timezone


def site_datetime(request):
    """
    Cung cấp cho template:
    - today_label : ngày hiện tại định dạng chuẩn Việt Nam ("Thứ Năm, 19/11/2026")
    - server_timestamp: mốc thời gian hiện tại (epoch ms) để JavaScript
      đồng bộ lệch múi giờ so với server theo thời gian thực.
    """
    now = timezone.localtime()
    weekday_names = [
        "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm",
        "Thứ Sáu", "Thứ Bảy", "Chủ Nhật",
    ]
    today_label = "{}, {:02d}/{:02d}/{}".format(
        weekday_names[now.weekday()], now.day, now.month, now.year
    )
    return {
        "today_label": today_label,
        "server_timestamp": int(now.timestamp() * 1000),
    }
