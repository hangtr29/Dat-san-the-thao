from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        """
        Tự động khởi tạo tài khoản Chủ Sân (chusan / chusan123) và gán quyền sở hữu
        toàn bộ Cụm sân khi ứng dụng khởi chạy.
        """
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                tables = connection.introspection.table_names(cursor)
                if 'users_user' in tables:
                    from users.models import User, UserRole
                    from facilities.models import Facility

                    owner, created = User.objects.get_or_create(
                        username='chusan',
                        defaults={
                            'first_name': 'Chủ Sân',
                            'last_name': 'SportBook',
                            'email': 'chusan@sportbook.vn',
                            'phone': '0988112233',
                            'role': UserRole.OWNER,
                            'is_staff': True,
                            'is_superuser': True,
                        }
                    )
                    # Đảm bảo mật khẩu và quyền chuẩn xác
                    owner.role = UserRole.OWNER
                    owner.is_staff = True
                    owner.is_superuser = True
                    owner.set_password('chusan123')
                    owner.save()

                    # Gán tất cả Cụm sân cho chủ sân này để có toàn quyền quản lý
                    if 'facilities_facility' in tables:
                        Facility.objects.all().update(owner=owner)
        except Exception:
            pass

