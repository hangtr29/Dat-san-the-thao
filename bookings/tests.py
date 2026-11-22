import uuid
import json
import os
import re
import glob
from datetime import date, time, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from users.models import UserRole
from facilities.models import SportCategory, Facility, Court, PricingRule, FacilityStatus
from bookings.models import Booking, BookingSlot, BookingStatus, Notification
from bookings.services import BookingEngineService, SlotGeneratorService
from bookings.services_extras import NotificationService

User = get_user_model()

class OOPAndBookingEngineTests(TestCase):
    """
    Unit Tests cho tính chất OOP và Core Booking Engine (Concurrency & State Machine).
    """

    def setUp(self):
        # 1. Khởi tạo Users
        self.owner = User.objects.create_user(
            username='owner_test',
            email='owner@test.com',
            password='password123',
            role=UserRole.OWNER,
            phone='0987654321'
        )
        self.customer_a = User.objects.create_user(
            username='customer_a',
            password='password123',
            role=UserRole.CUSTOMER,
            phone='0912345678'
        )
        self.customer_b = User.objects.create_user(
            username='customer_b',
            password='password123',
            role=UserRole.CUSTOMER,
            phone='0933333333'
        )

        # 2. Khởi tạo Facility & Courts
        self.category = SportCategory.objects.create(name='Pickleball', slug='pickleball')
        self.facility = Facility.objects.create(
            owner=self.owner,
            name='Cụm Sân Pickleball Test',
            address='123 Test Street',
            phone_contact='0987654321',
            bank_name='MBBank',
            bank_account_no='999988887777',
            bank_account_name='CHU SAN TEST',
            open_time=time(6, 0),
            close_time=time(22, 0),
            active_status=True
        )
        self.court1 = Court.objects.create(
            facility=self.facility,
            category=self.category,
            court_name='Sân Số 1'
        )

        # 3. Định nghĩa PricingRule (Đa hình - Polymorphism)
        self.pricing_rule = PricingRule.objects.create(
            facility=self.facility,
            day_of_week=0, # Thứ 2
            start_time=time(6, 0),
            end_time=time(22, 0),
            price_per_hour=Decimal('120000')
        )

        # 4. Sinh Slot kiểm thử
        # (đã sửa: dùng ngày TƯƠNG LAI thay vì ngày cố định đã trôi qua,
        #  vì BookingEngineService chặn đặt khung giờ đã trôi qua)
        self.test_date = timezone.localdate() + timedelta(days=1)
        self.slot1 = BookingSlot.objects.create(
            court=self.court1,
            date=self.test_date,
            start_time=time(18, 0),
            end_time=time(19, 0),
            price=Decimal('120000')
        )

    def test_user_inheritance_and_encapsulation(self):
        """Kiểm tra Tính kế thừa (Inheritance) và Đóng gói (Encapsulation) của User"""
        self.assertTrue(self.owner.is_owner())
        self.assertFalse(self.owner.is_customer())
        self.assertTrue(self.customer_a.is_customer())

    def test_facility_vietqr_generation_encapsulation(self):
        """Kiểm tra Phương thức sinh link VietQR động của Facility"""
        qr_url = self.facility.generate_vietqr_url(120000, 'BKTEST123')
        self.assertIn('mb', qr_url.lower())
        self.assertIn('999988887777', qr_url)
        self.assertIn('120000', qr_url)
        self.assertIn('BKTEST123', qr_url)

    def test_pricing_rule_polymorphism(self):
        """Kiểm tra Tính đa hình (Polymorphism) trong tính toán giá slot theo thời lượng"""
        # 1 giờ (18:00 - 19:00) -> 120,000 đ
        price_1h = self.pricing_rule.calculate_price(time(18, 0), time(19, 0))
        self.assertEqual(price_1h, Decimal('120000'))

        # 1.5 giờ (18:00 - 19:30) -> 180,000 đ
        price_1_5h = self.pricing_rule.calculate_price(time(18, 0), time(19, 30))
        self.assertEqual(price_1_5h, Decimal('180000'))

    def test_concurrency_lock_protection(self):
        """
        Kiểm tra Cơ chế Chống đặt trùng (Conflict Lock):
        User A khóa slot thành công -> User B cố khóa cùng slot sẽ bị từ chối ngay lập tức.
        """
        # Khách A đặt và giữ slot
        success_a, msg_a, booking_a = BookingEngineService.lock_slots_and_create_booking(
            self.customer_a, [self.slot1.id]
        )
        self.assertTrue(success_a)
        self.assertIsNotNone(booking_a)
        self.assertEqual(booking_a.status, BookingStatus.PENDING_BILL)

        # Khách B cố tình đặt cùng slot này trong 10 phút
        success_b, msg_b, booking_b = BookingEngineService.lock_slots_and_create_booking(
            self.customer_b, [self.slot1.id]
        )
        self.assertFalse(success_b)
        self.assertIsNone(booking_b)
        self.assertIn("đang được người khác giữ chỗ", msg_b)

    def test_booking_state_machine_flow(self):
        """
        Kiểm tra Luồng Máy trạng thái (Booking State Machine):
        AVAILABLE -> PENDING_BILL -> WAITING_APPROVAL -> CONFIRMED
        """
        # 1. Khóa và tạo đơn (PENDING_BILL)
        _, _, booking = BookingEngineService.lock_slots_and_create_booking(
            self.customer_a, [self.slot1.id]
        )
        self.assertEqual(booking.status, BookingStatus.PENDING_BILL)

        # 2. Khách upload bill (WAITING_APPROVAL)
        booking.upload_proof_and_submit('dummy_bill.png')
        self.assertEqual(booking.status, BookingStatus.WAITING_APPROVAL)

        # 3. Chủ sân kiểm tra tiền và duyệt (CONFIRMED)
        approved = booking.approve_by_owner(self.owner)
        self.assertTrue(approved)
        self.assertEqual(booking.status, BookingStatus.CONFIRMED)

    def test_past_slot_cannot_be_locked(self):
        """Kiểm tra khung giờ đã trôi qua trong quá khứ không thể bị đặt"""
        yesterday = timezone.localdate() - timedelta(days=1)
        past_slot = BookingSlot.objects.create(
            court=self.court1,
            date=yesterday,
            start_time=time(8, 0),
            end_time=time(9, 0),
            price=Decimal('120000')
        )
        self.assertTrue(past_slot.is_past())
        self.assertFalse(past_slot.is_available)

        success, msg, booking = BookingEngineService.lock_slots_and_create_booking(
            self.customer_a, [past_slot.id]
        )
        self.assertFalse(success)
        self.assertIsNone(booking)
        self.assertIn("đã trôi qua", msg)

    def test_booking_rejection_and_slot_release(self):
        """
        Kiểm tra Chủ sân từ chối đơn đặt:
        - allow_reupload=True (mặc định): đơn -> NEEDS_REUPLOAD, GIỮ slot để
          khách chỉ cần tải lại bill thay vì đặt lại từ đầu.
        - allow_reupload=False: đơn -> REJECTED và các slot được giải phóng.
        """
        _, _, booking = BookingEngineService.lock_slots_and_create_booking(
            self.customer_a, [self.slot1.id]
        )
        booking.upload_proof_and_submit('bad_bill.png')

        # Chủ sân từ chối do chưa nhận tiền -> cho khách tải lại bill
        rejected = booking.reject_by_owner("Chưa nhận được tiền vào tài khoản ngân hàng.")
        self.assertTrue(rejected)
        self.assertEqual(booking.status, BookingStatus.NEEDS_REUPLOAD)

        # Slot VẪN được giữ lại cho khách (chỉ bỏ khóa giữ chỗ tạm thời)
        self.slot1.refresh_from_db()
        self.assertEqual(self.slot1.booking_id, booking.id)
        self.assertIsNone(self.slot1.locked_by)

        # Khách tải lại bill được -> đơn quay lại trạng thái chờ duyệt
        booking.upload_proof_and_submit('good_bill.png')
        self.assertEqual(booking.status, BookingStatus.WAITING_APPROVAL)

    def test_booking_hard_rejection_releases_slots(self):
        """
        Từ chối hẳn (allow_reupload=False): đơn -> REJECTED và slot được giải phóng.
        """
        _, _, booking = BookingEngineService.lock_slots_and_create_booking(
            self.customer_a, [self.slot1.id]
        )
        booking.upload_proof_and_submit('bad_bill.png')

        rejected = booking.reject_by_owner(
            "Không nhận được tiền.", allow_reupload=False)
        self.assertTrue(rejected)
        self.assertEqual(booking.status, BookingStatus.REJECTED)

        # Slot phải được giải phóng
        self.slot1.refresh_from_db()
        self.assertIsNone(self.slot1.booking)
        self.assertIsNone(self.slot1.locked_by)


