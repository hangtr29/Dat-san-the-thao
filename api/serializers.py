"""
SERIALIZERS cho RESTful API (Django REST Framework).

Nguyên tắc:
- Chỉ xuất dữ liệu an toàn (không lộ bank_account_no, password, token).
- Sử dụng SerializerMethodField để đóng gói logic nghiệp vụ đã có sẵn trong Model
  (tôn trọng nguyên tắc Đóng gói của OOP thay vì viết lại logic).
"""
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from bookings.models import (
    Booking,
    BookingAddon,
    BookingSlot,
    Notification,
    RecurringBooking,
)
from facilities.models import (
    AddonService,
    Coupon,
    Court,
    Facility,
    FacilityGalleryImage,
    FacilityReview,
    Favorite,
    PricingRule,
    SportCategory,
)

User = get_user_model()


# ==========================================================================
# 1. NGƯỜI DÙNG & XÁC THỰC
# ==========================================================================

class UserSerializer(serializers.ModelSerializer):
    """Thông tin công khai của người dùng (không bao gồm mật khẩu)."""

    full_name = serializers.SerializerMethodField()
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'full_name', 'phone', 'role',
                  'role_display', 'is_staff', 'date_joined')
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class RegisterSerializer(serializers.ModelSerializer):
    """Đăng ký tài khoản mới qua API."""

    password = serializers.CharField(write_only=True, min_length=6,
                                     style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True,
                                             style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('username', 'email', 'phone', 'password',
                  'password_confirm', 'role')

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError(
                {'password_confirm': 'Mật khẩu xác nhận không khớp.'})
        if attrs.get('role') == 'ADMIN':
            raise serializers.ValidationError(
                {'role': 'Không thể tự đăng ký tài khoản Quản trị viên.'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm', None)
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Xác thực bằng tên đăng nhập / email + mật khẩu."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})


# ==========================================================================
# 2. DANH MỤC & CỤM SÂN
# ==========================================================================

class SportCategorySerializer(serializers.ModelSerializer):
    court_count = serializers.SerializerMethodField()
    facility_count = serializers.SerializerMethodField()

    class Meta:
        model = SportCategory
        fields = ('id', 'name', 'slug', 'icon_url', 'court_count', 'facility_count')
        read_only_fields = fields

    def get_court_count(self, obj):
        return obj.courts.filter(is_active=True).count()

    def get_facility_count(self, obj):
        return obj.get_active_facilities().count()


class PricingRuleSerializer(serializers.ModelSerializer):
    """Quy tắc định giá (giờ thường / giờ cao điểm)."""

    day_display = serializers.SerializerMethodField()

    class Meta:
        model = PricingRule
        fields = ('id', 'facility', 'day_of_week', 'day_display',
                  'start_time', 'end_time', 'price_per_hour')
        read_only_fields = fields

    def get_day_display(self, obj):
        return dict(obj._meta.get_field('day_of_week').choices).get(obj.day_of_week)


class AddonServiceSerializer(serializers.ModelSerializer):
    """Dịch vụ bổ sung (thuê vợt, thức uống...)."""

    unit_label = serializers.CharField(source='get_unit_label', read_only=True)

    class Meta:
        model = AddonService
        fields = ('id', 'facility', 'name', 'description', 'category',
                  'unit_type', 'unit_label', 'unit_price', 'icon',
                  'is_active', 'sort_order')
        read_only_fields = fields


class CouponSerializer(serializers.ModelSerializer):
    """Mã giảm giá - chỉ hiển thị mã công khai, KHÔNG lộ điều kiện nội bộ."""

    facility_name = serializers.CharField(source='facility.name', read_only=True,
                                          default=None)

    class Meta:
        model = Coupon
        fields = ('id', 'code', 'description', 'discount_type', 'discount_value',
                  'max_discount', 'min_order_value', 'facility', 'facility_name',
                  'valid_from', 'valid_to', 'is_active')
        read_only_fields = fields


class FacilityGalleryImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacilityGalleryImage
        fields = ('id', 'facility', 'image', 'caption', 'sort_order')
        read_only_fields = fields


class CourtSerializer(serializers.ModelSerializer):
    """Sân thi đấu thuộc cụm sân."""

    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Court
        fields = ('id', 'facility', 'category', 'category_name', 'court_name',
                  'court_area', 'surface_type', 'is_active')
        read_only_fields = fields


class FacilityReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacilityReview
        fields = ('id', 'facility', 'reviewer_name', 'rating', 'comment',
                  'owner_reply', 'owner_reply_at', 'created_at')
        read_only_fields = fields


class FacilityListSerializer(serializers.ModelSerializer):
    """
    Serializer rút gọn cho DANH SÁCH sân (dùng cho trang chủ / tìm kiếm).

    KHÔNG lộ thông tin nhạy cảm của chủ sân (số tài khoản ngân hàng).
    """

    owner_name = serializers.SerializerMethodField()
    category_names = serializers.SerializerMethodField()
    total_courts = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    min_price = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Facility
        fields = ('id', 'name', 'address', 'phone_contact', 'hotline',
                  'latitude', 'longitude', 'open_time', 'close_time',
                  'is_verified', 'reputation_score', 'image_url',
                  'status', 'active_status',
                  'owner_name', 'category_names', 'total_courts',
                  'average_rating', 'total_reviews', 'min_price',
                  'description', 'highlights', 'created_at')
        read_only_fields = fields

    def get_owner_name(self, obj):
        return obj.owner.get_full_name() or obj.owner.username

    def get_category_names(self, obj):
        return list(
            obj.courts.values_list('category__name', flat=True).distinct()
        )

    def get_total_courts(self, obj):
        return obj.courts.filter(is_active=True).count()

    def get_average_rating(self, obj):
        return obj.get_average_rating()

    def get_total_reviews(self, obj):
        return obj.get_total_reviews()

    def get_min_price(self, obj):
        """Giá thấp nhất trong các quy tắc định giá của cụm sân."""
        rule = obj.pricing_rules.order_by('price_per_hour').first()
        return int(rule.price_per_hour) if rule else None

    def get_image_url(self, obj):
        if not obj.image:
            return None
        try:
            request = self.context.get('request')
            url = obj.image.url
            return request.build_absolute_uri(url) if request else url
        except Exception:
            return None


class FacilityDetailSerializer(FacilityListSerializer):
    """Serializer CHI TIẾT: kèm sân con, bảng giá, dịch vụ, ảnh, coupon."""

    courts = CourtSerializer(many=True, read_only=True)
    pricing_rules = PricingRuleSerializer(many=True, read_only=True)
    addon_services = AddonServiceSerializer(many=True, read_only=True)
    gallery = FacilityGalleryImageSerializer(
        source='gallery_images', many=True, read_only=True)
    coupons = CouponSerializer(many=True, read_only=True)
    reviews = FacilityReviewSerializer(many=True, read_only=True)

    class Meta(FacilityListSerializer.Meta):
        fields = FacilityListSerializer.Meta.fields + (
            'courts', 'pricing_rules', 'addon_services', 'gallery',
            'coupons', 'reviews',
        )
        read_only_fields = fields


class FacilityRegisterSerializer(serializers.ModelSerializer):
    """Chủ sân đăng ký cụm sân mới qua API -> PENDING_REVIEW."""

    category_id = serializers.IntegerField(write_only=True, required=False)
    court_count = serializers.IntegerField(write_only=True, required=False, default=1)
    off_peak_price = serializers.DecimalField(write_only=True, required=False,
                                              max_digits=10, decimal_places=0)
    peak_price = serializers.DecimalField(write_only=True, required=False,
                                          max_digits=10, decimal_places=0)
    open_time = serializers.TimeField(write_only=True, required=False)
    close_time = serializers.TimeField(write_only=True, required=False)

    class Meta:
        model = Facility
        fields = ('id', 'name', 'address', 'phone_contact', 'hotline',
                  'bank_name', 'bank_account_no', 'bank_account_name',
                  'latitude', 'longitude', 'description', 'highlights',
                  'image', 'category_id', 'court_count', 'off_peak_price',
                  'peak_price', 'open_time', 'close_time')
        read_only_fields = ('id',)

    def validate_bank_account_no(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Số tài khoản không được để trống.')
        return value.strip()


# ==========================================================================
# 3. SLOT & ĐẶT SÂN
# ==========================================================================

class BookingSlotSerializer(serializers.ModelSerializer):
    """Khung giờ trống của một sân trong một ngày."""

    court_name = serializers.CharField(source='court.court_name', read_only=True)
    facility_id = serializers.UUIDField(source='court.facility_id', read_only=True)
    facility_name = serializers.CharField(source='court.facility.name', read_only=True)
    start_time_str = serializers.SerializerMethodField()
    end_time_str = serializers.SerializerMethodField()
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = BookingSlot
        fields = ('id', 'court', 'court_name', 'facility_id', 'facility_name',
                  'date', 'start_time', 'end_time', 'start_time_str',
                  'end_time_str', 'price', 'is_available')
        read_only_fields = fields

    def get_start_time_str(self, obj):
        return obj.start_time.strftime('%H:%M')

    def get_end_time_str(self, obj):
        return obj.end_time.strftime('%H:%M')


class BookingAddonSerializer(serializers.ModelSerializer):
    """Dịch vụ bổ sung đã chọn trong đơn (snapshot tên + giá tại thời điểm đặt)."""

    class Meta:
        model = BookingAddon
        fields = ('id', 'service', 'name', 'quantity', 'unit_price',
                  'subtotal', 'note')
        read_only_fields = fields


class BookingSerializer(serializers.ModelSerializer):
    """Chi tiết đơn đặt sân."""

    customer_name = serializers.CharField(source='display_customer_name', read_only=True)
    customer_phone = serializers.CharField(source='display_customer_phone', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    facility_name = serializers.SerializerMethodField()
    facility_id = serializers.SerializerMethodField()
    court_name = serializers.SerializerMethodField()
    slots = BookingSlotSerializer(many=True, read_only=True)
    addons = BookingAddonSerializer(many=True, read_only=True)
    payment_proof_url = serializers.SerializerMethodField()
    vietqr_url = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = ('id', 'booking_code', 'customer', 'customer_name',
                  'customer_phone', 'customer_note', 'total_amount',
                  'court_amount', 'addon_amount', 'discount_amount',
                  'coupon_code', 'status', 'status_display', 'reject_reason',
                  'is_recurring', 'recurring_group_id', 'recurrence_end_date',
                  'facility_id', 'facility_name', 'court_name',
                  'slots', 'addons', 'payment_proof_url', 'vietqr_url',
                  'created_at')
        read_only_fields = fields

    def get_facility_name(self, obj):
        facility = obj.facility
        return facility.name if facility else None

    def get_facility_id(self, obj):
        facility = obj.facility
        return facility.id if facility else None

    def get_court_name(self, obj):
        court = obj.court
        return court.court_name if court else None

    def get_payment_proof_url(self, obj):
        if not obj.payment_proof:
            return None
        try:
            request = self.context.get('request')
            url = obj.payment_proof.url
            return request.build_absolute_uri(url) if request else url
        except Exception:
            return None

    def get_vietqr_url(self, obj):
        """Sinh mã QR thanh toán động kèm số tiền & mã đơn (đóng gói logic của Model)."""
        facility = obj.facility
        if not facility:
            return None
        try:
            return facility.generate_vietqr_url(int(obj.total_amount), obj.booking_code)
        except Exception:
            return None


class BookingCreateSerializer(serializers.Serializer):
    """Tạo đơn đặt sân: khách chọn các slot theo id."""

    slot_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        help_text='Danh sách id của BookingSlot được chọn.',
    )
    customer_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    customer_phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    customer_note = serializers.CharField(required=False, allow_blank=True)

    def validate_slot_ids(self, value):
        if not value:
            raise serializers.ValidationError('Vui lòng chọn ít nhất 1 khung giờ.')
        return value


class BookingListSerializer(serializers.ModelSerializer):
    """Danh sách đơn rút gọn cho màn hình Lịch sử."""

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    facility_name = serializers.SerializerMethodField()
    court_name = serializers.SerializerMethodField()
    slot_summary = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = ('id', 'booking_code', 'status', 'status_display',
                  'total_amount', 'court_amount', 'addon_amount',
                  'discount_amount', 'facility_name', 'court_name',
                  'slot_summary', 'created_at')
        read_only_fields = fields

    def get_facility_name(self, obj):
        facility = obj.facility
        return facility.name if facility else None

    def get_court_name(self, obj):
        court = obj.court
        return court.court_name if court else None

    def get_slot_summary(self, obj):
        """Tóm tắt khung giờ: 'Sân 1 | 19/11 06:00-07:00 (+2)'"""
        slots = list(obj.slots.select_related('court').all())
        if not slots:
            return ''
        first = slots[0]
        extra = f' (+{len(slots) - 1})' if len(slots) > 1 else ''
        return (
            f"{first.court.court_name} | "
            f"{first.date.strftime('%d/%m')} "
            f"{first.start_time.strftime('%H:%M')}-{first.end_time.strftime('%H:%M')}"
            f"{extra}"
        )


class BookingPaymentProofSerializer(serializers.ModelSerializer):
    """Khách hàng tải ảnh bill thanh toán."""

    class Meta:
        model = Booking
        fields = ('booking_code', 'payment_proof')
        read_only_fields = ('booking_code',)


class BookingActionSerializer(serializers.Serializer):
    """Chủ sân duyệt / từ chối đơn."""

    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


# ==========================================================================
# 4. YÊU THÍCH, THÔNG BÁO, ĐẶT LỊCH CỐ ĐỊNH
# ==========================================================================

class FavoriteSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source='facility.name', read_only=True)

    class Meta:
        model = Favorite
        fields = ('id', 'facility', 'facility_name', 'created_at')
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_notification_type_display',
                                         read_only=True)

    class Meta:
        model = Notification
        fields = ('id', 'notification_type', 'type_display', 'title', 'message',
                  'link', 'is_read', 'created_at')
        read_only_fields = fields


class RecurringBookingSerializer(serializers.ModelSerializer):
    """Lịch đặt sân cố định theo tuần."""

    facility_name = serializers.SerializerMethodField()
    court_name = serializers.SerializerMethodField()
    day_display = serializers.SerializerMethodField()

    class Meta:
        model = RecurringBooking
        fields = ('id', 'group_id', 'facility', 'facility_name', 'court',
                  'court_name', 'weekday', 'day_display', 'start_time',
                  'end_time', 'start_date', 'end_date', 'total_amount',
                  'is_active')
        read_only_fields = fields

    def get_facility_name(self, obj):
        return obj.facility.name if obj.facility else None

    def get_court_name(self, obj):
        return obj.court.court_name if obj.court else None

    def get_day_display(self, obj):
        labels = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu',
                  'Thứ Bảy', 'Chủ Nhật']
        try:
            return labels[obj.weekday]
        except (IndexError, TypeError):
            return None
