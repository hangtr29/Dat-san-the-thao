from django.apps import AppConfig
from django.db.models.signals import post_migrate


class FacilitiesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'facilities'

    def ready(self):
        """
        Đảm bảo bảng `facilities_facilityreview` luôn sẵn sàng trong SQLite 
        ngay cả trên môi trường serverless (Vercel) khi chưa chạy migrate thủ công.
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
                        user_id char(32) REFERENCES users_user (id) DEFERRABLE INITIALLY DEFERRED
                    );
                """)
        except Exception:
            pass

