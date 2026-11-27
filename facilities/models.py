import uuid
from datetime import time, datetime
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils.text import slugify

class FacilityStatus(models.TextChoices):
    PENDING_REVIEW = 'PENDING_REVIEW', 'Chờ duyệt hồ sơ'
    ACTIVE = 'ACTIVE', 'Đang hoạt động'
    SUSPENDED = 'SUSPENDED', 'Tạm ngưng hoạt động'


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
        """Lấy danh sách các cụm sân có phục vụ môn này (đã duyệt & đang hoạt động)"""
        facility_ids = self.courts.filter(is_active=True).values_list('facility_id', flat=True).distinct()
        return Facility.objects.filter(
            id__in=facility_ids,
            active_status=True,
            status=FacilityStatus.ACTIVE,
            is_verified=True,
        )

    def __str__(self):
        return self.name


class Facility(models.Model):
    """
    Tính đóng gói (Encapsulation): Cụm sân thể thao.
    Đóng gói thông tin tọa độ GPS, tích xanh xác thực KYC, điểm uy tín và tài khoản ngân hàng.
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
    hotline = models.CharField(max_length=20, blank=True, default='', verbose_name="Hotline chính thức")

    # Mục tiêu 1: Chống sân ma - Xác thực thực địa & Điểm uy tín
    is_verified = models.BooleanField(default=True, verbose_name="Đã xác thực (Tích xanh)", db_index=True)
    reputation_score = models.FloatField(default=5.0, verbose_name="Điểm uy tín (1-5)")
    status = models.CharField(
        max_length=20,
        choices=FacilityStatus.choices,
        default=FacilityStatus.ACTIVE,
        verbose_name="Trạng thái hoạt động",
        db_index=True
    )
    
    # Thông tin tài khoản ngân hàng của Chủ sân (Không qua trung gian giữ tiền)
    bank_name = models.CharField(max_length=50, verbose_name="Tên ngân hàng (VD: MBBank, VCB, ICB)")
    bank_account_no = models.CharField(max_length=50, verbose_name="Số tài khoản nhận tiền")
    bank_account_name = models.CharField(max_length=150, verbose_name="Tên chủ tài khoản")

    # Ảnh đại diện cụm sân và ảnh mã QR tùy chọn do chủ sân tự upload
    image = models.ImageField(upload_to='facilities/', null=True, blank=True, verbose_name="Ảnh bìa cụm sân")
    custom_qr_image = models.ImageField(upload_to='qrcodes/', null=True, blank=True, verbose_name="Ảnh mã QR thanh toán (Tùy chọn)")
    description = models.TextField(
        blank=True,
        default='',
        verbose_name="Mô tả giới thiệu cụm sân"
    )
    highlights = models.CharField(
        max_length=500,
        blank=True,
        default='',
        verbose_name="Điểm nổi bật (ngăn cách bằng dấu |)"
    )
    
    open_time = models.TimeField(default=time(6, 0), verbose_name="Giờ mở cửa")
    close_time = models.TimeField(default=time(22, 0), verbose_name="Giờ đóng cửa")
    active_status = models.BooleanField(default=True, verbose_name="Đang hoạt động", db_index=True)

    # Tọa độ GPS để tính khoảng cách thực tế từ vị trí người dùng
    latitude = models.FloatField(default=10.7769, verbose_name="Vĩ độ (GPS Latitude)")
    longitude = models.FloatField(default=106.7009, verbose_name="Kinh độ (GPS Longitude)")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày đăng ký")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        verbose_name = "Cụm sân"
        verbose_name_plural = "Danh sách cụm sân"
        ordering = ['-created_at']

    def can_accept_bookings(self) -> bool:
        """
        Tính đóng gói (Encapsulation): Kiểm tra cơ sở có đủ điều kiện nhận khách hay không.
        Điều kiện:
        1. Cụm sân ở trạng thái ACTIVE và active_status == True.
        2. Chủ sân sở hữu phải có gói duy trì nền tảng còn hạn (is_subscription_active() == True).
        """
        if self.status != FacilityStatus.ACTIVE or not self.active_status:
            return False
        if hasattr(self.owner, 'owner_profile'):
            return self.owner.owner_profile.is_subscription_active()
        return True

    def get_display_hotline(self) -> str:
        """Lấy số hotline chuẩn hiển thị cho khách"""
        return self.hotline or self.phone_contact

    def get_vietqr_bank_id(self) -> str:
        """
        Chuẩn hóa tên ngân hàng về mã chuẩn VietQR (đóng gói logic ánh xạ).
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
            'vietbank': 'vcb',
            'agribank': 'agribank',
            'sacombank': 'sacombank',
            'eximbank': 'eximbank',
        }
        return bank_map.get(bank_code, bank_code)

    def generate_vietqr_url(self, amount: int, memo: str) -> str:
        """
        Tính đóng gói (Encapsulation):
        Sinh mã VietQR ĐỘNG luôn kèm SỐ TIỀN và NỘI DUNG chuyển khoản (mã đơn),
        để khách không phải tự nhập tay số tiền & nội dung khi quét mã.

        LƯU Ý (đã sửa):
        - Ảnh QR tùy chỉnh do chủ sân tải lên là mã QR TĨNH, không mang số tiền/nội dung.
          Vì vậy ảnh đó CHỈ được dùng làm phương án dự phòng khi hệ thống chưa có đủ
          thông tin ngân hàng (thiếu tên ngân hàng hoặc số tài khoản).
        - Mặc định (có đủ thông tin ngân hàng) luôn dùng VietQR API động.
        """
        bank_id = self.get_vietqr_bank_id()
        account_no = self.bank_account_no.strip()

        # Đủ thông tin ngân hàng -> sinh QR động kèm số tiền & nội dung
        if bank_id and account_no:
            return (
                f"https://img.vietqr.io/image/{bank_id}-{account_no}-compact.png"
                f"?amount={int(amount)}&addInfo={memo}"
            )

        # Thiếu thông tin ngân hàng -> dùng QR tùy chỉnh của chủ sân (nếu có)
        if self.custom_qr_image:
            try:
                return self.custom_qr_image.url
            except Exception:
                pass

        return ''

    def is_open_at(self, check_time: time) -> bool:
        """Kiểm tra thời điểm có nằm trong khung giờ mở cửa không"""
        return self.open_time <= check_time < self.close_time

    @property
    def is_open_now(self) -> bool:
        """Cụm sân đang mở cửa tại thời điểm hiện tại"""
        from django.utils import timezone
        return self.is_open_at(timezone.localtime().time())

    def get_available_courts(self, date=None):
        """Lấy danh sách các sân đang hoạt động trong cụm sân"""
        return self.courts.filter(is_active=True)

    def get_cover_image_url(self) -> str:
        """Ảnh đại diện sân thi đấu sống động chuẩn phong cách thể thao Alobo"""
        if self.image:
            try:
                return self.image.url
            except Exception:
                pass
        name_lower = self.name.lower()
        if 'pickleball' in name_lower:
            return "https://images.unsplash.com/photo-1554068865-24cecd4e34b8?w=800&auto=format&fit=crop&q=80"
        return "https://images.unsplash.com/photo-1626224583764-f87db24ac4ea?w=800&auto=format&fit=crop&q=80"

    def get_distance_display(self, ref_lat=None, ref_lng=None) -> str:
        """Khoảng cách thực tế chuẩn theo vị trí người dùng (hiển thị gọn)"""
        km = self.get_distance_km(ref_lat=ref_lat, ref_lng=ref_lng)
        if km <= 0:
            return "0m"
        if km < 1:
            return f"{int(round(km * 1000))}m"
        if km < 10:
            return f"{km:.1f}km"
        return f"{int(round(km))}km"

    def get_distance_km(self, ref_lat=None, ref_lng=None) -> float:
        """
        Tính đóng gói (Encapsulation): Khoảng cách (km) từ vị trí người dùng (hoặc mốc
        mặc định trung tâm TP.HCM nếu chưa chia sẻ GPS) tới cụm sân, dùng công thức Haversine.
        """
        from math import radians, sin, cos, asin, sqrt
        if ref_lat is None or ref_lng is None:
            ref_lat, ref_lng = 10.7769, 106.7009
        lat1, lng1 = radians(float(ref_lat)), radians(float(ref_lng))
        lat2, lng2 = radians(float(self.latitude)), radians(float(self.longitude))
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
        return round(2 * 6371 * asin(sqrt(a)), 2)

    def get_highlight_list(self) -> list:
        """Trả về danh sách điểm nổi bật của cụm sân"""
        if not self.highlights:
            return []
        return [h.strip() for h in self.highlights.split('|') if h.strip()]

    def get_max_price(self) -> int:
        """Giá cao nhất / giờ của cụm sân (để cấu hình thanh kéo giá)"""
        prices = [rule.price_per_hour for rule in self.pricing_rules.all()]
        if not prices:
            return 0
        return int(max(prices))

    def get_addon_services(self):
        """Danh sách dịch vụ bổ sung đang cung cấp của cụm sân"""
        return self.addon_services.filter(is_active=True)

    def get_racket_services(self):
        """Danh sách dịch vụ thuê dụng cụ (vợt,...)"""
        return self.addon_services.filter(is_active=True, category='EQUIPMENT')

    def get_drink_services(self):
        """Danh sách dịch vụ thức uống"""
        return self.addon_services.filter(is_active=True, category='DRINK')

    def get_average_rating(self) -> float:
        """Tính đóng gói (Encapsulation): Điểm đánh giá trung bình từ các lượt đánh giá đã xác thực"""
        try:
            reviews = self.reviews.all()
            if not reviews.exists():
                return 5.0  # Mặc định sân đạt chuẩn 5.0 sao
            avg = reviews.aggregate(models.Avg('rating'))['rating__avg']
            return round(float(avg), 1) if avg else 5.0
        except Exception:
            return 5.0

    def get_total_reviews(self) -> int:
        """Tính đóng gói (Encapsulation): Tổng số lượt đánh giá đã xác thực từ khách chơi"""
        try:
            return self.reviews.count()
        except Exception:
            return 0

    def get_gallery_images(self) -> list:
        """
        Tính đóng gói (Encapsulation): Trả về danh sách ảnh của cụm sân cho bảng thông tin.
        Ưu tiên ảnh trong thư viện do chủ sân tải lên, sau đó tới ảnh bìa,
        cuối cùng là bộ ảnh dự phòng theo môn thể thao.
        """
        gallery = []
        for item in self.gallery_images.all():
            try:
                gallery.append({
                    'url': item.image.url,
                    'caption': item.caption or 'Ảnh cụm sân',
                })
            except Exception:
                continue

        if self.image:
            try:
                cover = {'url': self.image.url, 'caption': 'Ảnh bìa cụm sân'}
                if not gallery:
                    gallery.append(cover)
                else:
                    gallery.insert(0, cover)
            except Exception:
                pass

        return gallery

    def get_sport_names(self) -> list:
        """Trả về danh sách tên các môn thể thao đang phục vụ tại cụm sân (không trùng lặp)"""
        names = []
        for court in self.courts.filter(is_active=True).select_related('category'):
            label = court.category.name
            if label not in names:
                names.append(label)
        return names

    @property
    def is_published(self) -> bool:
        """
        Cụm sân đã được Ban quản trị duyệt và đang hiển thị công khai cho khách hàng.
        Chỉ cụm sân ACTIVE + đã tích xanh mới xuất hiện trên bản đồ & danh sách.
        """
        return (
            self.status == FacilityStatus.ACTIVE
            and self.active_status
            and self.is_verified
        )

    def get_approval_badge(self) -> tuple:
        """
        Trả về (nhãn, class màu) hiển thị trạng thái duyệt của cụm sân cho chủ sân.
        """
        return (self.approval_badge_label, self.approval_badge_color)

    @property
    def approval_badge_label(self) -> str:
        """Nhãn trạng thái duyệt hiển thị cho chủ sân"""
        if self.status == FacilityStatus.ACTIVE:
            return "Đã được duyệt"
        if self.status == FacilityStatus.SUSPENDED:
            return "Đã bị tạm ngưng"
        return "Đang chờ Ban quản trị duyệt"

    @property
    def approval_badge_color(self) -> str:
        """Class màu Tailwind tương ứng trạng thái duyệt"""
        if self.status == FacilityStatus.ACTIVE:
            return "bg-emerald-50 text-emerald-700 border-emerald-200"
        if self.status == FacilityStatus.SUSPENDED:
            return "bg-rose-50 text-rose-700 border-rose-200"
        return "bg-amber-50 text-amber-700 border-amber-200"

    def get_surface_types(self) -> list:
        """Trả về danh sách chất liệu mặt sân đang sử dụng (không trùng lặp)"""
        types = []
        for court in self.courts.filter(is_active=True):
            label = court.surface_type
            if label and label not in types:
                types.append(label)
        return types

    def get_min_price(self) -> int:
        """Tính đóng gói (Encapsulation): Giá thấp nhất / giờ của cụm sân (để hiển thị 'Giá từ')"""
        from django.utils import timezone
        weekday = timezone.localdate().weekday()
        prices = [
            rule.price_per_hour
            for rule in self.pricing_rules.filter(day_of_week=weekday)
        ]
        if not prices:
            prices = [rule.price_per_hour for rule in self.pricing_rules.all()]
        if not prices:
            return 0
        return int(min(prices))

    def __str__(self):
        return f"{self.name} - {self.address}"


