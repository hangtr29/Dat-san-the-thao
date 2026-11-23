"""
VIEWS cho RESTful API (Django REST Framework + SimpleJWT).

Thiết kế:
- Tái sử dụng Service Layer sẵn có (BookingEngineService, NotificationService)
  thay vì viết lại logic nghiệp vụ -> nhất quán với kiến trúc OOP của dự án.
- Phân quyền theo vai trò (CUSTOMER / OWNER / ADMIN).
"""
from django.contrib.auth import authenticate, get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from bookings.models import (
    Booking,
    BookingSlot,
    Notification,
    RecurringBooking,
)
from bookings.services import BookingEngineService
from bookings.services_extras import NotificationService
from facilities.models import (
    AddonService,
    Coupon,
    Court,
    Facility,
    FacilityStatus,
    Favorite,
    PricingRule,
    SportCategory,
)

from .serializers import (
    AddonServiceSerializer,
    BookingActionSerializer,
    BookingCreateSerializer,
    BookingListSerializer,
    BookingPaymentProofSerializer,
    BookingSerializer,
    BookingSlotSerializer,
    CouponSerializer,
    CourtSerializer,
    FacilityDetailSerializer,
    FacilityListSerializer,
    FacilityRegisterSerializer,
    FavoriteSerializer,
    LoginSerializer,
    NotificationSerializer,
    PricingRuleSerializer,
    RecurringBookingSerializer,
    RegisterSerializer,
    SportCategorySerializer,
    UserSerializer,
)

User = get_user_model()


def _tokens_for(user):
    """Sinh cặp access/refresh token cho user."""
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


def _published_facilities():
    """Queryset cụm sân công khai (đã duyệt & đang hoạt động)."""
    return Facility.objects.filter(
        status=FacilityStatus.ACTIVE,
        active_status=True,
        is_verified=True,
    )


# ==========================================================================
# 1. XÁC THỰC
# ==========================================================================

class RegisterView(APIView):
    """POST /api/auth/register/ - Đăng ký tài khoản mới."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            'message': 'Đăng ký thành công.',
            'user': UserSerializer(user).data,
            'tokens': _tokens_for(user),
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST /api/auth/login/ - Đăng nhập, trả về access & refresh token."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username'].strip()
        password = serializer.validated_data['password']

        # Cho phép đăng nhập bằng email hoặc username
        user = None
        if '@' in username:
            user = User.objects.filter(email__iexact=username).first()
        if user is None:
            user = User.objects.filter(username__iexact=username).first()
        if user is not None:
            user = authenticate(username=user.username, password=password)

        if user is None:
            return Response(
                {'detail': 'Tên đăng nhập hoặc mật khẩu không đúng.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.is_active:
            return Response(
                {'detail': 'Tài khoản đã bị vô hiệu hóa.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            'message': f'Xin chào {user.get_full_name() or user.username}!',
            'user': UserSerializer(user).data,
            'tokens': _tokens_for(user),
        })


class LogoutView(APIView):
    """POST /api/auth/logout/ - Đăng xuất (blacklist refresh token)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            from rest_framework_simplejwt.token_blacklist.models import (
                BlacklistedToken, OutstandingToken,
            )
            token = request.data.get('refresh')
            if token:
                jti = RefreshToken(token).get('jti')
                out = OutstandingToken.objects.filter(jti=jti).first()
                if out:
                    BlacklistedToken.objects.get_or_create(token=out)
        except Exception:
            # Nếu chưa cài app blacklist thì bỏ qua (vẫn logout ở phía client)
            pass
        return Response({'message': 'Đã đăng xuất.'})


class CurrentUserView(APIView):
    """GET /api/auth/me/ - Thông tin user hiện tại (từ access token)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


# ==========================================================================
# 2. DANH MỤC & CỤM SÂN (Public Read)
# ==========================================================================

class SportCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/categories/ - Danh mục môn thể thao."""

    queryset = SportCategory.objects.all().order_by('name')
    serializer_class = SportCategorySerializer
    permission_classes = [AllowAny]


class FacilityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/facilities/          - Danh sách cụm sân (tìm kiếm, lọc, phân trang)
    GET /api/facilities/<id>/     - Chi tiết cụm sân (kèm sân, giá, dịch vụ, ảnh)
    """

    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = _published_facilities().select_related('owner').prefetch_related(
            'courts__category', 'pricing_rules', 'addon_services',
            'gallery_images', 'reviews',
        )
        params = self.request.query_params

        q = params.get('q')
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(address__icontains=q)
                | Q(description__icontains=q)
            )

        sport = params.get('sport')
        if sport:
            qs = qs.filter(courts__category__name__iexact=sport).distinct()

        lat = params.get('lat')
        lng = params.get('lng')
        if lat and lng:
            try:
                qs = qs.filter(latitude__gte=float(lat) - 0.5,
                               latitude__lte=float(lat) + 0.5,
                               longitude__gte=float(lng) - 0.5,
                               longitude__lte=float(lng) + 0.5)
            except (TypeError, ValueError):
                pass

        min_price = params.get('min_price')
        max_price = params.get('max_price')
        if min_price:
            try:
                qs = qs.filter(pricing_rules__price_per_hour__gte=float(min_price))
            except (TypeError, ValueError):
                pass
        if max_price:
            try:
                qs = qs.filter(pricing_rules__price_per_hour__lte=float(max_price))
            except (TypeError, ValueError):
                pass

        if params.get('verified') == 'true':
            qs = qs.filter(is_verified=True)

        return qs.distinct()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return FacilityDetailSerializer
        return FacilityListSerializer

    @action(detail=False, methods=['get'])
    def map(self, request):
        """GET /api/facilities/map/ - Dữ liệu bản đồ (marker cho Leaflet)."""
        data = [{
            'id': str(f.id),
            'name': f.name,
            'address': f.address,
            'latitude': f.latitude,
            'longitude': f.longitude,
            'hotline': f.get_display_hotline(),
            'is_verified': f.is_verified,
            'average_rating': f.get_average_rating(),
            'total_reviews': f.get_total_reviews(),
            'total_courts': f.courts.filter(is_active=True).count(),
        } for f in self.get_queryset()]
        return Response(data)


class CourtViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/courts/ - Danh sách sân thi đấu."""

    serializer_class = CourtSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Court.objects.filter(is_active=True).select_related(
            'facility', 'category').filter(facility__in=_published_facilities()).order_by('id')
        facility_id = self.request.query_params.get('facility')
        if facility_id:
            qs = qs.filter(facility_id=facility_id)
        return qs


class PricingRuleViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/pricing-rules/ - Bảng giá theo cụm sân."""

    serializer_class = PricingRuleSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = PricingRule.objects.select_related('facility').filter(
            facility__in=_published_facilities()).order_by('day_of_week', 'start_time')
        facility_id = self.request.query_params.get('facility')
        if facility_id:
            qs = qs.filter(facility_id=facility_id)
        return qs


class AddonServiceViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/addons/ - Dịch vụ bổ sung."""

    serializer_class = AddonServiceSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = AddonService.objects.filter(is_active=True).select_related('facility').filter(
            facility__in=_published_facilities()).order_by('category', 'sort_order', 'name')
        facility_id = self.request.query_params.get('facility')
        if facility_id:
            qs = qs.filter(facility_id=facility_id)
        return qs


class CouponViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/coupons/ - Danh sách mã giảm giá đang hiệu lực."""

    serializer_class = CouponSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        now = timezone.now()
        qs = Coupon.objects.filter(is_active=True).filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=now)
        ).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=now))
        facility_id = self.request.query_params.get('facility')
        if facility_id:
            qs = qs.filter(Q(facility_id=facility_id) | Q(facility__isnull=True))
        return qs

    @action(detail=False, methods=['get'])
    def validate_code(self, request):
        """
        GET /api/coupons/validate_code/?code=XXX&facility=<id>&amount=<số tiền>

        Kiểm tra mã có hợp lệ không (dùng chung logic `Coupon.is_valid_for`).
        """
        code = (request.query_params.get('code') or '').strip().upper()
        if not code:
            return Response({'detail': 'Thiếu mã giảm giá.'},
                            status=status.HTTP_400_BAD_REQUEST)

        coupon = Coupon.objects.filter(code__iexact=code).first()
        if not coupon:
            return Response({'ok': False, 'message': 'Mã giảm giá không tồn tại.'},
                            status=status.HTTP_200_OK)

        amount = request.query_params.get('amount')
        try:
            order_value = float(amount) if amount else 0
        except (TypeError, ValueError):
            order_value = 0

        facility = None
        facility_id = request.query_params.get('facility')
        if facility_id:
            facility = Facility.objects.filter(id=facility_id).first()

        valid, message = coupon.is_valid_for(order_value, facility)
        discount = coupon.calculate_discount(order_value) if valid else 0
        return Response({
            'ok': valid,
            'message': message if not valid else 'Mã giảm giá hợp lệ.',
            'discount_amount': int(discount),
            'coupon': CouponSerializer(coupon).data if valid else None,
        })


# ==========================================================================
# 3. SLOT & ĐẶT SÂN
# ==========================================================================

class SlotViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/slots/?facility=<id>&date=YYYY-MM-DD

    Trả về ma trận khung giờ trống của một cụm sân trong ngày.
    """

    serializer_class = BookingSlotSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = BookingSlot.objects.select_related(
            'court__facility', 'court__category').filter(
            court__facility__in=_published_facilities())

        params = self.request.query_params
        facility_id = params.get('facility')
        if facility_id:
            qs = qs.filter(court__facility_id=facility_id)

        date = params.get('date')
        if date:
            qs = qs.filter(date=date)

        court_id = params.get('court')
        if court_id:
            qs = qs.filter(court_id=court_id)

        # Chỉ trả về slot còn khả dụng (chưa trôi qua, chưa đặt, chưa bị lock)
        if params.get('available_only') == 'true':
            now = timezone.now()
            threshold = now - timezone.timedelta(minutes=BookingEngineService.LOCK_TIMEOUT_MINUTES)
            qs = qs.filter(
                Q(booking__isnull=True)
                | Q(booking__status__in=['PENDING_BILL', 'REJECTED', 'CANCELLED'])
            ).filter(
                Q(lock_time__isnull=True) | Q(lock_time__lte=threshold)
            ).exclude(date__lt=timezone.localdate())

        return qs.order_by('court_id', 'start_time')


