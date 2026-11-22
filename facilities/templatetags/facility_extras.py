"""
Template tags & filters dùng chung cho toàn hệ thống SportBook.

1) `vi_date`  : định dạng ngày giờ theo chuẩn tiếng Việt (Thứ Năm, 19/11/2026).
2) `gps_coord`: chuẩn hoá toạ độ GPS về định dạng thập phân dấu chấm (10.7769)
                để tránh lỗi Django format số theo locale vi-VN (10,7769) làm
                hỏng liên kết Google Maps "Chỉ đường".
3) `map_directions_url`: sinh sẵn URL chỉ đường tới cụm sân.
"""

from django import template
from django.utils import timezone

register = template.Library()

# Tên thứ đầy đủ trong tiếng Việt (Thứ Hai -> Chủ Nhật)
VI_WEEKDAYS = [
    "Thứ Hai",
    "Thứ Ba",
    "Thứ Tư",
    "Thứ Năm",
    "Thứ Sáu",
    "Thứ Bảy",
    "Chủ Nhật",
]


@register.filter
def vi_date(value, with_time=False):
    """
    Định dạng ngày theo chuẩn Việt Nam: "Thứ Năm, 19/11/2026".
    Nếu with_time=True -> "Thứ Năm, 19/11/2026 14:35"
    """
    if not value:
        return ""

    # Chuyển sang giờ Việt Nam (Asia/Ho_Chi_Minh) trước khi định dạng
    try:
        local_value = timezone.localtime(value)
    except (ValueError, AttributeError):
        local_value = value

    try:
        weekday = VI_WEEKDAYS[local_value.weekday()]
    except (AttributeError, IndexError):
        return ""

    text = "{wd}, {d:02d}/{m:02d}/{y}".format(
        wd=weekday, d=local_value.day, m=local_value.month, y=local_value.year
    )
    if with_time:
        text += " {h:02d}:{mi:02d}".format(h=local_value.hour, mi=local_value.minute)
    return text


@register.filter
def vi_today():
    """Ngày hiện tại (giờ Việt Nam) định dạng chuẩn Việt Nam."""
    return vi_date(timezone.localtime())


@register.filter
def gps_coord(value):
    """
    Chuẩn hoá toạ độ GPS về chuỗi thập phân dấu CHẤM.
    Django dùng locale vi-VN nên 10.7769 bị render thành "10,7769",
    khiến URL Google Maps (destination=lat,lng) bị sai toạ độ.
    """
    if value is None or value == "":
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    # Bỏ các ký tự lạ (ví dụ dấu phẩy do locale) trước khi parse
    return str(round(number, 7)).replace(",", ".")


@register.simple_tag
def map_directions_url(facility):
    """
    Sinh URL chỉ đường Google Maps tới cụm sân (dùng chung cho mọi template).
    """
    if facility is None:
        return ""
    lat = gps_coord(getattr(facility, "latitude", None))
    lng = gps_coord(getattr(facility, "longitude", None))
    if not lat or not lng:
        return "#"
    return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"


@register.filter
def get_item(mapping, key):
    """
    Lấy giá trị theo key từ dict (dùng cho template: {{ my_dict|get_item:'key' }}).
    Trả về list rỗng nếu key không tồn tại -> an toàn cho vòng lặp trong template.
    """
    if not mapping:
        return []
    try:
        return mapping.get(key, [])
    except AttributeError:
        return []
