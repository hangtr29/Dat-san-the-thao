"""
Phân hệ Nghiệp vụ dành cho Chủ Sân (Owner Subsystem):
Áp dụng tư duy Hướng đối tượng (OOP), phân quyền Role-based Access Control (RBAC).
Bao gồm:
1. FacilityManageView: Quản lý thông tin Cụm sân, ảnh thực địa, giờ hoạt động, hotline & tọa độ GPS.
2. CourtCreateUpdateView: Thêm/Sửa sân con, định giá giờ thường/cao điểm & tự động sinh ma trận TimeSlot 60 phút.
3. OwnerBookingApprovalView: Quản lý đối soát bill và phê duyệt / từ chối đơn đặt sân.
"""

from datetime import datetime, date, time, timedelta
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
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
            return redirect('users:login')
        if not (request.user.is_owner() or request.user.is_staff):
            messages.error(request, "Bạn không có quyền truy cập Kênh Chủ Sân.")
            return redirect('facilities:facility_list')
        return super().dispatch(request, *args, **kwargs)

    def get_owner_facilities(self, user):
        """Lấy danh sách các cụm sân thuộc quyền sở hữu của user"""
        if user.is_superuser:
            return Facility.objects.all()
        return Facility.objects.filter(owner=user)


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

        # Tự động phát sinh ma trận TimeSlot (60 phút) cho ngày hôm nay và 7 ngày tiếp theo
        today = timezone.localdate()
        total_slots_created = 0
        for i in range(8):
            target_date = today + timedelta(days=i)
            total_slots_created += SlotGeneratorService.generate_slots_for_court(
                court=court,
                target_date=target_date,
                slot_minutes=60
            )

        messages.success(
            request,
            f"{action_msg}! Đã tự động tạo {total_slots_created} slot giờ (60 phút) trong 8 ngày tới với giá Thường ({int(off_peak_price):,} đ) & Cao điểm ({int(peak_price):,} đ)."
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
        my_facilities = self.get_owner_facilities(request.user)
        facility_id = request.GET.get('facility_id')
        status_filter = request.GET.get('status', 'WAITING_APPROVAL')

        target_facilities = my_facilities
        if facility_id:
            target_facilities = my_facilities.filter(id=facility_id)

        # Query danh sách đơn đặt
        bookings_qs = Booking.objects.filter(
            slots__court__facility__in=target_facilities
        ).distinct().select_related('customer').prefetch_related('slots__court__facility').order_by('-created_at')

        if status_filter != 'ALL':
            bookings_qs = bookings_qs.filter(status=status_filter)

        pending_count = Booking.objects.filter(
            slots__court__facility__in=target_facilities,
            status=BookingStatus.WAITING_APPROVAL
        ).distinct().count()

        confirmed_count = Booking.objects.filter(
            slots__court__facility__in=target_facilities,
            status=BookingStatus.CONFIRMED
        ).distinct().count()

        context = {
            'bookings': bookings_qs,
            'my_facilities': my_facilities,
            'config_facility': target_facilities.first(),
            'selected_facility_id': facility_id or (str(target_facilities.first().id) if target_facilities.first() else ''),
            'active_menu': 'approval',
            'status_filter': status_filter,
            'pending_count': pending_count,
            'confirmed_count': confirmed_count,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        booking_code = request.POST.get('booking_code')
        action = request.POST.get('action') # 'approve' hoặc 'reject'
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

        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/facilities/owner/bookings/approval/'
        return redirect(next_url)

