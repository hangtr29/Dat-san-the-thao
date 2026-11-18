"""
Script tạo tài khoản CHỦ SÂN riêng cho TỪNG cụm sân trong hệ thống.

Mỗi cụm sân sẽ có 1 tài khoản OWNER riêng, được QUẢN LÝ bởi tài khoản Admin
(trường User.managed_by) để quản trị viên có thể truy vết & hỗ trợ các chủ sân.

Quy tắc:
- Không ghi đè mật khẩu của tài khoản đã tồn tại (để người dùng tự đổi thoải mái).
- Tài khoản Admin được tạo/đảm bảo tồn tại & làm "quản trị viên phụ trách".
- Mật khẩu mặc định: <username>@sportbook (có thể đổi qua Kênh Chủ Sân).

Dùng: python seed_owners.py
"""
import os
import sys
import django
from datetime import timedelta

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from users.models import User, UserRole, OwnerProfile, KYCStatus
from facilities.models import Facility

User = get_user_model()

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'
DEFAULT_PASSWORD_SUFFIX = '@sportbook'


def slugify_username(name: str) -> str:
    """Chuyển tên cụm sân thành tên đăng nhập hợp lệ (chữ thường, không dấu, gạch nối)"""
    from django.utils.text import slugify
    base = slugify(name)[:20]
    return base or 'chusan'


def ensure_admin():
    """Đảm bảo tài khoản Admin tồn tại (không reset mật khẩu nếu đã có)"""
    admin = User.objects.filter(username=ADMIN_USERNAME).first()
    if not admin:
        admin = User(
            username=ADMIN_USERNAME,
            first_name='Quản Trị Viên',
            last_name='Hệ Thống',
            email='admin@sportbook.vn',
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        admin.set_password(ADMIN_PASSWORD)
        admin.save()
        print(f" -> ĐÃ TẠO tài khoản Admin: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
    else:
        print(f" -> Tài khoản Admin đã tồn tại: {ADMIN_USERNAME} (không reset mật khẩu)")
    return admin


def seed_owners():
    print("--- ĐANG TẠO TÀI KHOẢN CHỦ SÂN CHO TỪNG CỤM SÂN ---")
    admin = ensure_admin()

    used_usernames = set(User.objects.values_list('username', flat=True))
    results = []

    for fac in Facility.objects.all().order_by('name'):
        # Nếu sân đã có chủ sân riêng (không phải admin/chusan dùng chung) thì giữ nguyên
        current_owner = fac.owner
        if current_owner and current_owner.role == UserRole.OWNER \
                and current_owner.username not in ('chusan', 'chusan1') \
                and current_owner.managed_by_id == admin.id:
            print(f" -> BỎ QUA (đã có chủ sân riêng): {fac.name} -> {current_owner.username}")
            results.append((fac.name, current_owner.username, 'đã có'))
            continue

        username = slugify_username(fac.name)
        # Đảm bảo username duy nhất
        base = username
        counter = 1
        while username in used_usernames:
            counter += 1
            username = f"{base}{counter}"
        used_usernames.add(username)

        password = f"{username}{DEFAULT_PASSWORD_SUFFIX}"

        owner = User.objects.create_user(
            username=username,
            email=f"{username}@sportbook.vn",
            password=password,
            role=UserRole.OWNER,
            first_name='Chủ Sân',
            last_name=fac.name[:40],
            is_staff=True,
        )
        # Liên kết với tài khoản Admin phụ trách
        owner.managed_by = admin
        owner.save()

        # Hồ sơ KYC + gói dịch vụ cho chủ sân
        profile, _ = OwnerProfile.objects.get_or_create(
            user=owner,
            defaults={
                'id_card_number': '',
                'bank_name': fac.bank_name,
                'bank_account_number': fac.bank_account_no,
                'bank_account_holder': fac.bank_account_name,
                'kyc_status': KYCStatus.KYC_VERIFIED,
                'subscription_expires_at': timezone.now() + timedelta(days=365),
            }
        )
        profile.kyc_status = KYCStatus.KYC_VERIFIED
        if not profile.subscription_expires_at or profile.subscription_expires_at <= timezone.now():
            profile.subscription_expires_at = timezone.now() + timedelta(days=365)
        profile.save()

        # Gán cụm sân cho chủ sân mới
        fac.owner = owner
        fac.save()

        results.append((fac.name, username, password))
        print(f" -> ĐÃ TẠO: {fac.name}")
        print(f"      Tài khoản: {username} | Mật khẩu: {password} | Quản lý bởi: {admin.username}")

    # Gán các sân còn lại (nếu chưa có chủ) cho admin
    orphan = Facility.objects.filter(owner__isnull=True)
    if orphan.exists():
        orphan.update(owner=admin)

    print("=" * 70)
    print("✅ HOÀN TẤT! DANH SÁCH TÀI KHOẢN CHỦ SÂN")
    print("=" * 70)
    print("%-38s %-22s %s" % ("CỤM SÂN", "TÀI KHOẢN", "MẬT KHẨU"))
    print("-" * 70)
    for name, username, pwd in results:
        print("%-38s %-22s %s" % (name[:38], username, pwd))
    print("-" * 70)
    print("Tất cả các tài khoản trên đều được liên kết với Admin: %s" % ADMIN_USERNAME)
    print("=" * 70)


if __name__ == '__main__':
    seed_owners()