class AddonService(models.Model):
    """
    Tính trừu tượng hóa (Abstraction): Dịch vụ bổ sung của từng CỤM SÂN.
    Ví dụ: Thuê vợt (tính theo lượt/người), Nước uống (tính theo chai/bình)...
    MỗI CỤM SÂN có bảng giá dịch vụ RIÊNG, chủ sân tự sửa trong Kênh Chủ Sân.
    """
    UNIT_CHOICES = [
        ('PER_BOOKING', 'Trọn đơn'),
        ('PER_HOUR', 'Theo giờ'),
        ('PER_PERSON', 'Theo người'),
        ('PER_ITEM', 'Theo món'),
    ]
    CATEGORY_CHOICES = [
        ('EQUIPMENT', 'Thuê dụng cụ'),
        ('DRINK', 'Thức uống'),
        ('FOOD', 'Đồ ăn'),
        ('OTHER', 'Khác'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        related_name='addon_services',
        verbose_name="Cụm sân"
    )
    name = models.CharField(max_length=120, verbose_name="Tên dịch vụ")
    description = models.CharField(max_length=250, blank=True, default='', verbose_name="Mô tả")
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='DRINK',
        verbose_name="Nhóm dịch vụ"
    )
    unit_type = models.CharField(
        max_length=20,
        choices=UNIT_CHOICES,
        default='PER_ITEM',
        verbose_name="Đơn vị tính"
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=0,
        verbose_name="Đơn giá (VNĐ)"
    )
    icon = models.CharField(max_length=40, blank=True, default='', verbose_name="Icon (FontAwesome)")
    is_active = models.BooleanField(default=True, verbose_name="Đang cung cấp")
    sort_order = models.IntegerField(default=0, verbose_name="Thứ tự hiển thị")

    class Meta:
        verbose_name = "Dịch vụ bổ sung"
        verbose_name_plural = "Danh mục dịch vụ bổ sung"
        ordering = ['category', 'sort_order', 'name']
        constraints = [
            models.UniqueConstraint(fields=['facility', 'name'], name='unique_facility_addon_name')
        ]

    def get_unit_label(self) -> str:
        """Nhãn đơn vị tính hiển thị trên giao diện"""
        return dict(self.UNIT_CHOICES).get(self.unit_type, '')

    def calculate_price(self, quantity: int = 1, hours: float = 0, people: int = 1) -> int:
        """
        Tính đóng gói (Encapsulation): Tính tiền dịch vụ theo đơn vị tính của từng sân.
        """
        qty = max(1, int(quantity or 1))
        if self.unit_type == 'PER_HOUR':
            factor = max(1, int(round(hours or 1)))
        elif self.unit_type == 'PER_PERSON':
            factor = max(1, int(people or 1))
        else:
            factor = qty
        return int(self.unit_price) * factor

    def __str__(self):
        return f"{self.name} ({self.facility.name}) - {int(self.unit_price):,} đ"


