import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from .models import Booking, BookingSlot, BookingStatus
from .services import BookingEngineService, CleanExpiredLocksService
from facilities.models import Facility

@login_required
def lock_and_book_slots(request):
    """
    Task 2.3: Xử lý khóa giữ chỗ tạm thời (Temporary Slot Locking)
    trong 10 phút khi người dùng ấn "Tiến hành đặt".
    """
    if request.method != 'POST':
        return redirect('facilities:facility_list')

    slot_ids = request.POST.getlist('slot_ids')
    facility_id = request.POST.get('facility_id')
    date_str = request.POST.get('date')

    if not slot_ids:
        messages.error(request, "Vui lòng chọn ít nhất 1 khung giờ trống trên ma trận.")
        if facility_id:
            return redirect(f"/facilities/{facility_id}/?date={date_str}")
        return redirect('facilities:facility_list')

    # Gọi Core Booking Engine với Atomic Transaction & Concurrency Control
    success, msg, booking = BookingEngineService.lock_slots_and_create_booking(request.user, slot_ids)

    if success and booking:
        messages.success(request, msg)
        return redirect('bookings:checkout', booking_code=booking.booking_code)
    else:
        messages.error(request, msg)
        if facility_id:
            return redirect(f"/facilities/{facility_id}/?date={date_str}")
        return redirect('facilities:facility_list')


@login_required
def checkout_view(request, booking_code):
    """
    Task 3.1: Trang Checkout & Sinh mã QR VietQR cá nhân của Chủ sân + Nội dung chuyển khoản.
    """
    CleanExpiredLocksService.cleanup()

    booking = get_object_or_404(Booking, booking_code=booking_code)
    
    # Đảm bảo đúng khách hàng
    if booking.customer != request.user and not request.user.is_staff:
        return HttpResponseForbidden("Bạn không có quyền truy cập đơn đặt này.")

    # Nếu đơn đã được xác nhận hoặc hủy
    if booking.status in [BookingStatus.WAITING_APPROVAL, BookingStatus.CONFIRMED]:
        return redirect('bookings:booking_detail', booking_code=booking.booking_code)

    first_slot = booking.slots.select_related('court__facility').first()
    facility = first_slot.court.facility if first_slot else None

    # Sinh link VietQR động
    vietqr_url = ""
    if facility:
        vietqr_url = facility.generate_vietqr_url(
            amount=booking.total_amount,
            memo=booking.booking_code
        )

    # Tính thời gian còn lại (10 phút kể từ khi tạo đơn)
    now = timezone.now()
    created_time = booking.created_at
    expires_at = created_time + timezone.timedelta(minutes=10)
    seconds_remaining = max(0, int((expires_at - now).total_seconds()))

    if seconds_remaining <= 0 and booking.status == BookingStatus.PENDING_BILL:
        booking.cancel_booking()
        messages.warning(request, "Đơn đặt của bạn đã hết hạn giữ chỗ (10 phút). Vui lòng đặt lại.")
        return redirect('facilities:facility_list')

    context = {
        'booking': booking,
        'facility': facility,
        'vietqr_url': vietqr_url,
        'seconds_remaining': seconds_remaining,
        'slots': booking.slots.select_related('court').all(),
    }
    return render(request, 'bookings/checkout.html', context)


@login_required
def upload_payment_proof(request, booking_code):
    """
    Task 3.2: Khách hàng chuyển khoản qua ứng dụng Bank và tải ảnh chụp màn hình (Bill) lên hệ thống.
    Cập nhật trạng thái đơn sang WAITING_APPROVAL.
    """
    if request.method != 'POST':
        return redirect('bookings:checkout', booking_code=booking_code)

    booking = get_object_or_404(Booking, booking_code=booking_code, customer=request.user)

    if 'payment_proof' not in request.FILES:
        messages.error(request, "Vui lòng chọn ảnh chụp biên lai chuyển khoản (Bill).")
        return redirect('bookings:checkout', booking_code=booking_code)

    proof_file = request.FILES['payment_proof']
    
    # Tính đóng gói (Encapsulation)
    booking.upload_proof_and_submit(proof_file)
    messages.success(request, "Đã tải lên ảnh bill thành công! Đơn đặt đã chuyển sang 'Chờ chủ sân duyệt'.")
    return redirect('bookings:booking_detail', booking_code=booking.booking_code)


def booking_detail(request, booking_code):
    """
    Chi tiết phiếu đặt sân & đối soát. Hiển thị Hotline/Zalo chủ sân để 2 bên tự giải quyết sự cố.
    """
    booking = get_object_or_404(Booking, booking_code=booking_code)
    first_slot = booking.slots.select_related('court__facility').first()
    facility = first_slot.court.facility if first_slot else None

    context = {
        'booking': booking,
        'facility': facility,
        'slots': booking.slots.all(),
    }
    return render(request, 'bookings/booking_detail.html', context)


