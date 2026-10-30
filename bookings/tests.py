import uuid
from datetime import date, time, timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from users.models import UserRole
from facilities.models import SportCategory, Facility, Court, PricingRule
from bookings.models import Booking, BookingSlot, BookingStatus
from bookings.services import BookingEngineService, SlotGeneratorService

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
        self.test_date = date(2026, 11, 2) # Thứ 2
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
        Trạng thái chuyển sang REJECTED và các slot tự động được giải phóng về trạng thái mở.
        """
        _, _, booking = BookingEngineService.lock_slots_and_create_booking(
            self.customer_a, [self.slot1.id]
        )
        booking.upload_proof_and_submit('bad_bill.png')

        # Chủ sân từ chối do chưa nhận tiền
        rejected = booking.reject_by_owner("Chưa nhận được tiền vào tài khoản ngân hàng.")
        self.assertTrue(rejected)
        self.assertEqual(booking.status, BookingStatus.REJECTED)

        # Slot phải được giải phóng
        self.slot1.refresh_from_db()
        self.assertIsNone(self.slot1.booking)
        self.assertIsNone(self.slot1.locked_by)
