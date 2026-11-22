"""
Middleware chong cache trinh duyet cho moi truong DEV.

Ly do can thiet:
Khi sua template (Django khong tu dong reload khi browser da cache HTML),
trinh duyet van dung ban HTML CU -> hien loi cu len tren man hinh ma source
da sua. Header 'no-store' + 'no-cache' buoc browser phai tai lai tuong phan.

Chi bat khi DEBUG = True (khong ap dung cho production).
"""
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class NoCacheMiddleware(MiddlewareMixin):
    """Chong cache HTML khi dang phat trien (chi bat o DEBUG=True)."""

    def process_response(self, request, response):
        # Chi ap dung cho HTML (khong phai file tinh, API JSON, ...)
        content_type = response.get('Content-Type', '') or ''
        if 'text/html' not in content_type:
            return response

        # Khong ap dung cho production (de ton tai hieu nang)
        if not settings.DEBUG:
            return response

        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        # De trinh duyet khong dung lai ban cache cu (neu co)
        response['Clear-Site-Data'] = '"cache"'
        return response
