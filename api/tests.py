"""
Unit Tests cho RESTful API + Xác thực JWT.

Yêu cầu đề tài: "Hoàn thiện RESTful API và Xác thực (Sử dụng JWT / Sanctum)".

Bộ test bao phủ:
1. Xác thực JWT (đăng ký, đăng nhập, refresh, bảo vệ endpoint)
2. API công khai (đọc dữ liệu không cần token)
3. Slot & đặt sân (kèm cơ chế chống đặt trùng)
4. Yêu thích, thông báo, coupon
5. Phân quyền chủ sân
6. An toàn thông tin
"""
import json

from django.test import TestCase

from bookings.models import BookingSlot, Notification
from facilities.models import (
    Court,
    Coupon,
    Facility,
    FacilityStatus,
    PricingRule,
    SportCategory,
)
from users.models import User, UserRole


class ApiTestBase(TestCase):
    """Dữ liệu dùng chung cho các test API."""

    def setUp(self):
        self.category = SportCategory.objects.create(name='Cầu Lông Test')

        self.owner = User.objects.create_user(
            username='api_owner', password='password123',
            role=UserRole.OWNER, phone='0900111000')

        self.facility = Facility.objects.create(
            owner=self.owner,
            name='CLB API Test',
            address='123 Nguyễn Huệ, Quận 1, TP.HCM',
            phone_contact='0900123456',
            bank_name='MBBank',
            bank_account_no='0123456789',
            bank_account_name='NGUYEN VAN A',
            status=FacilityStatus.ACTIVE,
            is_verified=True,
            active_status=True,
        )
        self.court = Court.objects.create(
            facility=self.facility, category=self.category, court_name='Sân 1')

        for day in range(7):
            PricingRule.objects.create(
                facility=self.facility, day_of_week=day,
                start_time='06:00', end_time='17:00', price_per_hour=100000)
            PricingRule.objects.create(
                facility=self.facility, day_of_week=day,
                start_time='17:00', end_time='22:00', price_per_hour=150000)

        self.coupon = Coupon.objects.create(
            code='CHUYENCA', discount_type='FIXED', discount_value=50000,
            max_discount=50000, min_order_value=300000, usage_limit=200,
            is_active=True)

    # ---- Helper ----
    def api_post(self, url, data, token=None):
        headers = {'HTTP_AUTHORIZATION': 'Bearer %s' % token} if token else {}
        return self.client.post(url, data=json.dumps(data),
                                content_type='application/json', **headers)

    def api_get(self, url, token=None):
        headers = {'HTTP_AUTHORIZATION': 'Bearer %s' % token} if token else {}
        return self.client.get(url, **headers)

    def register(self, username='api_customer', phone='0900999000'):
        r = self.api_post('/api/auth/register/', {
            'username': username, 'phone': phone, 'password': 'password123',
            'password_confirm': 'password123', 'role': 'CUSTOMER'})
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()['tokens']['access']

    def create_facility(self, name='CLB Phụ'):
        """Tạo nhanh một cụm sân đang hoạt động."""
        return Facility.objects.create(
            owner=self.owner,
            name=name,
            address='456 Lê Lợi, Quận 1, TP.HCM',
            phone_contact='0900123456',
            bank_name='MBBank',
            bank_account_no='0123456789',
            bank_account_name='NGUYEN VAN A',
            status=FacilityStatus.ACTIVE,
            is_verified=True,
            active_status=True,
        )

    def create_slots(self, count=4):
        from datetime import timedelta
        from django.utils import timezone
        slots = []
        for i in range(count):
            # Mỗi slot 30 phút, liên tiếp từ 06:00
            total_minutes = 6 * 60 + i * 30
            start_h, start_m = divmod(total_minutes, 60)
            end_minutes = total_minutes + 30
            end_h, end_m = divmod(end_minutes, 60)
            slots.append(BookingSlot.objects.create(
                court=self.court,
                date=timezone.localdate() + timedelta(days=1),
                start_time='%02d:%02d' % (start_h, start_m),
                end_time='%02d:%02d' % (end_h, end_m),
                price=75000))
        return slots


# ==========================================================================
# 1. XÁC THỰC JWT
# ==========================================================================

