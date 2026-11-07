from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        """
        Tự động tạo bảng KYC/Subscription trong SQLite, khởi tạo các gói duy trì
        và kích hoạt tài khoản Chủ Sân (chusan / chusan123) sẵn sàng kiểm thử.
        """
        import sys
        if any(cmd in sys.argv for cmd in ['makemigrations', 'migrate', 'collectstatic', 'check']):
            return

        try:
            from django.db import connection
            from django.utils import timezone
            from datetime import timedelta
            from decimal import Decimal

            with connection.cursor() as cursor:
                # 1. Đảm bảo cấu trúc các bảng mới trong SQLite
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users_ownerprofile (
                        id char(32) NOT NULL PRIMARY KEY,
                        id_card_number varchar(25) NOT NULL,
                        id_card_front varchar(100),
                        id_card_back varchar(100),
                        business_license varchar(100),
                        bank_name varchar(50) NOT NULL,
                        bank_account_number varchar(50) NOT NULL,
                        bank_account_holder varchar(150) NOT NULL,
                        bank_qr_image varchar(100),
                        kyc_status varchar(20) NOT NULL,
                        kyc_rejection_reason text,
                        subscription_expires_at datetime,
                        created_at datetime NOT NULL,
                        updated_at datetime NOT NULL,
                        user_id char(32) NOT NULL UNIQUE REFERENCES users_user (id) DEFERRABLE INITIALLY DEFERRED
                    );
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users_subscriptionplan (
                        id char(32) NOT NULL PRIMARY KEY,
                        name varchar(100) NOT NULL,
                        duration_days integer NOT NULL,
                        price decimal NOT NULL,
                        description text NOT NULL,
                        is_active bool NOT NULL
                    );
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users_subscriptionorder (
                        id char(32) NOT NULL PRIMARY KEY,
                        order_code varchar(30) NOT NULL UNIQUE,
                        amount decimal NOT NULL,
                        payment_proof varchar(100),
                        status varchar(20) NOT NULL,
                        rejection_reason text,
                        created_at datetime NOT NULL,
                        approved_at datetime,
                        approved_by_id char(32) REFERENCES users_user (id) DEFERRABLE INITIALLY DEFERRED,
                        owner_id char(32) NOT NULL REFERENCES users_user (id) DEFERRABLE INITIALLY DEFERRED,
                        plan_id char(32) NOT NULL REFERENCES users_subscriptionplan (id) DEFERRABLE INITIALLY DEFERRED
                    );
                """)

                tables = connection.introspection.table_names(cursor)
                if 'users_user' in tables:
                    from users.models import User, UserRole, OwnerProfile, KYCStatus, SubscriptionPlan
                    from facilities.models import Facility

                    # 1. Khởi tạo tài khoản Quản trị viên Admin Web
                    admin_user = User.objects.filter(username='admin').first()
                    if not admin_user:
                        admin_user = User(
                            id=uuid.UUID('00000000-0000-0000-0000-000000000001'),
                            username='admin',
                            first_name='Quản Trị Viên',
                            last_name='Hệ Thống',
                            email='admin@sportbook.vn',
                            role=UserRole.ADMIN,
                            is_staff=True,
                            is_superuser=True,
                        )
                    admin_user.role = UserRole.ADMIN
                    admin_user.is_staff = True
                    admin_user.is_superuser = True
                    admin_user.set_password('admin123')
                    admin_user.save()

                    # 2. Khởi tạo tài khoản test chusan
                    owner = User.objects.filter(username='chusan').first()
                    if not owner:
                        owner = User(
                            id=uuid.UUID('11111111-1111-1111-1111-111111111111'),
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

                    # 3. Tạo hồ sơ KYC và kích hoạt gói duy trì 1 năm cho chusan
                    profile, _ = OwnerProfile.objects.get_or_create(
                        user=owner,
                        defaults={
                            'id_card_number': '079098765432',
                            'bank_name': 'MBBank',
                            'bank_account_number': '0988112233',
                            'bank_account_holder': 'CHU SAN SPORTBOOK',
                            'kyc_status': KYCStatus.KYC_VERIFIED,
                            'subscription_expires_at': timezone.now() + timedelta(days=365),
                        }
                    )
                    profile.kyc_status = KYCStatus.KYC_VERIFIED
                    if not profile.subscription_expires_at or profile.subscription_expires_at <= timezone.now():
                        profile.subscription_expires_at = timezone.now() + timedelta(days=365)
                    profile.save()

                    # 4. Gán tất cả Cụm sân cho chủ sân này
                    if 'facilities_facility' in tables:
                        Facility.objects.all().update(owner=owner)

                    # 5. Khởi tạo các Gói Thu Phí Duy Trì mẫu
                    plans_data = [
                        ("Gói Khởi Nghiệp (1 Tháng)", 30, Decimal('199000'), "Phù hợp chủ sân mới trải nghiệm hệ thống."),
                        ("Gói Tiêu Chuẩn (3 Tháng)", 90, Decimal('499000'), "Tiết kiệm 20% chi phí vận hành."),
                        ("Gói Doanh Nghiệp (1 Năm)", 365, Decimal('1490000'), "Đầy đủ tính năng, ưu tiên hiển thị Top 1 tìm kiếm."),
                    ]
                    for name, days, price, desc in plans_data:
                        SubscriptionPlan.objects.get_or_create(
                            name=name,
                            defaults={
                                'duration_days': days,
                                'price': price,
                                'description': desc,
                                'is_active': True,
                            }
                        )
        except Exception:
            pass