@login_required
def booking_history(request):
    """
    Task 4.1: Lập trình Lịch sử đặt sân (Booking History) cho Khách hàng.
    """
    bookings = Booking.objects.filter(customer=request.user).order_by('-created_at')
    return render(request, 'bookings/booking_history.html', {'bookings': bookings})


def booking_lookup(request):
    """
    Task 4.1: Tra cứu đơn đặt sân nhanh qua mã đơn (booking_code) & số điện thoại.
    """
    query_code = request.GET.get('code', '').strip().upper()
    booking = None
    searched = False

    if query_code:
        searched = True
        booking = Booking.objects.filter(booking_code=query_code).first()

    return render(request, 'bookings/booking_lookup.html', {
        'booking': booking,
        'query_code': query_code,
        'searched': searched,
    })


@login_required
def owner_dashboard(request):
    """
    Task 3.3: Dashboard dành riêng cho Chủ sân.
    Hiển thị danh sách đơn chờ duyệt, soi ảnh Bill và nút bấm [Đã nhận tiền / Từ chối].
    """
    if not (request.user.is_owner() or request.user.is_staff):
        messages.warning(request, "Trang này chỉ dành riêng cho Chủ sân.")
        return redirect('facilities:facility_list')

    # Lấy các cụm sân của chủ sân này
    my_facilities = Facility.objects.filter(owner=request.user)

    # Đơn đặt tại các sân của chủ sân này
    status_filter = request.GET.get('status', 'WAITING_APPROVAL')
    
    bookings_qs = Booking.objects.filter(
        slots__court__facility__in=my_facilities
    ).distinct().select_related('customer').prefetch_related('slots__court').order_by('-created_at')

    if status_filter != 'ALL':
        bookings_qs = bookings_qs.filter(status=status_filter)

    # Thống kê nhanh
    pending_count = Booking.objects.filter(
        slots__court__facility__in=my_facilities,
        status=BookingStatus.WAITING_APPROVAL
    ).distinct().count()

    confirmed_count = Booking.objects.filter(
        slots__court__facility__in=my_facilities,
        status=BookingStatus.CONFIRMED
    ).distinct().count()

    context = {
        'my_facilities': my_facilities,
        'bookings': bookings_qs,
        'status_filter': status_filter,
        'pending_count': pending_count,
        'confirmed_count': confirmed_count,
    }
    return render(request, 'bookings/owner_dashboard.html', context)


@login_required
def owner_approve_booking(request, booking_code):
    """
    Chủ sân xác nhận đã nhận được tiền -> Chuyển trạng thái sang CONFIRMED
    """
    if request.method != 'POST':
        return redirect('bookings:owner_dashboard')

    booking = get_object_or_404(Booking, booking_code=booking_code)
    first_slot = booking.slots.select_related('court__facility').first()

    # Kiểm tra quyền sở hữu
    if first_slot and first_slot.court.facility.owner != request.user and not request.user.is_staff:
        return HttpResponseForbidden("Bạn không có quyền quản lý đơn đặt của sân này.")

    # Tính đóng gói (Encapsulation)
    if booking.approve_by_owner(request.user):
        messages.success(request, f"Đã xác nhận thành công đơn #{booking.booking_code}!")
    else:
        messages.error(request, f"Không thể duyệt đơn ở trạng thái hiện tại ({booking.get_status_display()}).")

    return redirect('bookings:owner_dashboard')


@login_required
def owner_reject_booking(request, booking_code):
    """
    Chủ sân từ chối đơn đặt (Chưa nhận tiền, Bill lỗi) -> Hủy và giải phóng slot
    """
    if request.method != 'POST':
        return redirect('bookings:owner_dashboard')

    booking = get_object_or_404(Booking, booking_code=booking_code)
    first_slot = booking.slots.select_related('court__facility').first()

    if first_slot and first_slot.court.facility.owner != request.user and not request.user.is_staff:
        return HttpResponseForbidden("Bạn không có quyền quản lý đơn đặt của sân này.")

    reason = request.POST.get('reject_reason', 'Không nhận được tiền hoặc thông tin bill không hợp lệ.')
    
    # Tính đóng gói (Encapsulation)
    if booking.reject_by_owner(reason):
        messages.warning(request, f"Đã từ chối đơn #{booking.booking_code} và giải phóng các slot giờ.")
    else:
        messages.error(request, "Không thể từ chối đơn ở trạng thái này.")

    return redirect('bookings:owner_dashboard')