class Coupon(models.Model):
    """
    Tính đóng gói (Encapsulation): Mã giảm giá / khuyến mãi áp dụng khi khách đặt sân.
    Hỗ trợ giảm theo % hoặc số tiền cố định, có hạn sử dụng và thời hạn hiệu lực.
    """
    DISCOUNT_CHOICES = [
        ('PERCENT', 'Giảm (%)'),
        ('FIXED', 'Giảm số tiền (VNĐ)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=30, unique=True, verbose_name="Mã giảm giá")
    description = models.CharField(max_length=200, blank=True, default='', verbose_name="Mô tả chương trình")
    discount_type = models.CharField(
        max_length=10,
        choices=DISCOUNT_CHOICES,
        default='PERCENT',
        verbose_name="Loại giảm giá"
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=0,
        verbose_name="Giá trị giảm"
    )
    max_discount = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=0,
        verbose_name="Giảm tối đa (0 = không giới hạn)"
    )
    min_order_value = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=0,
        verbose_name="Đơn tối thiểu (VNĐ)"
    )
    usage_limit = models.IntegerField(default=0, verbose_name="Giới hạn số lượt dùng (0 = không giới hạn)")
    used_count = models.IntegerField(default=0, verbose_name="Đã dùng")
    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='coupons',
        verbose_name="Áp dụng cho cụm sân (trống = tất cả)"
    )
    valid_from = models.DateTimeField(null=True, blank=True, verbose_name="Bắt đầu hiệu lực")
    valid_to = models.DateTimeField(null=True, blank=True, verbose_name="Kết thúc hiệu lực")
    is_active = models.BooleanField(default=True, verbose_name="Đang áp dụng")

    class Meta:
        verbose_name = "Mã giảm giá"
        verbose_name_plural = "Danh sách mã giảm giá"
        ordering = ['-is_active', 'code']

    def is_valid_for(self, order_value, facility=None) -> tuple:
        """
        Tính đóng gói (Encapsulation): Kiểm tra mã có hợp lệ không.
        Trả về (hợp_lệ, thông_báo_lỗi).
        """
        from django.utils import timezone
        if not self.is_active:
            return False, "Mã giảm giá đã ngừng hoạt động."
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False, "Mã giảm giá chưa tới thời gian áp dụng."
        if self.valid_to and now > self.valid_to:
            return False, "Mã giảm giá đã hết hạn."
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False, "Mã giảm giá đã hết lượt sử dụng."
        if self.facility_id and facility is not None and self.facility_id != facility.id:
            return False, "Mã giảm giá không áp dụng cho cụm sân này."
        if order_value < self.min_order_value:
            return False, f"Đơn hàng tối thiểu {int(self.min_order_value):,} đ để dùng mã này."
        return True, ""

    def calculate_discount(self, order_value) -> int:
        """
        Tính đóng gói (Encapsulation): Tính số tiền được giảm từ mã giảm giá.
        """
        value = Decimal(str(order_value or 0))
        if self.discount_type == 'PERCENT':
            discount = value * (Decimal(str(self.discount_value)) / Decimal(100))
            if self.max_discount and discount > self.max_discount:
                discount = self.max_discount
        else:
            discount = Decimal(str(self.discount_value))
            if discount > value:
                discount = value
        return int(discount.quantize(Decimal('1')))

    def __str__(self):
        return f"{self.code} - {self.get_discount_type_display()}"


