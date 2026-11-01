"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Đảm bảo database ở /tmp có quyền đọc ghi trên môi trường Vercel Serverless
if os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or '/var/task' in str(BASE_DIR):
    tmp_db = '/tmp/db.sqlite3'
    orig_db = BASE_DIR / 'db.sqlite3'
    if not os.path.exists(tmp_db) and orig_db.exists():
        try:
            shutil.copyfile(str(orig_db), tmp_db)
            os.chmod(tmp_db, 0o666)
        except Exception:
            pass

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()
app = application