class SecurityAndDataIntegrityTests(TestCase):
    """
    Kiểm thử cho các lỗi bảo mật & toàn vẹn dữ liệu đã sửa:
    - Không tạo đơn giả khi tra cứu mã đơn không tồn tại
    - is_locked() không được tự gỡ slot (side-effect khi đọc dữ liệu)
    - Chặn đặt slot từ nhiều cụm sân trong cùng 1 đơn
    - Tra cứu bằng SĐT yêu cầu đăng nhập
    - QR do chủ sân tải lên vẫn sinh QR động kèm số tiền & nội dung
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner_int_test',
            password='password123',
            role=UserRole.OWNER,
            phone='0987000001'
        )
        self.customer = User.objects.create_user(
            username='customer_int_test',
            password='password123',
            role=UserRole.CUSTOMER,
            phone='0912000002'
        )
        self.category = SportCategory.objects.create(name='Cầu lông Int', slug='cau-long-int')
        self.facility_a = Facility.objects.create(
            owner=self.owner,
            name='Cụm Sân A',
            address='A',
            phone_contact='0987000001',
            bank_name='MBBank',
            bank_account_no='1111111111',
            bank_account_name='A',
            active_status=True
        )
        self.facility_b = Facility.objects.create(
            owner=self.owner,
            name='Cụm Sân B',
            address='B',
            phone_contact='0987000001',
            bank_name='MBBank',
            bank_account_no='2222222222',
            bank_account_name='B',
            active_status=True
        )
        self.court_a = Court.objects.create(facility=self.facility_a, category=self.category, court_name='A1')
        self.court_b = Court.objects.create(facility=self.facility_b, category=self.category, court_name='B1')

        self.future = timezone.localdate() + timedelta(days=3)
        self.slot_a = BookingSlot.objects.create(
            court=self.court_a, date=self.future, start_time=time(10, 0),
            end_time=time(11, 0), price=Decimal('120000')
        )
        self.slot_b = BookingSlot.objects.create(
            court=self.court_b, date=self.future, start_time=time(10, 0),
            end_time=time(11, 0), price=Decimal('120000')
        )

    def test_lookup_nonexistent_code_does_not_create_booking(self):
        """Tra cứu mã đơn không tồn tại KHÔNG được tạo đơn giả với dữ liệu ghi cứng"""
        from bookings.views import get_booking_or_restore
        from django.test import RequestFactory

        request = RequestFactory().get('/bookings/detail/BKNOTEXIST123/')
        request.session = {}
        booking = get_booking_or_restore(request, 'BKNOTEXIST123')

        self.assertIsNone(booking)
        self.assertFalse(Booking.objects.filter(booking_code='BKNOTEXIST123').exists())

    def test_is_locked_has_no_side_effect(self):
        """is_locked() phải thuần khiết: đọc trạng thái không được gỡ khóa slot"""
        self.slot_a.lock_slot(user=self.customer)
        self.slot_a.refresh_from_db()
        self.assertTrue(self.slot_a.is_locked())

        # Gia hạn thời gian lock về quá khứ (mô phỏng lock hết hạn)
        BookingSlot.objects.filter(id=self.slot_a.id).update(
            lock_time=timezone.now() - timedelta(minutes=30)
        )
        self.slot_a.refresh_from_db()

        # is_locked() phải trả về False
        self.assertFalse(self.slot_a.is_locked())

        # Nhưng KHÔNG được tự gỡ slot khỏi đơn / xóa khóa
        self.slot_a.refresh_from_db()
        self.assertIsNotNone(self.slot_a.lock_time)
        self.assertIsNotNone(self.slot_a.locked_by)

    def test_cannot_book_slots_from_multiple_facilities(self):
        """Chặn chọn slot từ 2 cụm sân khác nhau trong cùng 1 đơn (tránh QR về nhầm chủ sân)"""
        success, msg, booking = BookingEngineService.lock_slots_and_create_booking(
            self.customer, [self.slot_a.id, self.slot_b.id]
        )
        self.assertFalse(success)
        self.assertIsNone(booking)
        self.assertIn("nhiều cụm sân", msg)

    def test_single_facility_booking_is_allowed(self):
        """Vẫn cho phép đặt slot từ cùng một cụm sân"""
        success, msg, booking = BookingEngineService.lock_slots_and_create_booking(
            self.customer, [self.slot_a.id]
        )
        self.assertTrue(success)
        self.assertIsNotNone(booking)

    def test_lookup_by_phone_requires_login(self):
        """Tra cứu đơn bằng Số điện thoại phải yêu cầu đăng nhập"""
        from django.test import Client

        # Tạo 1 đơn gắn với khách hàng đã đăng nhập
        _, _, booking = BookingEngineService.lock_slots_and_create_booking(
            self.customer, [self.slot_a.id]
        )
        booking.customer_name = 'Khách Test'
        booking.customer_phone = '0912000002'
        booking.save()

        client = Client()
        # Chưa đăng nhập -> bị từ chối tra cứu bằng SĐT
        resp = client.get('/bookings/lookup/?code=0912000002')
        self.assertContains(resp, 'cần đăng nhập')

        # Đã đăng nhập -> được xem
        client.login(username='customer_int_test', password='password123')
        resp = client.get('/bookings/lookup/?code=0912000002')
        self.assertContains(resp, booking.booking_code)

    def test_vietqr_always_includes_amount_and_memo(self):
        """QR tùy chỉnh của chủ sân không được làm mất số tiền & nội dung"""
        # Tạo ảnh QR tùy chỉnh giả (dùng file tạm)
        from django.core.files.base import ContentFile
        self.facility_a.custom_qr_image.save(
            'test_qr.png', ContentFile(b'fake-png-data'), save=True
        )
        self.facility_a.refresh_from_db()

        qr_url = self.facility_a.generate_vietqr_url(150000, 'BKTEST999')
        self.assertIn('amount=150000', qr_url)
        self.assertIn('BKTEST999', qr_url)
        self.assertIn('1111111111', qr_url)

    def test_session_does_not_store_base64_proof(self):
        """Ảnh bill KHÔNG được nhét base64 vào cookie session"""
        from django.test import RequestFactory
        from bookings.views import save_booking_to_session

        _, _, booking = BookingEngineService.lock_slots_and_create_booking(
            self.customer, [self.slot_b.id]
        )

        request = RequestFactory().get('/')
        request.session = {}
        save_booking_to_session(request, booking)

        saved = request.session['saved_bookings'][booking.booking_code]
        self.assertNotIn('proof_data_url', saved)
        self.assertIn('proof_path', saved)


class Slot30MinutesTests(TestCase):
    """
    Unit Tests cho khung giờ 30 PHÚT:
    - Mỗi giờ được chia làm 2 slot (vd 13:00-13:30, 13:30-14:00).
    - Giá mỗi slot 30 phút = đúng 1/2 giá giờ của khung giờ đó.
    - Khung giờ mở/đóng cửa chưa tròn giờ vẫn sinh slot đúng.
    - Chế độ hiển thị theo giờ (step=60) gộp đúng 2 slot con.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner_slot', password='password123',
            role=UserRole.OWNER, phone='0900000022',
        )
        self.category = SportCategory.objects.create(name='Cầu Lông 30P')
        self.facility = Facility.objects.create(
            owner=self.owner, name='CLB 30 Phút', address='Số 1 Đường A, Quận 1, TP.HCM',
            phone_contact='0900000033', bank_name='MBBank',
            bank_account_no='111122223333', bank_account_name='OWNER',
            open_time=time(13, 0), close_time=time(15, 0),
            status=FacilityStatus.ACTIVE, is_verified=True, active_status=True,
        )
        self.court = Court.objects.create(
            facility=self.facility, category=self.category, court_name='Sân 1',
        )
        # Biểu giá 120.000 đ/giờ cho cả 7 ngày
        for day in range(7):
            PricingRule.objects.create(
                facility=self.facility, day_of_week=day,
                start_time=time(6, 0), end_time=time(22, 0),
                price_per_hour=Decimal('120000'),
            )

    def test_default_slot_minutes_is_30(self):
        """Khung giờ chuẩn phải là 30 phút"""
        self.assertEqual(SlotGeneratorService.DEFAULT_SLOT_MINUTES, 30)

    def test_hour_is_split_into_two_30min_slots(self):
        """13:00-15:00 -> 4 slot 30 phút liên tục"""
        today = timezone.localdate()
        SlotGeneratorService.generate_slots_for_court(self.court, today)

        slots = list(BookingSlot.objects.filter(court=self.court, date=today)
                     .order_by('start_time'))
        self.assertEqual(len(slots), 4)
        self.assertEqual(
            [(s.start_time.strftime('%H:%M'), s.end_time.strftime('%H:%M')) for s in slots],
            [('13:00', '13:30'), ('13:30', '14:00'), ('14:00', '14:30'), ('14:30', '15:00')],
        )

    def test_30min_slot_price_is_half_hour_price(self):
        """Giá slot 30 phút = 1/2 giá giờ (120k/giờ -> 60k/slot)"""
        today = timezone.localdate()
        SlotGeneratorService.generate_slots_for_court(self.court, today)

        slot = BookingSlot.objects.filter(court=self.court, date=today).first()
        self.assertEqual(slot.price, Decimal('60000'))

    def test_all_slots_are_30_minutes(self):
        """Không còn slot 60 phút nào sau khi sinh"""
        today = timezone.localdate()
        SlotGeneratorService.generate_slots_for_court(self.court, today)

        for s in BookingSlot.objects.filter(court=self.court, date=today):
            duration = (s.end_time.hour * 60 + s.end_time.minute) - \
                       (s.start_time.hour * 60 + s.start_time.minute)
            self.assertEqual(duration, 30)

    def test_facility_detail_step_30_vs_60(self):
        """Chế độ hiển thị: step=30 cho lưới nửa giờ, step=60 gộp 2 slot con"""
        today = timezone.localdate()
        SlotGeneratorService.generate_slots_for_court(self.court, today)

        resp30 = self.client.get(f'/facilities/{self.facility.id}/?step=30')
        self.assertEqual(resp30.status_code, 200)
        self.assertEqual(len(resp30.context['time_headers']), 4)
        self.assertEqual(resp30.context['step_minutes'], 30)

        resp60 = self.client.get(f'/facilities/{self.facility.id}/?step=60')
        self.assertEqual(resp60.status_code, 200)
        self.assertEqual(len(resp60.context['time_headers']), 2)
        self.assertEqual(resp60.context['step_minutes'], 60)

    def test_booking_two_30min_slots_sums_price(self):
        """Đặt 2 slot 30 phút liền kề -> tổng tiền = 1 giờ, thời lượng 60 phút"""
        # Dùng ngày mai để tránh slot đã trôi qua (giờ mở cửa 13:00)
        target = timezone.localdate() + timedelta(days=1)
        SlotGeneratorService.generate_slots_for_court(self.court, target)

        slots = list(BookingSlot.objects.filter(court=self.court, date=target)
                     .order_by('start_time')[:2])
        self.assertEqual(len(slots), 2)
        ok, msg, booking = BookingEngineService.lock_slots_and_create_booking(
            user=None, slot_ids=[s.id for s in slots],
            session_key='sess-30', customer_name='Khách', customer_phone='0900000099',
        )
        self.assertTrue(ok, msg)
        self.assertEqual(booking.total_amount, Decimal('120000'))  # 2 x 60.000
        self.assertEqual(booking.slots.count(), 2)


