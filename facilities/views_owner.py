"""
Phân hệ Nghiệp vụ dành cho Chủ Sân (Owner Subsystem):
Áp dụng tư duy Hướng đối tượng (OOP), phân quyền Role-based Access Control (RBAC).
Bao gồm:
1. FacilityManageView: Quản lý thông tin Cụm sân, ảnh thực địa, giờ hoạt động, hotline & tọa độ GPS.
2. CourtCreateUpdateView: Thêm/Sửa sân con, định giá giờ thường/cao điểm & tự động sinh ma trận TimeSlot 60 phút.
3. OwnerBookingApprovalView: Quản lý đối soát bill và phê duyệt / từ chối đơn đặt sân.
4. FacilityRegisterView: Đăng ký cụm sân mới -> chờ Ban quản trị duyệt (PENDING_REVIEW).
"""

from datetime import datetime, date, time, timedelta
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.db import transaction
from .models import Facility, Court, SportCategory, PricingRule, FacilityStatus
from bookings.models import Booking, BookingStatus, BookingSlot
from bookings.services import SlotGeneratorService


class OwnerBaseView(LoginRequiredMixin, View):
    """
    Lớp cơ sở kế thừa (Tính kế thừa - Inheritance):
    Đóng gói kiểm tra phân quyền Chủ sân (OWNER hoặc Staff/Superuser).
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/users/login/?next={request.path}")
        if not (request.user.is_owner() or request.user.is_staff):
            messages.error(request, "Bạn không có quyền truy cập Kênh Chủ Sân.")
            return redirect('facilities:facility_list')
        return super().dispatch(request, *args, **kwargs)

    def get_owner_facilities(self, user):
        """Lấy danh sách các cụm sân thuộc quyền sở hữu của user"""
        if user.is_superuser:
            return Facility.objects.all()
        return Facility.objects.filter(owner=user)


class FacilityRegisterView(OwnerBaseView):
    """
    Mục tiêu: Luồng đăng ký CỤM SÂN MỚI của chủ sân.

    Trước đây hệ thống thiếu mắt xích này:
    - `FacilityStatus.PENDING_REVIEW` tồn tại trong model + admin nhưng KHÔNG có
      bất kỳ mã nào tạo ra nó -> không ai có thể đăng ký sân mới và chờ duyệt.
    - Chủ sân mới đăng ký tài khoản thì không có cụm sân nào để quản lý.

    Luồng sau khi triển khai:
      Chủ sân điền hồ sơ  ->  Facility(status=PENDING_REVIEW, is_verified=False)
      -> Ban quản trị xem trong /admin/ và bấm "Cấp tích xanh KYC & Kích hoạt"
      -> Facility(status=ACTIVE, is_verified=True)  ->  hiển thị công khai cho khách.
    """

    template_name = 'owner/facility_register.html'

    def get(self, request):
        my_facilities = self.get_owner_facilities(request.user)
        context = {
            'my_facilities': my_facilities,
            'categories': SportCategory.objects.all(),
            'pending_count': my_facilities.filter(status=FacilityStatus.PENDING_REVIEW).count(),
            'active_count': my_facilities.filter(status=FacilityStatus.ACTIVE).count(),
        }
        return render(request, self.template_name, context)

    def post(self, request):
        # --- 1. Thu thập & kiểm tra dữ liệu ---
        name = request.POST.get('name', '').strip()
        address = request.POST.get('address', '').strip()
        phone_contact = request.POST.get('phone_contact', '').strip()
        bank_name = request.POST.get('bank_name', '').strip()
        bank_account_no = request.POST.get('bank_account_no', '').strip()
        bank_account_name = request.POST.get('bank_account_name', '').strip()

        errors = []
        if len(name) < 3:
            errors.append("Tên cụm sân phải có ít nhất 3 ký tự.")
        if len(address) < 10:
            errors.append("Địa chỉ phải mô tả chi tiết ít nhất 10 ký tự.")
        if not phone_contact:
            errors.append("Vui lòng nhập số Hotline / Zalo liên hệ.")
        if not bank_name or not bank_account_no or not bank_account_name:
            errors.append("Vui lòng nhập đầy đủ thông tin tài khoản ngân hàng nhận tiền.")

        # Tọa độ GPS (bắt buộc để chống sân ma & hiển thị trên bản đồ)
        try:
            latitude = float(request.POST.get('latitude', '10.7769'))
            longitude = float(request.POST.get('longitude', '106.7009'))
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                raise ValueError
        except (TypeError, ValueError):
            errors.append("Tọa độ GPS không hợp lệ.")

        # Giờ mở/đóng cửa
        try:
            open_time = datetime.strptime(request.POST.get('open_time', '06:00'), '%H:%M').time()
            close_time = datetime.strptime(request.POST.get('close_time', '22:00'), '%H:%M').time()
            if open_time >= close_time:
                errors.append("Giờ mở cửa phải trước giờ đóng cửa.")
        except ValueError:
            errors.append("Định dạng giờ mở/đóng cửa không hợp lệ.")
            open_time, close_time = time(6, 0), time(22, 0)

        # Số lượng sân con & giá
        try:
            court_count = max(1, min(20, int(request.POST.get('court_count', '2'))))
        except (TypeError, ValueError):
            court_count = 2
        try:
            off_peak_price = Decimal(request.POST.get('off_peak_price', '120000').replace('.', '').replace(',', ''))
            peak_price = Decimal(request.POST.get('peak_price', '180000').replace('.', '').replace(',', ''))
        except Exception:
            off_peak_price, peak_price = Decimal('120000'), Decimal('180000')

        category_id = request.POST.get('category_id')
        category = SportCategory.objects.filter(id=category_id).first() if category_id else SportCategory.objects.first()
        if not category:
            errors.append("Vui lòng chọn môn thể thao chính của cụm sân.")

        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('facilities:owner_facility_register')

        # --- 2. Tạo cụm sân ở trạng thái CHỜ DUYỆT ---
        with transaction.atomic():
            facility = Facility.objects.create(
                owner=request.user,
                name=name,
                address=address,
                phone_contact=phone_contact,
                hotline=request.POST.get('hotline', '').strip() or phone_contact,
                bank_name=bank_name,
                bank_account_no=bank_account_no,
                bank_account_name=bank_account_name,
                open_time=open_time,
                close_time=close_time,
                latitude=latitude,
                longitude=longitude,
                description=request.POST.get('description', '').strip(),
                highlights=request.POST.get('highlights', '').strip(),
                # Chờ Ban quản trị duyệt -> chưa hiển thị công khai
                status=FacilityStatus.PENDING_REVIEW,
                is_verified=False,
                active_status=False,
            )

            # Ảnh bìa do chủ sân tải lên (tùy chọn)
            if 'image' in request.FILES:
                facility.image = request.FILES['image']
                facility.save(update_fields=['image'])

            # Tạo sân con
            for i in range(1, court_count + 1):
                Court.objects.create(
                    facility=facility,
                    category=category,
                    court_name=f"Sân {i}",
                    court_area=request.POST.get('court_area', 'Sân trong nhà'),
                    surface_type=request.POST.get('surface_type', 'Thảm PVC chuyên dụng'),
                    is_active=True,
                )

            # Bảng giá: Giờ thường (mở cửa -> 17:00) & Cao điểm (17:00 -> đóng cửa)
            peak_start = time(17, 0)
            if peak_start > close_time:
                peak_start = close_time
            for day in range(7):
                PricingRule.objects.create(
                    facility=facility, day_of_week=day,
                    start_time=open_time, end_time=peak_start,
                    price_per_hour=off_peak_price,
                )
                if peak_start < close_time:
                    PricingRule.objects.create(
                        facility=facility, day_of_week=day,
                        start_time=peak_start, end_time=close_time,
                        price_per_hour=peak_price,
                    )

            # Sinh slot giờ cho 14 ngày tới (chia nhỏ 30 phút/lần)
            today = timezone.localdate()
            for court in facility.courts.all():
                for i in range(14):
                    SlotGeneratorService.generate_slots_for_court(
                        court=court, target_date=today + timedelta(days=i)
                    )

        # --- 3. Thông báo cho chủ sân & Ban quản trị ---
        from bookings.services_extras import NotificationService
        NotificationService.notify(
            request.user, 'SYSTEM',
            "Đã gửi hồ sơ đăng ký cụm sân",
            f"Hồ sơ '{name}' đã được gửi tới Ban quản trị. Cụm sân sẽ hiển thị công khai sau khi được duyệt.",
            "/facilities/owner/facility/register/",
        )

        # Gửi thông báo cho tất cả admin (superuser) để họ duyệt kịp thời
        from users.models import User
        for admin in User.objects.filter(is_superuser=True).exclude(pk=request.user.pk):
            NotificationService.notify(
                admin, 'SYSTEM',
                "Hồ sơ đăng ký cụm sân mới chờ duyệt",
                f"Chủ sân '{request.user.get_full_name() or request.user.username}' vừa đăng ký cụm sân '{name}'.",
                f"/admin/facilities/facility/?q={name}",
            )

        messages.success(
            request,
            "🎉 Đã gửi hồ sơ đăng ký cụm sân! Ban quản trị sẽ kiểm tra và phản hồi sớm. "
            "Trong lúc chờ duyệt, bạn có thể tiếp tục cấu hình sân thi đấu & dịch vụ.",
        )
        return redirect('facilities:owner_facility_register')


class FacilityManageView(OwnerBaseView):
    """
    Mục tiêu 2.1: Xem thông tin cơ sở, cập nhật ảnh thực tế, sửa giờ mở/đóng cửa,
    hotline chính thức và tọa độ GPS định vị thực địa (Chống sân ma).
    """
    template_name = 'owner/facility_manage.html'

    def get_facility(self, request, facility_id=None):
        my_facilities = self.get_owner_facilities(request.user)
        if facility_id:
            facility = get_object_or_404(my_facilities, id=facility_id)
        else:
            facility = my_facilities.first()
        return facility, my_facilities

    def get(self, request, facility_id=None):
        facility, my_facilities = self.get_facility(request, facility_id)
        if not facility:
            messages.warning(request, "Bạn chưa có cụm sân nào để quản lý.")
            return redirect('facilities:facility_list')

        context = {
            'facility': facility,
            'config_facility': facility,
            'selected_facility_id': str(facility.id),
            'my_facilities': my_facilities,
            'active_menu': 'facility_profile',
            'is_subscription_active': request.user.is_subscription_active,
            'subscription_expires_at': getattr(getattr(request.user, 'owner_profile', None), 'subscription_expires_at', None),
        }
        return render(request, self.template_name, context)

    def post(self, request, facility_id=None):
        facility, _ = self.get_facility(request, facility_id)
        if not facility:
            return HttpResponseForbidden("Không tìm thấy cụm sân.")

        facility.name = request.POST.get('name', facility.name).strip()
        facility.address = request.POST.get('address', facility.address).strip()
        facility.hotline = request.POST.get('hotline', facility.hotline).strip()
        facility.phone_contact = facility.hotline or request.POST.get('phone_contact', facility.phone_contact).strip()

        # Giờ mở/đóng cửa
        open_time_str = request.POST.get('open_time')
        close_time_str = request.POST.get('close_time')
        if open_time_str:
            try:
                facility.open_time = datetime.strptime(open_time_str, '%H:%M').time()
            except ValueError:
                pass
        if close_time_str:
            try:
                facility.close_time = datetime.strptime(close_time_str, '%H:%M').time()
            except ValueError:
                pass

        # Tọa độ GPS định vị chống sân ma
        try:
            facility.latitude = float(request.POST.get('latitude', facility.latitude))
            facility.longitude = float(request.POST.get('longitude', facility.longitude))
        except (ValueError, TypeError):
            pass

        # Cấu hình tài khoản ngân hàng nhận tiền trực tiếp
        facility.bank_name = request.POST.get('bank_name', facility.bank_name).strip()
        facility.bank_account_no = request.POST.get('bank_account_no', facility.bank_account_no).strip()
        facility.bank_account_name = request.POST.get('bank_account_name', facility.bank_account_name).strip()

        # Ảnh thực tế & QR riêng
        if 'image' in request.FILES:
            facility.image = request.FILES['image']
        if 'custom_qr_image' in request.FILES:
            facility.custom_qr_image = request.FILES['custom_qr_image']

        facility.save()
        messages.success(request, f"Đã cập nhật thành công thông tin cơ sở và tọa độ GPS của '{facility.name}'!")
        return redirect('facilities:owner_facility_manage_detail', facility_id=facility.id)


class CourtCreateUpdateView(OwnerBaseView):
    """
    Mục tiêu 2.2:
    - Thêm mới / cập nhật sân con (Court) bên trong Cụm sân (Facility).
    - Chọn loại môn: Cầu lông, Pickleball, Bóng bàn.
    - Cấu hình giá theo giờ thường (Off-peak) và giờ cao điểm (Peak).
    - Tự động phát sinh ma trận TimeSlot (BookingSlot) theo bước nhảy 60 phút.
    """
    template_name = 'owner/court_manage.html'

    def get_facility(self, request, facility_id=None):
        my_facilities = self.get_owner_facilities(request.user)
        if facility_id:
            facility = get_object_or_404(my_facilities, id=facility_id)
        else:
            facility = my_facilities.first()
        return facility, my_facilities

    def get(self, request, facility_id=None):
        facility, my_facilities = self.get_facility(request, facility_id)
        if not facility:
            messages.warning(request, "Bạn chưa có cụm sân nào để quản lý sân con.")
            return redirect('facilities:facility_list')

        categories = SportCategory.objects.all()
        courts = facility.courts.select_related('category').all()
        court_id = request.GET.get('edit_court')
        edit_court = None
        if court_id:
            edit_court = facility.courts.filter(id=court_id).first()

        context = {
            'facility': facility,
            'config_facility': facility,
            'selected_facility_id': str(facility.id),
            'my_facilities': my_facilities,
            'active_menu': 'courts',
            'categories': categories,
            'courts': courts,
            'edit_court': edit_court,
        }
        return render(request, self.template_name, context)

    def post(self, request, facility_id=None):
        facility, my_facilities = self.get_facility(request, facility_id)
        if not facility:
            return HttpResponseForbidden("Không tìm thấy cụm sân.")

        court_id = request.POST.get('court_id')
        court_name = request.POST.get('court_name', '').strip()
        category_id = request.POST.get('category_id')
        court_area = request.POST.get('court_area', 'Sân trong nhà')
        surface_type = request.POST.get('surface_type', 'Thảm PVC chuyên dụng')
        is_active = request.POST.get('is_active') == 'on'

        # Giá thường và giá cao điểm
        off_peak_price_val = request.POST.get('off_peak_price', '120000').replace('.', '').replace(',', '')
        peak_price_val = request.POST.get('peak_price', '180000').replace('.', '').replace(',', '')
        try:
            off_peak_price = Decimal(off_peak_price_val)
            peak_price = Decimal(peak_price_val)
        except Exception:
            off_peak_price = Decimal('120000')
            peak_price = Decimal('180000')

        if not court_name or not category_id:
            messages.error(request, "Vui lòng nhập tên sân và chọn môn thể thao.")
            return redirect('facilities:owner_court_manage', facility_id=facility.id)

        category = get_object_or_404(SportCategory, id=category_id)

        if court_id:
            court = get_object_or_404(facility.courts, id=court_id)
            court.court_name = court_name
            court.category = category
            court.court_area = court_area
            court.surface_type = surface_type
            court.is_active = is_active
            court.save()
            action_msg = f"Đã cập nhật sân '{court.court_name}'"
        else:
            court = Court.objects.create(
                facility=facility,
                category=category,
                court_name=court_name,
                court_area=court_area,
                surface_type=surface_type,
                is_active=is_active
            )
            action_msg = f"Đã thêm mới thành công '{court.court_name}'"

        # Thiết lập Quy tắc định giá (PricingRule) cho 7 ngày trong tuần
        # Giờ thường: Mở cửa -> 17:00; Giờ cao điểm: 17:00 -> Đóng cửa
        peak_start_time = time(17, 0)
        facility.pricing_rules.filter(facility=facility).delete() # Cập nhật lại biểu giá chuẩn

        for day in range(7):
            # Khung giờ thường
            PricingRule.objects.create(
                facility=facility,
                day_of_week=day,
                start_time=facility.open_time,
                end_time=peak_start_time,
                price_per_hour=off_peak_price
            )
            # Khung giờ cao điểm
            PricingRule.objects.create(
                facility=facility,
                day_of_week=day,
                start_time=peak_start_time,
                end_time=facility.close_time,
                price_per_hour=peak_price
            )

        # Tự động phát sinh ma trận TimeSlot (chia nhỏ 30 phút) cho ngày hôm nay và 7 ngày tiếp theo
        today = timezone.localdate()
        total_slots_created = 0
        for i in range(8):
            target_date = today + timedelta(days=i)
            total_slots_created += SlotGeneratorService.generate_slots_for_court(
                court=court,
                target_date=target_date
            )

        messages.success(
            request,
            f"{action_msg}! Đã tự động tạo {total_slots_created} slot giờ (chia nhỏ 30 phút) trong 8 ngày tới "
            f"với giá Thường ({int(off_peak_price):,} đ/giờ) & Cao điểm ({int(peak_price):,} đ/giờ)."
        )
        return redirect('facilities:owner_court_manage', facility_id=facility.id)


class OwnerBookingApprovalView(OwnerBaseView):
    """
    Mục tiêu 2.3:
    - Hiển thị danh sách các đơn đặt ở trạng thái WAITING_APPROVAL.
    - Cho phép chủ sân xem ảnh biên lai chuyển khoản (Payment Proof) do khách hàng tải lên.
    - 2 nút hành động:
      + [Xác nhận]: gọi method approve_by_owner() của Booking -> chuyển trạng thái thành CONFIRMED.
      + [Từ chối]: gọi method reject_by_owner(reason) -> chuyển thành REJECTED, giải phóng slot.
    """
    template_name = 'owner/booking_list.html'

    def get(self, request):
        """
        HỢP NHẤT LUỒNG DUYỆT ĐƠN:
        Trang duyệt riêng này được chuyển hướng về Dashboard chủ sân
        (tab=orders) để chỉ còn MỘT nơi duyệt đơn duy nhất.
        """
        facility_id = request.GET.get('facility_id', '')
        status_filter = request.GET.get('status', 'WAITING_APPROVAL')
        query = request.GET.urlencode()
        target = f"/bookings/dashboard/?tab=orders&status={status_filter}"
        if facility_id:
            target += f"&facility_id={facility_id}"
        return redirect(target)

    def post(self, request):
        booking_code = request.POST.get('booking_code')
        action = request.POST.get('action')  # 'approve' hoặc 'reject'
        reject_reason = request.POST.get('reject_reason', 'Không nhận được tiền hoặc ảnh biên lai không hợp lệ.')

        booking = get_object_or_404(Booking, booking_code=booking_code)
        first_slot = booking.slots.select_related('court__facility').first()

        # Kiểm tra thẩm quyền quản lý của chủ sân
        if first_slot and first_slot.court.facility.owner != request.user and not request.user.is_staff:
            return HttpResponseForbidden("Bạn không có quyền quản lý đơn đặt của sân này.")

        # Gọi các phương thức OOP đóng gói trong Model Booking
        if action == 'approve':
            if booking.approve_by_owner(request.user):
                messages.success(request, f"🎉 Đã XÁC NHẬN thành công đơn #{booking.booking_code}! Lịch thi đấu đã chốt.")
            else:
                messages.error(request, f"Không thể duyệt đơn #{booking.booking_code} ở trạng thái hiện tại.")
        elif action == 'reject':
            if booking.reject_by_owner(reject_reason):
                messages.warning(request, f"⚠️ Đã TỪ CHỐI đơn #{booking.booking_code} và giải phóng toàn bộ khung giờ đã giữ.")
            else:
                messages.error(request, f"Không thể từ chối đơn #{booking.booking_code}.")
        else:
            messages.error(request, "Thao tác không hợp lệ.")

        next_url = request.POST.get('next') or '/bookings/dashboard/?tab=orders'
        return redirect(next_url)

