import uuid
from datetime import time, datetime
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils.text import slugify

class SportCategory(models.Model):
    """
    Tính đóng gói (Encapsulation): Danh mục bộ môn thể thao (Cầu lông, Pickleball, Bóng bàn).
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Tên môn thể thao")
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    icon_url = models.CharField(max_length=255, blank=True, verbose_name="Biểu tượng (Icon)")

    class Meta:
        verbose_name = "Môn thể thao"
        verbose_name_plural = "Danh mục môn thể thao"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def count_courts(self) -> int:
        """Đếm tổng số sân con đang hoạt động của bộ môn này"""
        return self.courts.filter(is_active=True).count()

    def count_facilities(self) -> int:
        """Đếm tổng số cụm sân (địa điểm) có phục vụ môn này"""
        return self.get_active_facilities().count()

    def get_active_facilities(self):
        """Lấy danh sách các cụm sân có phục vụ môn này"""
        facility_ids = self.courts.filter(is_active=True).values_list('facility_id', flat=True).distinct()
        return Facility.objects.filter(id__in=facility_ids, active_status=True)

    def __str__(self):
        return self.name

class Facility(models.Model):
    """
    Tính đóng gói (Encapsulation): Cụm sân thể thao.
    Đóng gói thông tin tài khoản ngân hàng của Chủ sân để phục vụ cơ chế sinh VietQR động.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='facilities',
        verbose_name="Chủ sân"
    )
    name = models.CharField(max_length=255, verbose_name="Tên cụm sân", db_index=True)
    address = models.TextField(verbose_name="Địa chỉ cụ thể")
    phone_contact = models.CharField(max_length=20, verbose_name="Hotline / Zalo liên hệ")
    
    # Thông tin tài khoản ngân hàng của Chủ sân (Không qua trung gian giữ tiền)
    bank_name = models.CharField(max_length=50, verbose_name="Tên ngân hàng (VD: MBBank, VCB, ICB)")
    bank_account_no = models.CharField(max_length=50, verbose_name="Số tài khoản nhận tiền")
    bank_account_name = models.CharField(max_length=150, verbose_name="Tên chủ tài khoản")
    
    open_time = models.TimeField(default=time(6, 0), verbose_name="Giờ mở cửa")
    close_time = models.TimeField(default=time(22, 0), verbose_name="Giờ đóng cửa")
    active_status = models.BooleanField(default=True, verbose_name="Đang hoạt động", db_index=True)

    # Tọa độ GPS để tính khoảng cách thực tế từ vị trí người dùng
    latitude = models.FloatField(default=10.7769, verbose_name="Vĩ độ (GPS Latitude)")
    longitude = models.FloatField(default=106.7009, verbose_name="Kinh độ (GPS Longitude)")

    class Meta:
        verbose_name = "Cụm sân"
        verbose_name_plural = "Danh sách cụm sân"

    def generate_vietqr_url(self, amount: int, memo: str) -> str:
        """
        Tính đóng gói (Encapsulation): Tự động sinh link ảnh VietQR API
        theo chuẩn https://img.vietqr.io/image/{bank_id}-{account_no}-compact.png?amount={total}&addInfo={booking_code}
        """
        bank_code = self.bank_name.strip().lower()
        # Chuẩn hóa một số tên ngân hàng thông dụng sang mã chuẩn VietQR
        bank_map = {
            'vietcombank': 'vcb',
            'vietinbank': 'icb',
            'mbbank': 'mb',
            'techcombank': 'tcb',
            'bidv': 'bidv',
            'tpbank': 'tpb',
            'vpbank': 'vpb',
            'acb': 'acb',
        }
        bank_id = bank_map.get(bank_code, bank_code)
        account_no = self.bank_account_no.strip()
        return f"https://img.vietqr.io/image/{bank_id}-{account_no}-compact.png?amount={int(amount)}&addInfo={memo}"

    def is_open_at(self, check_time: time) -> bool:
        """Kiểm tra thời điểm có nằm trong khung giờ mở cửa không"""
        return self.open_time <= check_time < self.close_time

    def get_available_courts(self, date=None):
        """Lấy danh sách các sân đang hoạt động trong cụm sân"""
        return self.courts.filter(is_active=True)

    def get_cover_image_url(self) -> str:
        """Ảnh đại diện sân thi đấu sống động chuẩn phong cách thể thao Alobo"""
        name_lower = self.name.lower()
        if 'pickleball' in name_lower:
            return "https://images.unsplash.com/photo-1554068865-24cecd4e34b8?w=800&auto=format&fit=crop&q=80"
        return "https://images.unsplash.com/photo-1626224583764-f87db24ac4ea?w=800&auto=format&fit=crop&q=80"

    def get_distance_display(self) -> str:
        """Khoảng cách mẫu hiển thị chuẩn ảnh tham khảo"""
        name_lower = self.name.lower()
        if 'sài gòn' in name_lower:
            return "2.3km"
        return "3.8km"

    def __str__(self):
        return f"{self.name} - {self.address}"

