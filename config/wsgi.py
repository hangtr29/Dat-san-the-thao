"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import shutil
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

is_serverless = bool(
    os.environ.get('VERCEL')
    or os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
    or '/var/task' in str(BASE_DIR)
)


def _table_exists(db_file: str, table_name: str) -> bool:
    if not os.path.exists(db_file) or os.path.getsize(db_file) == 0:
        return False
    try:
        conn = sqlite3.connect(db_file)
        cur = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        exists = cur.fetchone() is not None
        conn.close()
        return exists
    except Exception:
        return False


# Đảm bảo database ở /tmp có quyền đọc ghi và đủ bảng trên môi trường Vercel Serverless
needs_bootstrap = False
if is_serverless:
    tmp_db = '/tmp/db.sqlite3'
    orig_db = BASE_DIR / 'db.sqlite3'
    if not os.path.exists(tmp_db) and orig_db.exists():
        try:
            shutil.copyfile(str(orig_db), tmp_db)
            os.chmod(tmp_db, 0o666)
        except Exception:
            pass
    needs_bootstrap = not _table_exists(tmp_db, 'facilities_facility')

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

def _bootstrap_serverless_db():
    """Chạy migrate và nạp đủ 6 cụm sân + mô tả + giá riêng + dịch vụ + coupon cực nhanh cho Vercel."""
    from django.core.management import call_command
    from django.db import connection, transaction

    with connection.cursor() as cursor:
        cursor.execute('PRAGMA synchronous = OFF;')
        cursor.execute('PRAGMA temp_store = MEMORY;')

    call_command('migrate', '--noinput', verbosity=0)

    from bookings.services import SlotGeneratorService

    orig_gen = SlotGeneratorService.__dict__.get('generate_slots_for_facility')
    # Bỏ qua sinh sẵn hàng nghìn slot lúc cold-start (views.py sẽ tự sinh on-demand theo ngày khách chọn)
    SlotGeneratorService.generate_slots_for_facility = classmethod(
        lambda cls, facility, target_date: 0
    )
    try:
        import seed_data
        import seed_map_facilities
        import seed_owners
        import seed_facility_descriptions
        import seed_facility_pricing
        import seed_coupons

        with transaction.atomic():
            seed_data.seed()
            seed_map_facilities.seed()
            seed_owners.seed_owners()
            seed_facility_descriptions.main()
            seed_facility_pricing.main()
            seed_coupons.main()
    finally:
        if orig_gen is not None:
            SlotGeneratorService.generate_slots_for_facility = orig_gen
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA synchronous = FULL;')


if needs_bootstrap:
    # Tạm bỏ qua DDL thủ công trong AppConfig.ready() để migrate tạo đủ bảng không bị xung đột
    _orig_argv = list(sys.argv)
    sys.argv = ['manage.py', 'migrate']
    try:
        application = get_wsgi_application()
        try:
            _bootstrap_serverless_db()
        except Exception:
            pass
    finally:
        sys.argv = _orig_argv
else:
    application = get_wsgi_application()

app = application
