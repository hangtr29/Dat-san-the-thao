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

if needs_bootstrap:
    # Tạm bỏ qua DDL thủ công trong AppConfig.ready() để migrate tạo đủ bảng không bị xung đột
    _orig_argv = list(sys.argv)
    sys.argv = ['manage.py', 'migrate']
    try:
        application = get_wsgi_application()
        from django.core.management import call_command

        call_command('migrate', '--noinput', verbosity=0)
        try:
            import seed_data

            seed_data.seed()
        except Exception:
            pass
    finally:
        sys.argv = _orig_argv
else:
    application = get_wsgi_application()

app = application