class Court(models.Model):
    """
    Đại diện cho từng đơn vị sân thi đấu thực tế trong một Cụm sân.
    """
    COURT_AREA_CHOICES = [
        ('Sân trong nhà', 'Sân trong nhà'),
        ('Sân ngoài trời', 'Sân ngoài trời'),
        ('Khu sân VIP', 'Khu sân VIP'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='courts', verbose_name="Cụm sân")
    category = models.ForeignKey(SportCategory, on_delete=models.CASCADE, related_name='courts', verbose_name="Môn thể thao")
    court_name = models.CharField(max_length=100, verbose_name="Tên sân (Sân 1, Sân 2...)")
    court_area = models.CharField(max_length=50, choices=COURT_AREA_CHOICES, default='Sân trong nhà', verbose_name="Khu vực (Trong nhà / Ngoài trời)")
    surface_type = models.CharField(max_length=50, blank=True, verbose_name="Chất liệu mặt sân (Thảm PVC, Sàn gỗ...)")
    is_active = models.BooleanField(default=True, verbose_name="Khả dụng")

    class Meta:
        verbose_name = "Sân đấu"
        verbose_name_plural = "Danh sách sân đấu"

    def is_slot_available(self, date, start_time, end_time) -> bool:
        """Kiểm tra slot giờ có bị đặt hoặc lock hay không"""
        existing_slots = self.slots.filter(
            date=date,
            start_time=start_time,
            end_time=end_time
        )
        for s in existing_slots:
            if s.booking and s.booking.status in ['WAITING_APPROVAL', 'CONFIRMED']:
                return False
            if s.is_locked():
                return False
        return True

    def __str__(self):
        return f"{self.facility.name} - {self.court_name} ({self.category.name})"

class PricingRule(models.Model):
    """
    Tính đa hình (Polymorphism): Áp dụng các quy tắc tính giá linh hoạt
    theo giờ Cao điểm / Thường / Cuối tuần.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='pricing_rules', verbose_name="Cụm sân")
    day_of_week = models.IntegerField(
        choices=[
            (0, "Thứ Hai"),
            (1, "Thứ Ba"),
            (2, "Thứ Tư"),
            (3, "Thứ Năm"),
            (4, "Thứ Sáu"),
            (5, "Thứ Bảy"),
            (6, "Chủ Nhật"),
        ],
        verbose_name="Ngày trong tuần (0-6)"
    )
    start_time = models.TimeField(verbose_name="Giờ bắt đầu")
    end_time = models.TimeField(verbose_name="Giờ kết thúc")
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Đơn giá / giờ (VNĐ)")

    class Meta:
        verbose_name = "Quy tắc định giá"
        verbose_name_plural = "Quy tắc định giá"

    def calculate_price(self, start_time: time, end_time: time) -> Decimal:
        """
        Tính đa hình (Polymorphism): Tính tiền cho khoảng thời gian giữa start_time và end_time.
        """
        # Quy đổi giờ sang phút
        duration_minutes = (end_time.hour * 60 + end_time.minute) - (start_time.hour * 60 + start_time.minute)
        hours = Decimal(duration_minutes) / Decimal(60)
        return (hours * self.price_per_hour).quantize(Decimal('1'))

    def __str__(self):
        day_label = dict(self._meta.get_field('day_of_week').choices).get(self.day_of_week)
        return f"{self.facility.name} [{day_label}: {self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}] -> {int(self.price_per_hour):,} đ/h"
