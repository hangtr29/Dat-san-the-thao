"""
Custom pagination cho DRF.

Cho phép client tùy chỉnh số lượng item/trang bằng query param `page_size`.
Mặc định giữ nguyên PAGE_SIZE cấu hình trong settings.
"""
from rest_framework.pagination import PageNumberPagination


class FlexiblePageNumberPagination(PageNumberPagination):
    """
    - `?page=2`        -> trang thứ 2
    - `?page_size=50`  -> mỗi trang 50 item (tối đa 100)
    """

    page_size_query_param = 'page_size'
    max_page_size = 100