class ApiAuthenticationTests(ApiTestBase):
    """Kiểm tra luồng đăng ký / đăng nhập / token."""

    def test_register_returns_tokens(self):
        r = self.api_post('/api/auth/register/', {
            'username': 'newuser', 'phone': '0900222333', 'password': 'password123',
            'password_confirm': 'password123', 'role': 'CUSTOMER'})
        self.assertEqual(r.status_code, 201)
        data = r.json()
        self.assertIn('access', data['tokens'])
        self.assertIn('refresh', data['tokens'])
        self.assertEqual(data['user']['username'], 'newuser')
        self.assertEqual(data['user']['role'], 'CUSTOMER')

    def test_register_never_exposes_password(self):
        r = self.api_post('/api/auth/register/', {
            'username': 'newuser2', 'phone': '0900222444', 'password': 'password123',
            'password_confirm': 'password123', 'role': 'CUSTOMER'})
        self.assertNotIn('password', r.json()['user'])

    def test_register_rejects_mismatched_password(self):
        r = self.api_post('/api/auth/register/', {
            'username': 'newuser3', 'phone': '0900222555', 'password': 'password123',
            'password_confirm': 'khac', 'role': 'CUSTOMER'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('password_confirm', r.json())

    def test_register_rejects_admin_role(self):
        """Không cho tự đăng ký tài khoản Quản trị viên (bảo mật)"""
        r = self.api_post('/api/auth/register/', {
            'username': 'fakeadmin', 'phone': '0900222666', 'password': 'password123',
            'password_confirm': 'password123', 'role': 'ADMIN'})
        self.assertEqual(r.status_code, 400)

    def test_login_returns_valid_access_token(self):
        self.register('loginuser', '0900333444')
        r = self.api_post('/api/auth/login/', {
            'username': 'loginuser', 'password': 'password123'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('access', r.json()['tokens'])

    def test_login_with_wrong_password_fails(self):
        self.register('loginuser2', '0900333555')
        r = self.api_post('/api/auth/login/', {
            'username': 'loginuser2', 'password': 'sai_mat_khau'})
        self.assertEqual(r.status_code, 400)

    def test_login_with_email(self):
        self.register('emailuser', '0900444666')
        User.objects.filter(username='emailuser').update(email='emailuser@test.com')
        r = self.api_post('/api/auth/login/', {
            'username': 'emailuser@test.com', 'password': 'password123'})
        self.assertEqual(r.status_code, 200)

    def test_refresh_token_issues_new_access_token(self):
        self.register('refreshuser', '0900555777')
        r = self.api_post('/api/auth/login/', {
            'username': 'refreshuser', 'password': 'password123'})
        refresh = r.json()['tokens']['refresh']
        r2 = self.api_post('/api/auth/token/refresh/', {'refresh': refresh})
        self.assertEqual(r2.status_code, 200)
        self.assertIn('access', r2.json())

    def test_protected_endpoint_requires_token(self):
        r = self.api_get('/api/bookings/')
        self.assertEqual(r.status_code, 401)

    def test_protected_endpoint_accepts_token(self):
        token = self.register()
        r = self.api_get('/api/bookings/', token=token)
        self.assertEqual(r.status_code, 200)

    def test_current_user_endpoint(self):
        token = self.register('meuser', '0900666888')
        r = self.api_get('/api/auth/me/', token=token)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['username'], 'meuser')

    def test_invalid_token_is_rejected(self):
        r = self.api_get('/api/bookings/', token='token.khong.hop.le')
        self.assertIn(r.status_code, (401, 403))


# ==========================================================================
# 2. API CÔNG KHAI
# ==========================================================================

class ApiPublicDataTests(ApiTestBase):
    """Các endpoint đọc dữ liệu không cần token."""

    def test_categories_public(self):
        r = self.api_get('/api/categories/')
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.json()['count'], 1)

    def test_facilities_public(self):
        r = self.api_get('/api/facilities/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['count'], 1)

    def test_facilities_support_page_size_param(self):
        """Client có thể tùy chỉnh số item/trang bằng ?page_size="""
        # Tạo thêm vài cụm sân để có nhiều hơn 1 trang
        for i in range(3):
            self.create_facility(name='Cum san phu %d' % i)

        r = self.api_get('/api/facilities/?page_size=2')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['count'], 4)
        self.assertEqual(len(body['results']), 2)
        self.assertIsNotNone(body['next'])

    def test_facilities_page_size_capped(self):
        """page_size vượt quá max sẽ bị giới hạn (max_page_size=100)"""
        r = self.api_get('/api/facilities/?page_size=9999')
        self.assertEqual(r.status_code, 200)
        self.assertLessEqual(len(r.json()['results']), 100)

    def test_facility_list_hides_bank_info(self):
        """Danh sách KHÔNG được lộ số tài khoản ngân hàng của chủ sân"""
        r = self.api_get('/api/facilities/')
        item = r.json()['results'][0]
        self.assertNotIn('bank_account_no', item)
        self.assertNotIn('bank_account_name', item)

    def test_facility_detail_includes_nested_data(self):
        r = self.api_get('/api/facilities/%s/' % self.facility.id)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['courts'])
        self.assertTrue(data['pricing_rules'])

    def test_facility_map_returns_markers(self):
        r = self.api_get('/api/facilities/map/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data)
        self.assertIn('latitude', data[0])
        self.assertIn('longitude', data[0])

    def test_courts_pricing_addons_coupons_public(self):
        for url in ('/api/courts/', '/api/pricing-rules/',
                    '/api/addons/', '/api/coupons/'):
            r = self.api_get(url)
            self.assertEqual(r.status_code, 200, url)

    def test_facility_search_filter(self):
        r = self.api_get('/api/facilities/?q=khongcothat12345')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['count'], 0)

    def test_facility_search_by_name(self):
        r = self.api_get('/api/facilities/?q=API Test')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['count'], 1)

    def test_pending_facility_hidden_from_public_api(self):
        """Cụm sân CHỜ DUYỆT không được lộ qua API công khai"""
        Facility.objects.create(
            owner=self.owner, name='CLB Cho Duyet', address='456 Duong X',
            phone_contact='0900999888', bank_name='MBBank',
            bank_account_no='9876543210', bank_account_name='B',
            status=FacilityStatus.PENDING_REVIEW, is_verified=False,
            active_status=False)
        r = self.api_get('/api/facilities/')
        names = [f['name'] for f in r.json()['results']]
        self.assertNotIn('CLB Cho Duyet', names)