class TemplateRenderingIntegrityTests(TestCase):
    """
    Regression tests chống 2 lỗi template rendering:

    1) TEMPLATE TAG BỊ NGẮT DÒNG
       Khi '{{' nằm cuối dòng và phần còn lại của biến nằm ở dòng sau,
       Django KHÔNG render mà in ra nguyên văn lên trang web, ví dụ:
           Thứ Hai (05:00-{{ rule.end_time|time:"H:i" }}): 150000 đ/h

    2) JAVASCRIPT NẰM NGOÀI THẺ <script>
       Khi một khối JS không nằm trong <script>...</script>, trình duyệt
       hiển thị nguyên code ra dưới footer (như text thường).

    Cả hai lỗi đều làm trang web hiển thị sai cho người dùng.
    """

    TEMPLATE_ROOT = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')

    def _iter_template_files(self):
        for path in glob.glob(os.path.join(self.TEMPLATE_ROOT, '**', '*.html'), recursive=True):
            yield path

    def test_no_broken_multiline_template_tags(self):
        """Không được có template tag bị ngắt dòng trong bất kỳ file .html nào"""
        broken = []
        for path in self._iter_template_files():
            rel = os.path.relpath(path, self.TEMPLATE_ROOT)
            with open(path, encoding='utf-8') as f:
                lines = f.readlines()
            for i, line in enumerate(lines, start=1):
                stripped = line.rstrip('\n')
                has_open = ('{{' in stripped) or ('{%' in stripped)
                has_close = ('}}' in stripped) or ('%}' in stripped)
                if has_open and not has_close:
                    broken.append('%s:%d -> %s' % (rel, i, stripped.strip()[:90]))

        self.assertEqual(
            broken, [],
            'Cac template tag bi cat dong (Django se KHONG render):\n  '
            + '\n  '.join(broken)
        )

    def test_rendered_pages_have_no_leftover_template_tags(self):
        """HTML render ra khong được chua template tag chua render"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin, _ = User.objects.get_or_create(
            username='chusan_tpl', defaults={'email': 'chusan_tpl@test.com'})
        admin.set_password('chusan123')
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()

        client = Client()
        client.force_login(admin)

        urls = [
            '/facilities/', '/facilities/map/', '/facilities/favorites/',
            '/bookings/dashboard/?tab=orders', '/bookings/dashboard/?tab=reviews',
            '/bookings/dashboard/?tab=settings', '/bookings/history/',
            '/bookings/owner/calendar/', '/bookings/owner/gallery/',
            '/bookings/owner/services/', '/bookings/owner/kyc/',
            '/facilities/owner/facility/manage/', '/facilities/owner/courts/',
            '/users/profile/',
        ]
        for fid in Facility.objects.values_list('id', flat=True):
            urls.append('/facilities/%s/' % fid)

        # Khu vuc HTML render co tag chua render
        leftover_re = re.compile(
            r'\{\{\s*\n?\s*[a-zA-Z_][\w\.\|\:"\'\[\]\- ]{0,80}\}\}'
            r'|\{%\s*\n?\s*[a-zA-Z_][\w\s\|\.\(\)":\'\[\]\-]{0,80}%\}')

        problems = []
        for url in urls:
            resp = client.get(url)
            if resp.status_code != 200:
                continue
            html = resp.content.decode('utf-8', 'replace')
            hits = [m.replace('\n', ' ')[:90] for m in leftover_re.findall(html)
                    if m.strip() not in ('{{', '{%')]
            if hits:
                problems.append('%s -> %s' % (url, hits[:3]))

        self.assertEqual(problems, [],
                         'Cac trang van con template tag chua render:\n  '
                         + '\n  '.join(problems))

    def test_no_cache_headers_in_debug(self):
        """Trang HTML phai co header chong cache de trinh duyet luon tai ban moi"""
        from django.conf import settings
        if not settings.DEBUG:
            self.skipTest('Chi kiem tra header chong cache khi DEBUG=True')

        resp = self.client.get('/facilities/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('no-store', resp.get('Cache-Control', ''))
        self.assertIn('no-cache', resp.get('Pragma', ''))

    def test_script_tags_balanced_in_source_templates(self):
        """Trong source template, so <script> va </script> phai bang nhau"""
        unbalanced = []
        for path in self._iter_template_files():
            rel = os.path.relpath(path, self.TEMPLATE_ROOT)
            with open(path, encoding='utf-8') as f:
                content = f.read()
            opens = len(re.findall(r'<script\b', content, re.IGNORECASE))
            closes = len(re.findall(r'</script\s*>', content, re.IGNORECASE))
            if opens != closes:
                unbalanced.append('%s: %d <script> / %d </script>' % (rel, opens, closes))

        self.assertEqual(unbalanced, [],
                         'So <script> va </script> khong khai trong template:\n  '
                         + '\n  '.join(unbalanced))

    def test_no_javascript_leaks_outside_script_tag(self):
        """Không được có khối JS nằm ngoài thẻ <script> (sẽ hiện ra dưới footer)"""
        from html.parser import HTMLParser

        class _Watcher(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.in_script = False
                self.in_style = False
                self.outside = []

            def handle_starttag(self, tag, attrs):
                if tag == 'script':
                    self.in_script = True
                elif tag == 'style':
                    self.in_style = True

            def handle_endtag(self, tag):
                if tag == 'script':
                    self.in_script = False
                elif tag == 'style':
                    self.in_style = False

            def handle_data(self, data):
                if not self.in_script and not self.in_style and data.strip():
                    self.outside.append(data)

        # Dau hieu code JS (nhung bien text thuong HTML co the trung -> dung regex chat)
        js_hint = re.compile(
            r'document\.(addEventListener|querySelector|getElementById|createElement)'
            r'|window\.(location|location\.href)'
            r'|const\s+\w+\s*=\s*(document|window|fetch)'
            r'|^\s*\}\s*\)\s*;'
            r'|;\s*\}\s*\)\s*$')

        problems = []
        for path in self._iter_template_files():
            rel = os.path.relpath(path, self.TEMPLATE_ROOT)
            with open(path, encoding='utf-8') as f:
                content = f.read()
            w = _Watcher()
            try:
                w.feed(content)
            except Exception:
                continue
            for text in w.outside:
                if js_hint.search(text):
                    problems.append('%s -> %s' % (rel, text.strip()[:100].replace('\n', ' ')))
                    break

        self.assertEqual(problems, [],
                         'Co khoi JavaScript nam NGOAI the <script> (se bi hien ra duoi footer):\n  '
                         + '\n  '.join(problems))

    def test_rendered_pages_have_no_raw_js_in_body(self):
        """HTML render ra không được chứa code JS lộ ra ngoài thẻ script"""
        client = Client()
        urls = ['/facilities/', '/facilities/map/', '/facilities/favorites/']
        for fid in Facility.objects.values_list('id', flat=True):
            urls.append('/facilities/%s/' % fid)

        # Chuoi dac trung cua khoi JS "loi" bi hien ra ngoai the script
        leak_markers = [
            'document.addEventListener(\'DOMContentLoaded\'',
            'getCookie(name)',
            'showToast(message, type)',
            'data-fav-btn',
        ]

        problems = []
        for url in urls:
            resp = client.get(url)
            if resp.status_code != 200:
                continue
            html = resp.content.decode('utf-8', 'replace')
            # Lay phan text visible (bo moi noi dung <script>)
            visible = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            visible = re.sub(r'<style\b[^>]*>.*?</style>', '', visible, flags=re.DOTALL | re.IGNORECASE)
            hits = [m for m in leak_markers if m in visible]
            if hits:
                problems.append('%s -> %s' % (url, hits))

        self.assertEqual(problems, [],
                         'Co code JavaScript lo ra ngoai the <script> (hien duoi footer):\n  '
                         + '\n  '.join(problems))


class FacilityRegistrationFlowTests(TestCase):
    """
    Unit Tests cho luồng đăng ký CỤM SÂN MỚI:
    Chủ sân điền hồ sơ -> Facility ở trạng thái PENDING_REVIEW, chưa hiển thị công khai
    -> Ban quản trị duyệt trong /admin/ -> ACTIVE + tích xanh -> hiện ra cho khách.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner_reg',
            password='password123',
            role=UserRole.OWNER,
            phone='0900000001',
        )
        self.category = SportCategory.objects.create(name='Cầu Lông Test')

        self.valid_payload = {
            'name': 'CLB Cầu Lông Mới',
            'address': 'Số 123 Đường Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP.HCM',
            'phone_contact': '0901234567',
            'bank_name': 'MBBank',
            'bank_account_no': '0123456789',
            'bank_account_name': 'NGUYEN VAN A',
            'latitude': '10.7769',
            'longitude': '106.7009',
            'open_time': '06:00',
            'close_time': '22:00',
            'court_count': '3',
            'off_peak_price': '120000',
            'peak_price': '180000',
            'category_id': str(self.category.id),
        }

    def test_owner_can_access_register_page(self):
        """Chủ sân đăng nhập được mở trang đăng ký cụm sân"""
        self.client.login(username='owner_reg', password='password123')
        resp = self.client.get('/facilities/owner/facility/register/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Đăng ký cụm sân mới')

    def test_customer_cannot_access_register_page(self):
        """Khách hàng KHÔNG được đăng ký cụm sân"""
        customer = User.objects.create_user(
            username='cust_reg', password='password123',
            role=UserRole.CUSTOMER, phone='0900000002',
        )
        self.client.login(username='cust_reg', password='password123')
        resp = self.client.get('/facilities/owner/facility/register/')
        self.assertEqual(resp.status_code, 302)

    def test_register_creates_pending_facility_not_public(self):
        """Hồ sơ mới phải ở PENDING_REVIEW và KHÔNG hiển thị trong danh sách khách hàng"""
        self.client.login(username='owner_reg', password='password123')
        resp = self.client.post('/facilities/owner/facility/register/', self.valid_payload)
        self.assertEqual(resp.status_code, 302)

        facility = Facility.objects.get(name='CLB Cầu Lông Mới')
        self.assertEqual(facility.status, FacilityStatus.PENDING_REVIEW)
        self.assertFalse(facility.is_verified)
        self.assertFalse(facility.active_status)
        self.assertFalse(facility.is_published)
        self.assertEqual(facility.owner, self.owner)

        # Không hiển thị công khai cho khách
        public_list = self.client.get('/facilities/')
        self.assertNotContains(public_list, 'CLB Cầu Lông Mới')

    def test_register_creates_courts_pricing_and_slots(self):
        """Hồ sơ mới tự sinh sân con, bảng giá & ma trận slot giờ"""
        self.client.login(username='owner_reg', password='password123')
        self.client.post('/facilities/owner/facility/register/', self.valid_payload)

        facility = Facility.objects.get(name='CLB Cầu Lông Mới')
        self.assertEqual(facility.courts.count(), 3)
        # 7 ngày x (giờ thường + giờ cao điểm)
        self.assertEqual(facility.pricing_rules.count(), 14)
        # Slot giờ đã được sinh
        self.assertGreater(BookingSlot.objects.filter(court__facility=facility).count(), 0)

    def test_register_rejects_missing_required_fields(self):
        """Thiếu thông tin bắt buộc -> không tạo cụm sân nào"""
        payload = dict(self.valid_payload)
        payload['bank_account_no'] = ''
        self.client.login(username='owner_reg', password='password123')
        self.client.post('/facilities/owner/facility/register/', payload)
        self.assertEqual(Facility.objects.filter(name='CLB Cầu Lông Mới').count(), 0)

    def test_admin_approval_makes_facility_public(self):
        """Ban quản trị duyệt -> cụm sân hiển thị công khai cho khách hàng"""
        self.client.login(username='owner_reg', password='password123')
        self.client.post('/facilities/owner/facility/register/', self.valid_payload)

        facility = Facility.objects.get(name='CLB Cầu Lông Mới')

        # Hành động của Admin trong /admin/
        Facility.objects.filter(pk=facility.pk).update(
            is_verified=True,
            status=FacilityStatus.ACTIVE,
            active_status=True,
        )
        facility.refresh_from_db()
        self.assertTrue(facility.is_published)

        # Khách hàng (chưa đăng nhập) thấy cụm sân trong danh sách
        anon = self.client_class()
        resp = anon.get('/facilities/')
        self.assertContains(resp, 'CLB Cầu Lông Mới')

    # ---------------------------------------------------------------
    # CHỐNG LÁCH DUYỆT: cụm sân PENDING_REVIEW phải thực sự "ẩn"
    # ---------------------------------------------------------------

    def test_pending_facility_hidden_from_public_list(self):
        """Cụm sân CHỜ DUYỆT không được hiện trên danh sách công khai"""
        self.client.login(username='owner_reg', password='password123')
        self.client.post('/facilities/owner/facility/register/', self.valid_payload)

        anon = self.client_class()
        resp = anon.get('/facilities/')
        self.assertNotContains(resp, 'CLB Cầu Lông Mới')

    def test_pending_facility_detail_returns_404(self):
        """Cụm sân CHỜ DUYỆT: trang chi tiết & API bảng thông tin phải chặn (404)"""
        self.client.login(username='owner_reg', password='password123')
        self.client.post('/facilities/owner/facility/register/', self.valid_payload)
        facility = Facility.objects.get(name='CLB Cầu Lông Mới')

        anon = self.client_class()
        resp = anon.get(f'/facilities/{facility.id}/')
        self.assertEqual(resp.status_code, 404)

        resp_api = anon.get(f'/facilities/api/info/{facility.id}/')
        self.assertEqual(resp_api.status_code, 404)

    def test_pending_facility_cannot_be_booked(self):
        """Cụm sân CHỜ DUYỆT: khách không thể giữ chỗ slot (chặn tại BookingEngine)"""
        from datetime import timedelta
        from django.utils import timezone

        self.client.login(username='owner_reg', password='password123')
        self.client.post('/facilities/owner/facility/register/', self.valid_payload)
        facility = Facility.objects.get(name='CLB Cầu Lông Mới')
        court = facility.courts.first()
        slot = BookingSlot.objects.filter(
            court=court, date=timezone.localdate() + timedelta(days=1)
        ).first()
        self.assertIsNotNone(slot)

        ok, msg, booking = BookingEngineService.lock_slots_and_create_booking(
            user=None, slot_ids=[slot.id], session_key='anon-session',
            customer_name='Khách lạ', customer_phone='0900000099',
        )
        self.assertFalse(ok, 'Không được phép đặt lịch vào cụm sân chờ duyệt!')
        self.assertIsNone(booking)

    def test_pending_facility_not_in_search_suggestions(self):
        """Cụm sân CHỜ DUYỆT không được gợi ý trong ô tìm kiếm"""
        self.client.login(username='owner_reg', password='password123')
        self.client.post('/facilities/owner/facility/register/', self.valid_payload)

        anon = self.client_class()
        resp = anon.get('/facilities/api/suggest/?q=Cầu Lông Mới')
        data = json.loads(resp.content)
        names = [f['name'] for f in data.get('facilities', [])]
        self.assertNotIn('CLB Cầu Lông Mới', names)

    def test_kyc_approval_auto_activates_pending_facility(self):
        """Duyệt KYC chủ sân -> cụm sân đang chờ duyệt cũng được kích hoạt luôn"""
        from users.models import OwnerProfile, KYCStatus
        from django.contrib.admin.sites import AdminSite
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.messages import get_messages
        from django.test import RequestFactory
        from users.admin import OwnerProfileAdmin

        self.client.login(username='owner_reg', password='password123')
        self.client.post('/facilities/owner/facility/register/', self.valid_payload)
        facility = Facility.objects.get(name='CLB Cầu Lông Mới')
        self.assertEqual(facility.status, FacilityStatus.PENDING_REVIEW)

        profile, _ = OwnerProfile.objects.get_or_create(user=self.owner)
        profile.kyc_status = KYCStatus.KYC_PENDING
        profile.save()

        # Dựng request giả để gọi admin action (admin action cần request.messages)
        request = RequestFactory().post('/admin/users/ownerprofile/')
        request.user = User.objects.create_superuser(
            username='admin_kyc', email='admin@x.com', password='password123'
        )
        setattr(request, 'session', 'session')
        request._messages = FallbackStorage(request)

        admin_site = AdminSite()
        model_admin = OwnerProfileAdmin(OwnerProfile, admin_site)
        model_admin.approve_kyc_selected(
            request=request, queryset=OwnerProfile.objects.filter(pk=profile.pk)
        )

        facility.refresh_from_db()
        self.assertEqual(facility.status, FacilityStatus.ACTIVE)
        self.assertTrue(facility.is_verified)
        self.assertTrue(facility.active_status)
        self.assertTrue(facility.is_published)