class FacilityGalleryImage(models.Model):
    """
    Thư viện ảnh của cụm sân (Tính trừu tượng hóa - Abstraction):
    Tách riêng ảnh tham khảo (gallery) khỏi ảnh bìa (cover image) để chủ sân
    có thể tải lên nhiều ảnh minh hoạ về sân, mặt sân, tiện ích...
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        related_name='gallery_images',
        verbose_name="Cụm sân"
    )
    image = models.ImageField(upload_to='facilities/gallery/', verbose_name="Ảnh")
    caption = models.CharField(max_length=150, blank=True, default='', verbose_name="Chú thích ảnh")
    sort_order = models.IntegerField(default=0, verbose_name="Thứ tự hiển thị")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tải lên")

    class Meta:
        verbose_name = "Ảnh thư viện cụm sân"
        verbose_name_plural = "Thư viện ảnh cụm sân"
        ordering = ['sort_order', '-created_at']

    def __str__(self):
        return f"{self.facility.name} - {self.caption or self.image.name}"

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
            if s.booking and s.booking.status in ['WAITING_APPROVAL', 'CONFIRMED', 'NEEDS_REUPLOAD']:
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


class Favorite(models.Model):
    """
    Tính đóng gói (Encapsulation): Lưu yêu thích cụm sân của khách hàng.
    Trước đây nút hình trái tim ở danh sách sân chỉ là giao diện, bấm vào không có tác dụng.
    Mỗi (user, facility) chỉ được lưu 1 lần (ràng buộc unique) - tránh trùng lặp.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='facility_favorites',
        verbose_name="Khách hàng"
    )
    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        related_name='favorited_by',
        verbose_name="Cụm sân"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian lưu yêu thích")

    class Meta:
        verbose_name = "Sân yêu thích"
        verbose_name_plural = "Danh sách sân yêu thích"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'facility'], name='unique_user_facility_favorite')
        ]

    def __str__(self):
        return f"{self.user.username} ♥ {self.facility.name}"