class BookingViewSet(viewsets.ModelViewSet):
    """
    Đơn đặt sân.

    - GET    /api/bookings/            - Danh sách đơn của tôi
    - POST   /api/bookings/            - Tạo đơn (khóa slot 10 phút)
    - GET    /api/bookings/<code>/     - Chi tiết đơn
    - POST   /api/bookings/<code>/upload-proof/  - Tải ảnh bill
    - POST   /api/bookings/<code>/cancel/       - Khách hủy đơn
    - POST   /api/bookings/<code>/approve/      - Chủ sân duyệt
    - POST   /api/bookings/<code>/reject/       - Chủ sân từ chối
    """

    permission_classes = [IsAuthenticated]

    # Dùng MÃ ĐƠN (booking_code) thay vì UUID làm định danh trong URL
    # -> API thân thiện hơn: /api/bookings/BKQECE6DLM/
    lookup_field = 'booking_code'
    lookup_url_kwarg = 'booking_code'

    def get_queryset(self):
        user = self.request.user
        qs = Booking.objects.select_related('customer', 'coupon').prefetch_related(
            'slots__court__facility', 'slots__court__category', 'addons')

        if user.is_superuser or user.role == 'ADMIN':
            return qs
        if user.role == 'OWNER':
            # Chủ sân thấy đơn của các cụm sân mình sở hữu
            return qs.filter(slots__court__facility__owner=user).distinct()
        # Khách hàng thấy đơn của mình (+ đơn khách vãng lai đặt bằng số điện thoại)
        return qs.filter(Q(customer=user) | Q(customer_phone=getattr(user, 'phone', '') or ''))

    def get_serializer_class(self):
        if self.action == 'list':
            return BookingListSerializer
        return BookingSerializer

    def create(self, request, *args, **kwargs):
        """Tạo đơn đặt sân - tái sử dụng BookingEngineService."""
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ok, message, booking = BookingEngineService.lock_slots_and_create_booking(
            user=request.user,
            slot_ids=[str(s) for s in serializer.validated_data['slot_ids']],
            session_key=request.session.session_key,
            customer_name=serializer.validated_data.get('customer_name', ''),
            customer_phone=serializer.validated_data.get('customer_phone', ''),
        )
        if not ok:
            return Response({'detail': message, 'ok': False},
                            status=status.HTTP_400_BAD_REQUEST)

        # Ghi chú của khách (nếu có)
        note = serializer.validated_data.get('customer_note', '')
        if note:
            booking.customer_note = note
            booking.save(update_fields=['customer_note'])

        # Thông báo cho chủ sân có đơn mới
        NotificationService.notify_owner_new_booking(booking)

        return Response({
            'ok': True,
            'message': message,
            'booking': BookingSerializer(booking, context={'request': request}).data,
        }, status=status.HTTP_201_CREATED)

    def lookup(self, request, booking_code):
        """GET /api/bookings/lookup/<code>/ - Tra cứu đơn bằng mã (không cần đăng nhập)."""
        booking = Booking.objects.filter(booking_code__iexact=booking_code).first()
        if not booking:
            return Response({'detail': 'Không tìm thấy đơn đặt.'},
                            status=status.HTTP_404_NOT_FOUND)
        # Chỉ trả về thông tin tối thiểu cho người tra cứu
        facility = booking.facility
        return Response({
            'booking_code': booking.booking_code,
            'status': booking.status,
            'status_display': booking.get_status_display(),
            'total_amount': booking.total_amount,
            'created_at': booking.created_at,
            'facility_name': facility.name if facility else None,
            'facility_hotline': facility.get_display_hotline() if facility else None,
        })

    @action(detail=False, methods=['get'], url_path=r'lookup/(?P<booking_code>[A-Za-z0-9]+)',
            permission_classes=[AllowAny])
    def lookup_by_code(self, request, booking_code=None):
        return self.lookup(request, booking_code)

    @action(detail=True, methods=['post'], url_path='upload-proof')
    def upload_proof(self, request, booking_code=None):
        """Khách hàng tải ảnh bill thanh toán -> chuyển sang WAITING_APPROVAL."""
        booking = self.get_object()
        if booking.customer != request.user and not request.user.is_staff:
            return Response({'detail': 'Không có quyền thao tác đơn này.'},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = BookingPaymentProofSerializer(
            booking, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        proof = request.FILES.get('payment_proof')
        if not proof:
            return Response({'detail': 'Thiếu ảnh bill thanh toán.'},
                            status=status.HTTP_400_BAD_REQUEST)

        booking.upload_proof_and_submit(proof)
        return Response({
            'ok': True,
            'message': 'Đã gửi ảnh thanh toán. Chủ sân sẽ kiểm tra và phản hồi.',
            'booking': BookingSerializer(booking, context={'request': request}).data,
        })

    @action(detail=True, methods=['post'])
    def cancel(self, request, booking_code=None):
        """Khách hàng hủy đơn -> giải phóng slot & thông báo chủ sân."""
        booking = self.get_object()
        if booking.customer != request.user and not request.user.is_staff:
            return Response({'detail': 'Không có quyền hủy đơn này.'},
                            status=status.HTTP_403_FORBIDDEN)

        if booking.status == 'CONFIRMED':
            return Response(
                {'detail': 'Đơn đã xác nhận không thể hủy trực tuyến. '
                           'Vui lòng liên hệ chủ sân.'},
                status=status.HTTP_400_BAD_REQUEST)

        reason = (request.data.get('reason') or '').strip()

        # Tái sử dụng logic hủy đã đóng gói trong Model (Đóng gói - Encapsulation)
        cancelled = booking.cancel_booking()
        if not cancelled:
            # Trạng thái không cho hủy trực tuyến (VD: đang chờ chủ sân duyệt)
            booking.status = 'CANCELLED'
            booking.save(update_fields=['status'])
            for slot in booking.slots.all():
                slot.release_slot()

        NotificationService.notify_owner_booking_cancelled(booking, reason)
        return Response({
            'ok': True,
            'message': 'Đã hủy đơn đặt sân.',
            'booking': BookingSerializer(booking, context={'request': request}).data,
        })

    def _assert_owner_of_booking(self, request, booking):
        """Chỉ chủ sân sở hữu cụm sân hoặc admin mới được duyệt/từ chối."""
        if request.user.is_superuser or request.user.role == 'ADMIN':
            return True
        facility = booking.facility
        return bool(facility and facility.owner_id == request.user.id)

    @action(detail=True, methods=['post'])
    def approve(self, request, booking_code=None):
        """Chủ sân duyệt đơn -> CONFIRMED."""
        booking = self.get_object()
        if not self._assert_owner_of_booking(request, booking):
            return Response({'detail': 'Bạn không phải chủ sân của đơn này.'},
                            status=status.HTTP_403_FORBIDDEN)
        if not booking.approve_by_owner(request.user):
            return Response({'detail': 'Không thể duyệt đơn ở trạng thái hiện tại.'},
                            status=status.HTTP_400_BAD_REQUEST)
        NotificationService.notify_booking_status(booking, 'CONFIRMED')
        return Response({
            'ok': True,
            'message': 'Đã duyệt đơn đặt sân.',
            'booking': BookingSerializer(booking, context={'request': request}).data,
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, booking_code=None):
        """Chủ sân từ chối đơn (cho phép khách tải lại bill)."""
        booking = self.get_object()
        if not self._assert_owner_of_booking(request, booking):
            return Response({'detail': 'Bạn không phải chủ sân của đơn này.'},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = BookingActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get('reason', '')

        if not booking.reject_by_owner(reason):
            return Response({'detail': 'Không thể từ chối đơn ở trạng thái hiện tại.'},
                            status=status.HTTP_400_BAD_REQUEST)
        NotificationService.notify_booking_status(booking, 'NEEDS_REUPLOAD')
        return Response({
            'ok': True,
            'message': 'Đã từ chối đơn. Khách có thể tải lại bill.',
            'booking': BookingSerializer(booking, context={'request': request}).data,
        })


# ==========================================================================
# 4. YÊU THÍCH
# ==========================================================================

class FavoriteViewSet(viewsets.ModelViewSet):
    """
    GET    /api/favorites/       - Danh sách sân yêu thích
    POST   /api/favorites/       - Thêm (body: facility_id)
    DELETE /api/favorites/<id>/  - Xóa
    """

    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).select_related('facility')

    def create(self, request, *args, **kwargs):
        facility_id = request.data.get('facility_id')
        facility = Facility.objects.filter(id=facility_id).first()
        if not facility:
            return Response({'detail': 'Không tìm thấy cụm sân.'},
                            status=status.HTTP_404_NOT_FOUND)

        fav, created = Favorite.objects.get_or_create(
            user=request.user, facility=facility)
        return Response({
            'ok': True,
            'is_favorite': True,
            'created': created,
            'favorite': FavoriteSerializer(fav).data,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='toggle')
    def toggle(self, request):
        """POST /api/favorites/toggle/ - Bật/tắt yêu thích (body: facility_id)."""
        facility_id = request.data.get('facility_id')
        facility = Facility.objects.filter(id=facility_id).first()
        if not facility:
            return Response({'detail': 'Không tìm thấy cụm sân.'},
                            status=status.HTTP_404_NOT_FOUND)

        fav = Favorite.objects.filter(user=request.user, facility=facility).first()
        if fav:
            fav.delete()
            return Response({'ok': True, 'is_favorite': False,
                             'message': 'Đã bỏ lưu yêu thích.'})
        Favorite.objects.create(user=request.user, facility=facility)
        return Response({'ok': True, 'is_favorite': True,
                         'message': 'Đã lưu yêu thích.'})


# ==========================================================================
# 5. THÔNG BÁO
# ==========================================================================

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/notifications/ - Trung tâm thông báo."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        return Response({'count': NotificationService.unread_count(request.user)})

    @action(detail=False, methods=['post'], url_path='mark-read')
    def mark_read(self, request):
        """POST /api/notifications/mark-read/ - Đánh dấu đã xem (một hoặc tất cả)."""
        notification_id = request.data.get('notification_id')
        qs = Notification.objects.filter(user=request.user, is_read=False)
        if notification_id:
            qs = qs.filter(id=notification_id)
        updated = qs.update(is_read=True)
        return Response({'ok': True, 'updated': updated,
                         'unread_count': NotificationService.unread_count(request.user)})

    @action(detail=False, methods=['post'], url_path='mark-unread')
    def mark_unread(self, request):
        notification_id = request.data.get('notification_id')
        qs = Notification.objects.filter(user=request.user)
        if notification_id:
            qs = qs.filter(id=notification_id)
        updated = qs.update(is_read=False)
        return Response({'ok': True, 'updated': updated,
                         'unread_count': NotificationService.unread_count(request.user)})


# ==========================================================================
# 6. CHỦ SÂN
# ==========================================================================

class OwnerFacilityViewSet(viewsets.ModelViewSet):
    """
    Chủ sân đăng ký & quản lý cụm sân.

    - GET  /api/owner/facilities/          - Danh sách cụm sân của tôi
    - POST /api/owner/facilities/          - Đăng ký cụm sân mới (PENDING_REVIEW)
    - GET  /api/owner/facilities/<id>/     - Chi tiết (kèm sân con, giá, dịch vụ)
    - PUT  /api/owner/facilities/<id>/     - Cập nhật thông tin
    """

    serializer_class = FacilityDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Facility.objects.filter(owner=user).prefetch_related(
            'courts__category', 'pricing_rules', 'addon_services', 'gallery_images')
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return FacilityRegisterSerializer
        return FacilityDetailSerializer

    def create(self, request, *args, **kwargs):
        """Đăng ký cụm sân mới -> PENDING_REVIEW, chờ Admin duyệt."""
        if request.user.role not in ('OWNER', 'ADMIN'):
            return Response({'detail': 'Chỉ chủ sân mới có thể đăng ký cụm sân.'},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = FacilityRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Tách field không thuộc model
        category_id = data.pop('category_id', None)
        court_count = int(data.pop('court_count', 1) or 1)
        off_peak_price = data.pop('off_peak_price', 100000)
        peak_price = data.pop('peak_price', off_peak_price)
        open_time = data.pop('open_time', None)
        close_time = data.pop('close_time', None)

        category = SportCategory.objects.filter(id=category_id).first()
        if not category:
            return Response({'detail': 'Môn thể thao không hợp lệ.'},
                            status=status.HTTP_400_BAD_REQUEST)

        facility = Facility.objects.create(
            owner=request.user,
            status=FacilityStatus.PENDING_REVIEW,
            is_verified=False,
            active_status=False,
            **data,
        )
        if open_time:
            facility.open_time = open_time
        if close_time:
            facility.close_time = close_time
        facility.save()

        # Tạo sân con
        from facilities.models import Court, PricingRule
        for i in range(1, court_count + 1):
            Court.objects.create(
                facility=facility, category=category,
                court_name=f"Sân {i}",
                court_area=request.data.get('court_area', 'Sân trong nhà'),
                surface_type=request.data.get('surface_type', 'Thảm PVC chuyên dụng'),
                is_active=True,
            )

        # Bảng giá: giờ thường + giờ cao điểm cho 7 ngày
        from datetime import time as _time
        open_t = open_time or facility.open_time
        close_t = close_time or facility.close_time
        peak_start = _time(17, 0)
        if peak_start > close_t:
            peak_start = close_t
        for day in range(7):
            PricingRule.objects.create(
                facility=facility, day_of_week=day,
                start_time=open_t, end_time=peak_start,
                price_per_hour=off_peak_price)
            if peak_start < close_t:
                PricingRule.objects.create(
                    facility=facility, day_of_week=day,
                    start_time=peak_start, end_time=close_t,
                    price_per_hour=peak_price)

        # Sinh slot 14 ngày
        from datetime import timedelta
        from bookings.services import SlotGeneratorService
        today = timezone.localdate()
        for court in facility.courts.all():
            for i in range(14):
                SlotGeneratorService.generate_slots_for_court(
                    court=court, target_date=today + timedelta(days=i))

        # Thông báo cho admin
        for admin in User.objects.filter(is_superuser=True).exclude(pk=request.user.pk):
            NotificationService.notify(
                admin, 'SYSTEM',
                'Hồ sơ đăng ký cụm sân mới chờ duyệt',
                f"Chủ sân '{request.user.get_full_name() or request.user.username}' "
                f"vừa đăng ký cụm sân '{facility.name}'.",
                f'/admin/facilities/facility/?q={facility.name}',
            )

        return Response({
            'ok': True,
            'message': 'Đã gửi hồ sơ đăng ký cụm sân! Ban quản trị sẽ kiểm tra và phản hồi.',
            'facility': FacilityDetailSerializer(facility, context={'request': request}).data,
        }, status=status.HTTP_201_CREATED)


class OwnerBookingViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/owner/bookings/ - Các đơn đặt sân tới cụm sân của tôi."""

    serializer_class = BookingListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == 'ADMIN':
            qs = Booking.objects.all()
        else:
            qs = Booking.objects.filter(slots__court__facility__owner=user).distinct()
        status_param = self.request.query_params.get('status')
        if status_param and status_param != 'ALL':
            qs = qs.filter(status=status_param)
        return qs.prefetch_related('slots__court__facility')

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """GET /api/owner/bookings/stats/ - Thống kê nhanh cho dashboard chủ sân."""
        qs = self.get_queryset()
        from django.db.models import Sum
        agg = qs.aggregate(
            total=Count('id'),
            revenue=Sum('total_amount'),
        )
        return Response({
            'total_bookings': agg['total'] or 0,
            'total_revenue': int(agg['revenue'] or 0),
            'by_status': {
                row['status']: row['n'] for row in
                qs.values('status').annotate(n=Count('id'))
            },
        })