# ==========================================================================
# 3. SLOT & ĐẶT SÂN
# ==========================================================================

class ApiBookingTests(ApiTestBase):
    """Luồng đặt sân qua API."""

    def setUp(self):
        super().setUp()
        self.token = self.register()
        self.slots = self.create_slots(4)

    def test_slots_endpoint(self):
        r = self.api_get('/api/slots/?facility=%s' % self.facility.id)
        self.assertEqual(r.status_code, 200)
        # Endpoint slots KHÔNG phân trang (trả về mảng) vì cần đủ ma trận
        # khung giờ cho toàn bộ sân trong ngày.
        slots = r.json()
        self.assertIsInstance(slots, list)
        self.assertTrue(slots)
        first = slots[0]
        self.assertIn('is_available', first)
        self.assertIn('start_time_str', first)

    def test_slots_endpoint_filters_by_date(self):
        from bookings.models import BookingSlot
        from django.utils import timezone
        import datetime

        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        BookingSlot.objects.filter(court__facility=self.facility).update(date=tomorrow)

        r = self.api_get(
            '/api/slots/?facility=%s&date=%s' % (self.facility.id, tomorrow))
        self.assertEqual(r.status_code, 200)
        slots = r.json()
        self.assertIsInstance(slots, list)
        self.assertTrue(slots)
        self.assertTrue(all(s['date'] == tomorrow.isoformat() for s in slots))

    def test_create_booking(self):
        slot_ids = [str(s.id) for s in self.slots[:2]]
        r = self.api_post('/api/bookings/', {
            'slot_ids': slot_ids, 'customer_name': 'Khach API',
            'customer_phone': '0900999000'}, token=self.token)
        self.assertEqual(r.status_code, 201, r.content)
        booking = r.json()['booking']
        self.assertEqual(booking['status'], 'PENDING_BILL')
        self.assertEqual(len(booking['slots']), 2)
        self.assertTrue(booking['vietqr_url'])

    def test_create_booking_rejects_empty_slots(self):
        r = self.api_post('/api/bookings/', {'slot_ids': []}, token=self.token)
        self.assertEqual(r.status_code, 400)

    def test_create_booking_rejects_invalid_uuid(self):
        r = self.api_post('/api/bookings/', {'slot_ids': ['khong-hop-le']},
                          token=self.token)
        self.assertEqual(r.status_code, 400)

    def test_create_booking_requires_auth(self):
        r = self.api_post('/api/bookings/', {
            'slot_ids': [str(self.slots[0].id)]})
        self.assertEqual(r.status_code, 401)

    def test_other_user_cannot_book_locked_slot(self):
        """Chống đặt trùng: khách khác không thể đặt slot đang bị giữ"""
        slot_ids = [str(self.slots[0].id)]
        r = self.api_post('/api/bookings/', {'slot_ids': slot_ids},
                          token=self.token)
        self.assertEqual(r.status_code, 201)

        other = self.register('otheruser', '0900777888')
        r2 = self.api_post('/api/bookings/', {'slot_ids': slot_ids}, token=other)
        self.assertEqual(r2.status_code, 400)
        self.assertIn('giữ chỗ', r2.json()['detail'])

    def test_booking_detail_uses_booking_code(self):
        slot_ids = [str(self.slots[0].id)]
        r = self.api_post('/api/bookings/', {'slot_ids': slot_ids},
                          token=self.token)
        code = r.json()['booking']['booking_code']

        r2 = self.api_get('/api/bookings/%s/' % code, token=self.token)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['booking_code'], code)

    def test_booking_lookup_is_public(self):
        """Tra cứu đơn bằng mã không cần đăng nhập (khách vãng lai)"""
        r = self.api_post('/api/bookings/', {
            'slot_ids': [str(self.slots[0].id)]}, token=self.token)
        code = r.json()['booking']['booking_code']

        r2 = self.api_get('/api/bookings/lookup/%s/' % code)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['status'], 'PENDING_BILL')
        # Không lộ thông tin nhạy cảm
        self.assertNotIn('customer_phone', r2.json())

    def test_booking_lookup_unknown_code_404(self):
        r = self.api_get('/api/bookings/lookup/KHONGCO/')
        self.assertEqual(r.status_code, 404)

    def test_customer_can_cancel_booking(self):
        r = self.api_post('/api/bookings/', {
            'slot_ids': [str(self.slots[0].id)]}, token=self.token)
        code = r.json()['booking']['booking_code']

        r2 = self.api_post('/api/bookings/%s/cancel/' % code, {}, token=self.token)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['booking']['status'], 'CANCELLED')
        # Slot phải được giải phóng
        self.slots[0].refresh_from_db()
        self.assertFalse(self.slots[0].is_locked())

    def test_other_user_cannot_cancel_booking(self):
        """User khác KHÔNG được hủy đơn của người khác
        (API trả 404 vì đơn không nằm trong tập dữ liệu của user đó)"""
        r = self.api_post('/api/bookings/', {
            'slot_ids': [str(self.slots[0].id)]}, token=self.token)
        code = r.json()['booking']['booking_code']

        other = self.register('otheruser2', '0900888999')
        r2 = self.api_post('/api/bookings/%s/cancel/' % code, {}, token=other)
        self.assertIn(r2.status_code, (403, 404))

    def test_owner_can_approve_booking(self):
        """Chủ sân duyệt đơn (sau khi khách nộp bill -> WAITING_APPROVAL)"""
        r = self.api_post('/api/bookings/', {
            'slot_ids': [str(self.slots[0].id)]}, token=self.token)
        code = r.json()['booking']['booking_code']

        # Khách nộp bill -> chuyển sang WAITING_APPROVAL
        self.assertEqual(self._upload_proof(code, self.token).status_code, 200)

        self.client.force_login(self.owner)
        r2 = self.client.post('/api/bookings/%s/approve/' % code,
                              data=json.dumps({}),
                              content_type='application/json')
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertEqual(r2.json()['booking']['status'], 'CONFIRMED')

    def test_customer_cannot_approve_own_booking(self):
        """Khách hàng không được tự duyệt đơn của mình"""
        r = self.api_post('/api/bookings/', {
            'slot_ids': [str(self.slots[0].id)]}, token=self.token)
        code = r.json()['booking']['booking_code']

        r2 = self.api_post('/api/bookings/%s/approve/' % code, {}, token=self.token)
        self.assertEqual(r2.status_code, 403)

    def test_owner_can_reject_booking_with_reason(self):
        r = self.api_post('/api/bookings/', {
            'slot_ids': [str(self.slots[0].id)]}, token=self.token)
        code = r.json()['booking']['booking_code']

        self.assertEqual(self._upload_proof(code, self.token).status_code, 200)

        self.client.force_login(self.owner)
        r2 = self.client.post('/api/bookings/%s/reject/' % code,
                              data=json.dumps({'reason': 'Bill sai so tien'}),
                              content_type='application/json')
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertEqual(r2.json()['booking']['status'], 'NEEDS_REUPLOAD')

    def _upload_proof(self, booking_code, token=None):
        """Khách hàng tải ảnh bill thanh toán (multipart)"""
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Tạo file PNG 1x1 hợp lệ
        png = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
               b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00'
               b'\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
        proof = SimpleUploadedFile('bill.png', png, content_type='image/png')
        headers = {'HTTP_AUTHORIZATION': 'Bearer %s' % token} if token else {}
        return self.client.post('/api/bookings/%s/upload-proof/' % booking_code,
                                {'payment_proof': proof}, **headers)


