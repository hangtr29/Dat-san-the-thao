"""
Script khởi tạo nhanh tài khoản Chủ Sân (OWNER) phục vụ kiểm thử:
- Tài khoản: chusan
- Mật khẩu: chusan123
- Quyền: Chủ sân (Role: OWNER), Nhân viên quản trị (is_staff: True)
- Đồng bộ: Gán tất cả Cụm sân hiện có cho tài khoản 'chusan'
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from users.models import User, UserRole
from facilities.models import Facility

def seed_owner():
    owner = User.objects.filter(username='chusan').first()
    if not owner:
        owner = User(
            username='chusan',
            first_name='Chủ Sân',
            last_name='SportBook',
            email='chusan@sportbook.vn',
            role=UserRole.OWNER,
            is_staff=True,
            is_superuser=True,
        )
    owner.role = UserRole.OWNER
    owner.is_staff = True
    owner.is_superuser = True
    owner.set_password('chusan123')
    owner.save()

    updated_count = Facility.objects.all().update(owner=owner)
    print("=" * 60)
    print("✅ ĐÃ KHỞI TẠO XONG TÀI KHOẢN CHỦ SÂN THÀNH CÔNG!")
    print(f"👉 Tên đăng nhập: chusan")
    print(f"👉 Mật khẩu:     chusan123")
    print(f"👉 Vai trò:      {owner.get_role_display()} (OWNER / Admin)")
    print(f"👉 Số cụm sân thuộc quyền sở hữu: {updated_count}")
    print("=" * 60)

if __name__ == '__main__':
    seed_owner()

