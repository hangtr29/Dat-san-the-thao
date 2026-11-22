import os
import shutil
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Đọc file .env đơn giản (KEY=VALUE) và nạp vào os.environ nếu chưa có.
    Giúp đặt GOOGLE_MAPS_API_KEY (và các biến khác) mà không cần cài thêm thư viện."""
    if not path.exists():
        return
    try:
        # Đọc với encoding='utf-8-sig' để loại bỏ BOM (PowerShell 5.1 hay thêm BOM khi ghi file)
        content = path.read_text(encoding='utf-8-sig')
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip().lstrip('\ufeff').strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass


_load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-&5#l!k^^75ljders%n$e+nm#40)k!3e3hg28$ff2)e$4o8^w&)'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = [
    'https://*.vercel.app',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
]

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Local Apps
    'users.apps.UsersConfig',
    'facilities.apps.FacilitiesConfig',
    'bookings.apps.BookingsConfig',
]

AUTH_USER_MODEL = 'users.User'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Chống cache trình duyệt khi đang phát triển (tự động tắt ở DEBUG=False)
    'config.middleware.NoCacheMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Ngày giờ thực tế cho header (Thứ Năm, 19/11/2026)
                'facilities.context_processors.site_datetime',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

db_path = BASE_DIR / 'db.sqlite3'

# Trên môi trường Vercel Serverless (read-only filesystem ở /var/task),
# ta tự động sao chép db.sqlite3 sang /tmp/db.sqlite3 (nơi có toàn quyền đọc/ghi).
is_serverless = os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or '/var/task' in str(BASE_DIR)

if is_serverless:
    tmp_db = '/tmp/db.sqlite3'
    if not os.path.exists(tmp_db):
        try:
            if db_path.exists():
                shutil.copyfile(str(db_path), tmp_db)
                os.chmod(tmp_db, 0o666)
            else:
                open(tmp_db, 'a').close()
                os.chmod(tmp_db, 0o666)
        except Exception:
            pass
    if os.path.exists(tmp_db):
        try:
            os.chmod(tmp_db, 0o666)
        except Exception:
            pass
        db_path = tmp_db

    # Lưu session vào signed cookies thay vì DB để tránh write database ở mỗi request trên serverless
    SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
    SESSION_COOKIE_AGE = 86400 * 7
    SESSION_SAVE_EVERY_REQUEST = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': db_path,
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'vi'

TIME_ZONE = 'Asia/Ho_Chi_Minh'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# ---------------------------------------------------------------------------
# BẢN ĐỒ (Leaflet) - Cấu hình nhà cung cấp tile
# ---------------------------------------------------------------------------
# Google Maps API key (tùy chọn). Để trống => dùng tile Google Maps công khai
# (mt*.google.com) hoặc OpenStreetMap dự phòng, KHÔNG cần key.
#   - Tạo key miễn phí: https://console.cloud.google.com/apis/credentials
#   - Bật API: Maps JavaScript API + Maps Static API + Geocoding API
#   - Giới hạn theo HTTP referrer để tránh bị lạm dụng
#   - Nạp qua biến môi trường: GOOGLE_MAPS_API_KEY=xxx  (không hardcode)
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '').strip()

# Cho phép dùng tile Google Maps công khai (không cần key) làm dự phòng.
# Lưu ý: đây là endpoint nội bộ của Google, không phải API chính thức được
# hỗ trợ cho sản phẩm thương mại — nên dùng cho demo/môi trường dev.
# Khi deploy production, hãy đặt GOOGLE_MAPS_API_KEY để dùng API chính thức.
GOOGLE_MAPS_KEYLESS_TILES = os.environ.get(
    'GOOGLE_MAPS_KEYLESS_TILES', 'true'
).lower() in ('true', '1', 'yes')


MEDIA_URL = '/media/'
if is_serverless:
    MEDIA_ROOT = '/tmp/media'
    os.makedirs(MEDIA_ROOT, exist_ok=True)
else:
    MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_URL = '/users/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