# ==========================================================================
# 4. YÊU THÍCH, THÔNG BÁO, COUPON
# ==========================================================================

class ApiEngagementTests(ApiTestBase):
    """Yêu thích, thông báo, mã giảm giá."""

    def setUp(self):
        super().setUp()
        self.token = self.register()

    def test_favorite_toggle(self):
        r = self.api_post('/api/favorites/toggle/',
                          {'facility_id': str(self.facility.id)}, token=self.token)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['is_favorite'])

        r2 = self.api_post('/api/favorites/toggle/',
                           {'facility_id': str(self.facility.id)}, token=self.token)
        self.assertFalse(r2.json()['is_favorite'])

    def test_favorite_list(self):
        self.api_post('/api/favorites/toggle/',
                      {'facility_id': str(self.facility.id)}, token=self.token)
        r = self.api_get('/api/favorites/', token=self.token)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['count'], 1)

    def test_favorite_requires_auth(self):
        r = self.api_post('/api/favorites/toggle/',
                          {'facility_id': str(self.facility.id)})
        self.assertEqual(r.status_code, 401)

    def test_notifications_endpoint(self):
        r = self.api_get('/api/notifications/', token=self.token)
        self.assertEqual(r.status_code, 200)

    def test_unread_count(self):
        r = self.api_get('/api/notifications/unread_count/', token=self.token)
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json()['count'], int)

    def test_mark_notification_read(self):
        user = User.objects.get(username='api_customer')
        n = Notification.objects.create(
            user=user, notification_type='SYSTEM', title='Test')
        r = self.api_post('/api/notifications/mark-read/',
                          {'notification_id': str(n.id)}, token=self.token)
        self.assertEqual(r.status_code, 200)
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_coupon_validate_success(self):
        r = self.api_get('/api/coupons/validate_code/?code=CHUYENCA&amount=400000')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])
        self.assertEqual(r.json()['discount_amount'], 50000)

    def test_coupon_validate_below_minimum(self):
        r = self.api_get('/api/coupons/validate_code/?code=CHUYENCA&amount=100000')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['ok'])

    def test_coupon_validate_unknown_code(self):
        r = self.api_get('/api/coupons/validate_code/?code=MAKHONGCO')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['ok'])