class FacilityReview(models.Model):
    """
    Tính đóng gói (Encapsulation): Đánh giá & Phản hồi chất lượng sân.
    Chỉ khách hàng có mã đơn đặt sân đã được duyệt thành công (CONFIRMED) mới được đánh giá (Chống spam).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name="Cụm sân"
    )
    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='review',
        verbose_name="Đơn đặt sân đã xác thực",
        null=True,
        blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='facility_reviews',
        verbose_name="Khách hàng"
    )
    reviewer_name = models.CharField(max_length=150, verbose_name="Tên người đánh giá")
    rating = models.IntegerField(
        choices=[
            (1, "1 Sao - Rất tệ"),
            (2, "2 Sao - Tệ"),
            (3, "3 Sao - Bình thường"),
            (4, "4 Sao - Tốt"),
            (5, "5 Sao - Xuất sắc"),
        ],
        default=5,
        verbose_name="Số sao đánh giá (1-5)"
    )
    comment = models.TextField(verbose_name="Nhận xét chất lượng sân")
    owner_reply = models.TextField(blank=True, null=True, verbose_name="Phản hồi của Chủ sân")
    owner_reply_at = models.DateTimeField(blank=True, null=True, verbose_name="Thời gian chủ sân phản hồi")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian đánh giá")

    class Meta:
        verbose_name = "Đánh giá cụm sân"
        verbose_name_plural = "Danh sách đánh giá cụm sân"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.rating}★] {self.facility.name} - {self.reviewer_name}"