class TwoWayInteractionTests(TestCase):
    """
    Unit Tests cho cơ chế TƯƠNG TÁC 2 CHIỀU giữa Chủ sân và Khách hàng:
    - Khách hủy đơn -> chủ sân nhận notification.
    - Chủ sân phản hồi đánh giá -> khách nhận notification.
    - Chủ sân nhận đơn mới -> notification (đã có).
    - Chủ sân duyệt/từ chối -> khách nhận notification (đã có).
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner_tw', password='password123',
            role=UserRole.OWNER, phone='0900000011',
        )
        self.customer = User.objects.create_user(
            username='cust_tw', password='password123',
            role=UserRole.CUSTOMER, phone='0900000012',
        )
        self.category = SportCategory.objects.create(name='Cầu Lông TW')
        self.facility = Facility.objects.create(
            owner=self.owner, name='CLB TW', address='Số 1 Đường A, Quận 1, TP.HCM',
            phone_contact='0900000013', bank_name='MBBank',
            bank_account_no='111122223333', bank_account_name='OWNER',
            status=FacilityStatus.ACTIVE, is_verified=True, active_status=True,
        )
        self.court = Court.objects.create(
            facility=self.facility, category=self.category, court_name='Sân 1',
        )
        self.booking = Booking.objects.create(
            customer=self.customer, customer_name='Khách TW', customer_phone='0900000012',
            total_amount=120000, status=BookingStatus.WAITING_APPROVAL,
        )
        slot = BookingSlot.objects.create(
            court=self.court, booking=self.booking,
            date=timezone.localdate() + timedelta(days=1),
            start_time=time(8, 0), end_time=time(9, 0), price=120000,
        )
        self.booking.slots.add(slot)

    def test_customer_cancel_notifies_owner_and_frees_slot(self):
        """Khách hủy đơn -> chủ sân nhận thông báo & slot được giải phóng"""
        self.client.login(username='cust_tw', password='password123')
        resp = self.client.post(
            f'/bookings/cancel/{self.booking.booking_code}/',
            {'cancel_reason': 'Có việc đột xuất'},
        )
        self.assertEqual(resp.status_code, 302)

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.CANCELLED)

        # Slot đã được giải phóng (booking = None)
        slot = BookingSlot.objects.get(court=self.court)
        self.assertIsNone(slot.booking)

        # Chủ sân nhận notification
        notif = Notification.objects.filter(
            user=self.owner, notification_type='BOOKING_CANCELLED'
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn(self.booking.booking_code, notif.title)

    def test_customer_cannot_cancel_confirmed_booking(self):
        """Đơn đã được duyệt thì khách KHÔNG hủy được qua hệ thống"""
        self.booking.status = BookingStatus.CONFIRMED
        self.booking.save()
        self.client.login(username='cust_tw', password='password123')
        self.client.post(f'/bookings/cancel/{self.booking.booking_code}/', {})
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.CONFIRMED)

    def test_owner_reply_notifies_customer(self):
        """Chủ sân phản hồi đánh giá -> khách hàng nhận notification"""
        from facilities.models import FacilityReview
        review = FacilityReview.objects.create(
            facility=self.facility, booking=self.booking, user=self.customer,
            reviewer_name='Khách TW', rating=4, comment='Sân đẹp, vợt chuẩn',
        )
        self.client.login(username='owner_tw', password='password123')
        resp = self.client.post(
            f'/bookings/owner/review/{review.id}/reply/',
            {'owner_reply': 'Cảm ơn bạn, hẹn gặp lại!'},
        )
        self.assertEqual(resp.status_code, 302)

        notif = Notification.objects.filter(
            user=self.customer, notification_type='SYSTEM'
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn('phản hồi', notif.title.lower())

    def test_new_review_notifies_owner(self):
        """Khách đánh giá -> chủ sân nhận notification"""
        from facilities.models import FacilityReview
        review = FacilityReview.objects.create(
            facility=self.facility, booking=self.booking, user=self.customer,
            reviewer_name='Khách TW', rating=5, comment='Tuyệt vời',
        )
        NotificationService.notify_owner_new_review(review)
        notif = Notification.objects.filter(
            user=self.owner, title__icontains='Đánh giá mới'
        ).first()
        self.assertIsNotNone(notif)

    def test_owner_receives_new_booking_notification(self):
        """Khách đặt sân -> chủ sân nhận notification đơn mới"""
        NotificationService.notify_owner_new_booking(self.booking)
        notif = Notification.objects.filter(
            user=self.owner, notification_type='BOOKING_NEW'
        ).first()
        self.assertIsNotNone(notif)