# ==========================================================================
# 5. PHÂN QUYỀN CHỦ SÂN
# ==========================================================================

class ApiOwnerTests(ApiTestBase):
    """API dành cho chủ sân."""

    def setUp(self):
        super().setUp()
        self.customer_token = self.register()

    def test_customer_cannot_create_facility(self):
        r = self.api_post('/api/owner/facilities/', {
            'name': 'CLB Khong Duoc Phep', 'address': '1 Duong',
            'phone_contact': '0900000000', 'bank_name': 'MBBank',
            'bank_account_no': '0123456789', 'bank_account_name': 'A',
            'category_id': self.category.id, 'court_count': 2,
            'off_peak_price': '100000', 'peak_price': '150000',
            'open_time': '06:00', 'close_time': '22:00',
        }, token=self.customer_token)
        self.assertEqual(r.status_code, 403)

    def test_owner_registers_facility_as_pending(self):
        self.client.force_login(self.owner)
        r = self.client.post('/api/owner/facilities/', data=json.dumps({
            'name': 'CLB Moi Dang Ky', 'address': '789 Duong XYZ',
            'phone_contact': '0900000000', 'bank_name': 'MBBank',
            'bank_account_no': '0123456789', 'bank_account_name': 'A',
            'category_id': self.category.id, 'court_count': 2,
            'off_peak_price': '100000', 'peak_price': '150000',
            'open_time': '06:00', 'close_time': '22:00',
        }), content_type='application/json')
        self.assertEqual(r.status_code, 201, r.content)
        data = r.json()['facility']
        self.assertEqual(data['status'], 'PENDING_REVIEW')
        self.assertFalse(data['is_verified'])
        self.assertEqual(len(data['courts']), 2)
        self.assertEqual(len(data['pricing_rules']), 14)

    def test_new_facility_is_hidden_from_public_api(self):
        self.client.force_login(self.owner)
        self.client.post('/api/owner/facilities/', data=json.dumps({
            'name': 'CLB Cho Duyet Qua API', 'address': '789 Duong XYZ',
            'phone_contact': '0900000000', 'bank_name': 'MBBank',
            'bank_account_no': '0123456789', 'bank_account_name': 'A',
            'category_id': self.category.id, 'court_count': 1,
            'off_peak_price': '100000', 'peak_price': '150000',
            'open_time': '06:00', 'close_time': '22:00',
        }), content_type='application/json')

        r = self.api_get('/api/facilities/')
        names = [f['name'] for f in r.json()['results']]
        self.assertNotIn('CLB Cho Duyet Qua API', names)

    def test_owner_lists_only_own_facilities(self):
        self.client.force_login(self.owner)
        r = self.client.get('/api/owner/facilities/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['count'], 1)

    def test_owner_facilities_requires_auth(self):
        r = self.api_get('/api/owner/facilities/')
        self.assertEqual(r.status_code, 401)

    def test_owner_booking_stats(self):
        self.client.force_login(self.owner)
        r = self.client.get('/api/owner/bookings/stats/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('total_bookings', r.json())
        self.assertIn('total_revenue', r.json())


# ==========================================================================
# 6. AN TOÀN THÔNG TIN
# ==========================================================================

class ApiSecurityTests(ApiTestBase):
    """Đảm bảo API không rò rỉ dữ liệu nhạy cảm."""

    def test_facility_list_never_exposes_bank_account(self):
        r = self.api_get('/api/facilities/')
        content = r.content.decode('utf-8')
        self.assertNotIn('0123456789', content)
        self.assertNotIn('bank_account_no', content)

    def test_user_serializer_hides_sensitive_fields(self):
        token = self.register('sectest', '0900123123')
        r = self.api_get('/api/auth/me/', token=token)
        content = r.content.decode('utf-8')
        self.assertNotIn('password', content)

    def test_customer_cannot_list_other_customers_bookings(self):
        token_a = self.register('cust_a', '0900124001')
        token_b = self.register('cust_b', '0900124002')
        self.create_slots(2)

        r = self.api_post('/api/bookings/', {
            'slot_ids': [str(BookingSlot.objects.first().id)]}, token=token_a)
        self.assertEqual(r.status_code, 201)

        r2 = self.api_get('/api/bookings/', token=token_b)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['count'], 0)

    def test_pending_facility_cannot_be_booked_via_api(self):
        """Cụm sân CHỜ DUYỆT phải bị chặn khi đặt lịch qua API"""
        from datetime import timedelta
        from django.utils import timezone

        pending = Facility.objects.create(
            owner=self.owner, name='CLB Cho Duyet API', address='1 Duong',
            phone_contact='0900999888', bank_name='MBBank',
            bank_account_no='9876543210', bank_account_name='B',
            status=FacilityStatus.PENDING_REVIEW, is_verified=False,
            active_status=False)
        court = Court.objects.create(
            facility=pending, category=self.category, court_name='San cho duyet')
        slot = BookingSlot.objects.create(
            court=court, date=timezone.localdate() + timedelta(days=1),
            start_time='06:00', end_time='06:30', price=75000)

        token = self.register('cust_pending', '0900125001')
        r = self.api_post('/api/bookings/', {'slot_ids': [str(slot.id)]},
                          token=token)
        self.assertEqual(r.status_code, 400)
        self.assertIn('duyet', r.json()['detail'].lower())

