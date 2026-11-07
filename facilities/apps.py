from django.apps import AppConfig
from django.db.models.signals import post_migrate


class FacilitiesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'facilities'

    def ready(self):
        """
        Đảm bảo bảng `facilities_facilityreview` và các trường mở rộng
        (ảnh sân, QR tùy chọn, phản hồi của chủ sân) luôn sẵn sàng trong SQLite.
        """
        from django.db import connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS facilities_facilityreview (
                        id char(32) NOT NULL PRIMARY KEY,
                        reviewer_name varchar(150) NOT NULL,
                        rating integer NOT NULL,
                        comment text NOT NULL,
                        created_at datetime NOT NULL,
                        booking_id char(32) UNIQUE REFERENCES bookings_booking (id) DEFERRABLE INITIALLY DEFERRED,
                        facility_id char(32) NOT NULL REFERENCES facilities_facility (id) DEFERRABLE INITIALLY DEFERRED,
                        user_id char(32) REFERENCES users_user (id) DEFERRABLE INITIALLY DEFERRED,
                        owner_reply text,
                        owner_reply_at datetime
                    );
                """)
                # Cập nhật thêm các cột mới nếu bảng đã tồn tại từ trước
                for col, typ in [('owner_reply', 'text'), ('owner_reply_at', 'datetime')]:
                    try:
                        cursor.execute(f"ALTER TABLE facilities_facilityreview ADD COLUMN {col} {typ};")
                    except Exception:
                        pass

                for col, typ in [('image', 'varchar(100)'), ('custom_qr_image', 'varchar(100)')]:
                    try:
                        cursor.execute(f"ALTER TABLE facilities_facility ADD COLUMN {col} {typ};")
                    except Exception:
                        pass
        except Exception:
            pass


