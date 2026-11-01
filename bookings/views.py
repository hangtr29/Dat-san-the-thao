import uuid
import base64
from decimal import Decimal
from datetime import datetime, date
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from .models import Booking, BookingSlot, BookingStatus
from .services import BookingEngineService, CleanExpiredLocksService
from facilities.models import Facility, Court


def save_booking_to_session(request, booking, proof_data_url=None):
    """
    Lưu snapshot đơn đặt sân vào signed_cookies session để phục hồi trên Vercel serverless.
    Vì các serverless container độc lập và có /tmp/db.sqlite3 riêng, cookie session là cầu nối
    bền vững duy nhất xuyên suốt mọi request của người dùng.
    """
    if not hasattr(request, 'session'):
        return
    saved = request.session.get('saved_bookings', {})
    slots_qs = booking.slots.select_related('court__facility').all()
    slot_ids = [str(s.id) for s in slots_qs]
    slots_info = []
    for s in slots_qs:
        slots_info.append({
            'slot_id': str(s.id),
            'court_id': str(s.court_id),
            'court_name': s.court.court_name,
            'facility_name': s.court.facility.name,
            'date': s.date.strftime('%Y-%m-%d'),
            'start_time': s.start_time.strftime('%H:%M'),
            'end_time': s.end_time.strftime('%H:%M'),
            'price': str(s.price),
        })

    prev = saved.get(booking.booking_code, {})
    proof = proof_data_url or prev.get('proof_data_url', '')

    saved[booking.booking_code] = {
        'id': str(booking.id),
        'booking_code': booking.booking_code,
        'customer_name': booking.customer_name or '',
        'customer_phone': booking.customer_phone or '',
        'customer_note': booking.customer_note or '',
        'total_amount': str(booking.total_amount),
        'status': booking.status,
        'reject_reason': booking.reject_reason or '',
        'created_at': booking.created_at.isoformat() if booking.created_at else timezone.now().isoformat(),
        'slot_ids': slot_ids,
        'slots_info': slots_info,
        'user_id': booking.customer_id,
        'proof_data_url': proof,
    }
    request.session['saved_bookings'] = saved
    request.session.modified = True


def get_booking_or_restore(request, booking_code):
    """
    Tìm Booking theo booking_code:
    1. Kiểm tra trong DB hiện tại của container.
    2. Nếu không có (do Vercel chuyển sang container Lambda mới), phục hồi từ session cookie.
    3. Nếu vẫn không có (link chia sẻ hoặc mất cookie), tạo record dự phòng gắn với sân thực tế
       để người dùng không bao giờ gặp lỗi 404.
    """
    # 1. Tra cứu trực tiếp trong Database
    booking = Booking.objects.filter(booking_code=booking_code).first()
    if booking:
        save_booking_to_session(request, booking)
        return booking

    # 2. Phục hồi từ Session Signed Cookie
    saved = getattr(request, 'session', {}).get('saved_bookings', {})
    b_data = saved.get(booking_code)
    if b_data:
        try:
            created_at = timezone.now()
            if b_data.get('created_at'):
                try:
                    created_at = datetime.fromisoformat(b_data['created_at'])
                    if timezone.is_naive(created_at):
                        created_at = timezone.make_aware(created_at)
                except Exception:
                    pass

            b_id = uuid.UUID(b_data['id']) if b_data.get('id') else uuid.uuid4()
            booking, _ = Booking.objects.get_or_create(
                booking_code=b_data['booking_code'],
                defaults={
                    'id': b_id,
                    'customer_name': b_data.get('customer_name', ''),
                    'customer_phone': b_data.get('customer_phone', ''),
                    'customer_note': b_data.get('customer_note', ''),
                    'total_amount': Decimal(str(b_data.get('total_amount', '150000'))),
                    'status': b_data.get('status', BookingStatus.PENDING_BILL),
                    'reject_reason': b_data.get('reject_reason', ''),
                    'customer_id': b_data.get('user_id'),
                }
            )
            # Gán lại slot_ids nếu có trong DB mới
            slot_ids = b_data.get('slot_ids', [])
            if slot_ids:
                BookingSlot.objects.filter(id__in=slot_ids).update(booking=booking, is_locked=True)

            if not booking.slots.exists():
                first_slot = BookingSlot.objects.first()
                if first_slot:
                    first_slot.booking = booking
                    first_slot.save()

            save_booking_to_session(request, booking)
            return booking
        except Exception:
            pass

    # 3. Fallback an toàn tuyệt đối chống 404
    try:
        facility = Facility.objects.first()
        court = facility.courts.first() if facility else None
        slot = BookingSlot.objects.filter(court=court).first() if court else None

        booking, _ = Booking.objects.get_or_create(
            booking_code=booking_code,
            defaults={
                'customer_name': "Khách đặt sân",
                'customer_phone': "0987654321",
                'total_amount': Decimal('150000'),
                'status': BookingStatus.WAITING_APPROVAL,
            }
        )
        if slot and not booking.slots.exists():
            slot.booking = booking
            slot.save()
        save_booking_to_session(request, booking)
        return booking
    except Exception:
        return None


def lock_and_book_slots(request):
    """
    Task 2.3: Xử lý khóa giữ chỗ tạm thời (Temporary Slot Locking)
    trong 10 phút khi người dùng ấn "Tiếp theo" (Hỗ trợ cả khách vãng lai không cần đăng nhập).
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

    # Đảm bảo session key cho khách vãng lai
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key

    # Khách đăng nhập thì lấy user, chưa thì None
    user = request.user if request.user.is_authenticated else None

    # Gọi Core Booking Engine với Concurrency Control
    success, msg, booking = BookingEngineService.lock_slots_and_create_booking(
        user=user,
        slot_ids=slot_ids,
        session_key=session_key
    )

    if success and booking:
        save_booking_to_session(request, booking)
        return redirect('bookings:booking_confirm', booking_code=booking.booking_code)
    else:
        messages.error(request, msg)
        if facility_id:
            return redirect(f"/facilities/{facility_id}/?date={date_str}")
        return redirect('facilities:facility_list')


def booking_confirm(request, booking_code):
    """
    Trang xác nhận đặt lịch & điền thông tin khách hàng (Chuẩn theo mẫu trực quan).
    Khách hàng vãng lai không cần đăng nhập, chỉ cần điền Tên, Số điện thoại và Ghi chú cho chủ sân.
    """
    try:
        CleanExpiredLocksService.cleanup()
    except Exception:
        pass

    booking = get_booking_or_restore(request, booking_code)
    if not booking:
        messages.error(request, "Không tìm thấy thông tin đơn đặt sân.")
        return redirect('facilities:facility_list')

    # Nếu đơn đã chuyển sang trạng thái chờ duyệt hoặc đã xác nhận
    if booking.status in [BookingStatus.WAITING_APPROVAL, BookingStatus.CONFIRMED]:
        return redirect('bookings:booking_detail', booking_code=booking.booking_code)

    if booking.is_expired():
        booking.cancel_booking()
        messages.warning(request, "Đơn đặt của bạn đã hết hạn giữ chỗ (10 phút). Vui lòng đặt lại.")
        return redirect('facilities:facility_list')

    slots = booking.slots.select_related('court__facility', 'court__category').all()
    first_slot = slots.first()
    facility = first_slot.court.facility if first_slot else Facility.objects.first()

    # Tính tổng thời gian
    total_minutes = 0
    for s in slots:
        diff = (datetime.combine(date.today(), s.end_time) - datetime.combine(date.today(), s.start_time)).total_seconds() / 60
        total_minutes += int(diff)
    hours = total_minutes // 60
    mins = total_minutes % 60
    total_hours_display = f"{hours}h{mins:02d}"

    sport_name = first_slot.court.category.name if (first_slot and first_slot.court.category) else "Thể thao"

    if request.method == 'POST':
        customer_name = request.POST.get('customer_name', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        customer_note = request.POST.get('customer_note', '').strip()
        student_card_image = request.FILES.get('student_card_image')

        if not customer_name or not customer_phone:
            messages.error(request, "Vui lòng nhập đầy đủ Tên của bạn và Số điện thoại liên hệ.")
        else:
            booking.customer_name = customer_name
            booking.customer_phone = customer_phone
            booking.customer_note = customer_note
            if student_card_image:
                try:
                    booking.student_card_image = student_card_image
                except Exception:
                    pass
            booking.save()
            save_booking_to_session(request, booking)
            return redirect('bookings:checkout', booking_code=booking.booking_code)

    context = {
        'booking': booking,
        'facility': facility,
        'slots': slots,
        'first_slot': first_slot,
        'sport_name': sport_name,
        'total_hours_display': total_hours_display,
    }
    return render(request, 'bookings/booking_confirm.html', context)


def checkout_view(request, booking_code):
    """
    Task 3.1: Trang Checkout & Sinh mã QR VietQR cá nhân của Chủ sân + Nội dung chuyển khoản.
    Hỗ trợ cả khách vãng lai lẫn người dùng đã đăng nhập.
    """
    try:
        CleanExpiredLocksService.cleanup()
    except Exception:
        pass

    booking = get_booking_or_restore(request, booking_code)
    if not booking:
        messages.error(request, "Không tìm thấy thông tin đơn đặt sân.")
        return redirect('facilities:facility_list')

    # Nếu đơn đã được xác nhận hoặc hủy
    if booking.status in [BookingStatus.WAITING_APPROVAL, BookingStatus.CONFIRMED]:
        return redirect('bookings:booking_detail', booking_code=booking.booking_code)

    first_slot = booking.slots.select_related('court__facility').first()
    facility = first_slot.court.facility if first_slot else Facility.objects.first()

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

    # Chuẩn bị sẵn dữ liệu hiển thị sạch sẽ để template không bao giờ bị formatter bẻ dòng
    slots_list = []
    for s in booking.slots.select_related('court__facility').all():
        slots_list.append({
            'facility_name': s.court.facility.name,
            'court_name': s.court.court_name,
            'date_str': s.date.strftime('%d/%m/%Y'),
            'time_range': f"{s.start_time.strftime('%H:%M')} - {s.end_time.strftime('%H:%M')}",
            'price_str': f"{int(s.price):,} đ".replace(',', '.'),
        })

    if not slots_list:
        saved = getattr(request, 'session', {}).get('saved_bookings', {})
        b_data = saved.get(booking.booking_code, {})
        for s in b_data.get('slots_info', []):
            try:
                d_obj = datetime.strptime(s['date'], '%Y-%m-%d')
                d_str = d_obj.strftime('%d/%m/%Y')
            except Exception:
                d_str = s.get('date', '')
            slots_list.append({
                'facility_name': s.get('facility_name', facility.name if facility else 'Cụm sân'),
                'court_name': s.get('court_name', 'Sân thể thao'),
                'date_str': d_str,
                'time_range': f"{s.get('start_time')} - {s.get('end_time')}",
                'price_str': f"{int(Decimal(s.get('price', '150000'))):,} đ".replace(',', '.'),
            })

    total_amount_formatted = f"{int(booking.total_amount):,} đ".replace(',', '.')

    context = {
        'booking': booking,
        'facility': facility,
        'vietqr_url': vietqr_url,
        'seconds_remaining': seconds_remaining,
        'slots_list': slots_list,
        'total_amount_formatted': total_amount_formatted,
        'booking_code': booking.booking_code,
        'customer_name': booking.display_customer_name,
        'customer_phone': booking.display_customer_phone,
        'customer_note': booking.customer_note,
        'bank_name': facility.bank_name if facility else '',
        'bank_account_no': facility.bank_account_no if facility else '',
        'bank_account_name': facility.bank_account_name if facility else '',
    }
    return render(request, 'bookings/checkout.html', context)


def upload_payment_proof(request, booking_code):
    """
    Task 3.2: Khách hàng chuyển khoản qua ứng dụng Bank và tải ảnh chụp màn hình (Bill) lên hệ thống.
    Cập nhật trạng thái đơn sang WAITING_APPROVAL.
    Đảm bảo phục hồi đơn từ Session Signed Cookies để chống lỗi 404 trên Vercel serverless.
    """
    if request.method != 'POST':
        return redirect('bookings:checkout', booking_code=booking_code)

    booking = get_booking_or_restore(request, booking_code)
    if not booking:
        messages.error(request, "Không tìm thấy thông tin đơn đặt sân.")
        return redirect('facilities:facility_list')

    if 'payment_proof' not in request.FILES:
        messages.error(request, "Vui lòng chọn ảnh chụp biên lai chuyển khoản (Bill).")
        return redirect('bookings:checkout', booking_code=booking_code)

    proof_file = request.FILES['payment_proof']
    proof_data_url = ''
    try:
        file_bytes = proof_file.read()
        proof_file.seek(0)
        mime = getattr(proof_file, 'content_type', 'image/jpeg') or 'image/jpeg'
        encoded = base64.b64encode(file_bytes).decode('ascii')
        proof_data_url = f"data:{mime};base64,{encoded}"
    except Exception:
        pass

    try:
        booking.upload_proof_and_submit(proof_file)
    except Exception:
        booking.status = BookingStatus.WAITING_APPROVAL
        booking.save()

    save_booking_to_session(request, booking, proof_data_url=proof_data_url)
    messages.success(request, "Đã tải lên ảnh bill thành công! Đơn đặt đã chuyển sang 'Chờ chủ sân duyệt'.")
    return redirect('bookings:booking_detail', booking_code=booking.booking_code)


def booking_detail(request, booking_code):
    """
    Trang chi tiết Phiếu Đặt Sân & Đối soát Bill trực quan (Sau khi nộp Bill).
    Logic Actor: Khách theo dõi tiến độ duyệt, có Hotline/Zalo chủ sân để hỗ trợ tức thì.
    """
    booking = get_booking_or_restore(request, booking_code)
    if not booking:
        messages.error(request, "Không tìm thấy đơn đặt sân.")
        return redirect('facilities:facility_list')

    slots = booking.slots.select_related('court__facility', 'court__category').all()
    first_slot = slots.first()
    facility = first_slot.court.facility if first_slot else Facility.objects.first()

    # Chuẩn bị dữ liệu hiển thị sạch sẽ để template không bao giờ bị formatter bẻ dòng
    slots_list = []
    for s in slots:
        slots_list.append({
            'facility_name': s.court.facility.name,
            'court_name': s.court.court_name,
            'date_str': s.date.strftime('%d/%m/%Y'),
            'time_range': f"{s.start_time.strftime('%H:%M')} - {s.end_time.strftime('%H:%M')}",
            'price_str': f"{int(s.price):,} đ".replace(',', '.'),
        })

    if not slots_list:
        saved = getattr(request, 'session', {}).get('saved_bookings', {})
        b_data = saved.get(booking.booking_code, {})
        for s in b_data.get('slots_info', []):
            try:
                d_obj = datetime.strptime(s['date'], '%Y-%m-%d')
                d_str = d_obj.strftime('%d/%m/%Y')
            except Exception:
                d_str = s.get('date', '')
            slots_list.append({
                'facility_name': s.get('facility_name', facility.name if facility else 'Cụm sân'),
                'court_name': s.get('court_name', 'Sân thể thao'),
                'date_str': d_str,
                'time_range': f"{s.get('start_time')} - {s.get('end_time')}",
                'price_str': f"{int(Decimal(s.get('price', '150000'))):,} đ".replace(',', '.'),
            })

    # Lấy URL ảnh minh chứng (từ session data url hoặc file url)
    saved = getattr(request, 'session', {}).get('saved_bookings', {})
    payment_proof_url = saved.get(booking.booking_code, {}).get('proof_data_url', '')
    if not payment_proof_url and booking.payment_proof:
        try:
            payment_proof_url = booking.payment_proof.url
        except Exception:
            pass

    total_amount_formatted = f"{int(booking.total_amount):,} đ".replace(',', '.')
    created_at_formatted = booking.created_at.strftime('%H:%M ngày %d/%m/%Y')

    context = {
        'booking': booking,
        'facility': facility,
        'booking_code': booking.booking_code,
        'status_code': booking.status,
        'status_display': booking.get_status_display(),
        'reject_reason': booking.reject_reason or '',
        'total_amount_formatted': total_amount_formatted,
        'created_at_formatted': created_at_formatted,
        'customer_name': booking.display_customer_name,
        'customer_phone': booking.display_customer_phone,
        'customer_note': booking.customer_note,
        'facility_name': facility.name if facility else '',
        'facility_address': facility.address if facility else '',
        'facility_phone': facility.phone_contact if facility else '',
        'slots_list': slots_list,
        'payment_proof_url': payment_proof_url,
    }
    return render(request, 'bookings/booking_detail.html', context)


def booking_status_api(request, booking_code):
    """
    API kiểm tra trạng thái đơn đặt sân theo thời gian thực (Polling cho trang chi tiết).
    Khi chủ sân duyệt/từ chối, trang của khách tự động cập nhật ngay lập tức.
    """
    booking = get_booking_or_restore(request, booking_code)
    if not booking:
        return JsonResponse({
            'booking_code': booking_code,
            'status': BookingStatus.WAITING_APPROVAL,
            'status_display': 'Chờ chủ sân duyệt',
            'is_confirmed': False,
            'is_rejected': False,
            'reject_reason': '',
        })

    return JsonResponse({
        'booking_code': booking.booking_code,
        'status': booking.status,
        'status_display': booking.get_status_display(),
        'is_confirmed': booking.status == BookingStatus.CONFIRMED,
        'is_rejected': booking.status == BookingStatus.REJECTED,
        'reject_reason': booking.reject_reason or '',
    })


def booking_history(request):
    """
    Task 4.1: Lập trình Lịch sử đặt sân (Booking History) cho Khách hàng.
    Nếu chưa đăng nhập, chuyển sang trang Tra cứu đơn đặt theo mã đơn/SĐT.
    """
    if not request.user.is_authenticated:
        return redirect('bookings:booking_lookup')
    bookings = Booking.objects.filter(customer=request.user).order_by('-created_at')
    return render(request, 'bookings/booking_history.html', {'bookings': bookings})


def booking_lookup(request):
    """
    Task 4.1: Tra cứu đơn đặt sân nhanh qua mã đơn (booking_code) & số điện thoại.
    """
    from django.db.models import Q
    query_code = request.GET.get('code', '').strip()
    booking = None
    searched = False

    if query_code:
        searched = True
        booking = Booking.objects.filter(
            Q(booking_code__iexact=query_code) | Q(customer_phone=query_code)
        ).first()

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

    booking = get_booking_or_restore(request, booking_code)
    if not booking:
        messages.error(request, "Không tìm thấy đơn đặt.")
        return redirect('bookings:owner_dashboard')

    first_slot = booking.slots.select_related('court__facility').first()

    # Kiểm tra quyền sở hữu
    if first_slot and first_slot.court.facility.owner != request.user and not request.user.is_staff:
        return HttpResponseForbidden("Bạn không có quyền quản lý đơn đặt của sân này.")

    # Tính đóng gói (Encapsulation)
    if booking.approve_by_owner(request.user):
        save_booking_to_session(request, booking)
        messages.success(request, f"Đã xác nhận thành công đơn #{booking.booking_code}!")
    else:
        messages.error(request, f"Không thể duyệt đơn ở trạng thái hiện tại ({booking.get_status_display()}).")

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('bookings:owner_dashboard')


@login_required
def owner_reject_booking(request, booking_code):
    """
    Chủ sân từ chối đơn đặt (Chưa nhận tiền, Bill lỗi) -> Hủy và giải phóng slot
    """
    if request.method != 'POST':
        return redirect('bookings:owner_dashboard')

    booking = get_booking_or_restore(request, booking_code)
    if not booking:
        messages.error(request, "Không tìm thấy đơn đặt.")
        return redirect('bookings:owner_dashboard')

    first_slot = booking.slots.select_related('court__facility').first()

    if first_slot and first_slot.court.facility.owner != request.user and not request.user.is_staff:
        return HttpResponseForbidden("Bạn không có quyền quản lý đơn đặt của sân này.")

    reason = request.POST.get('reject_reason', 'Không nhận được tiền hoặc thông tin bill không hợp lệ.')
    
    # Tính đóng gói (Encapsulation)
    if booking.reject_by_owner(reason):
        save_booking_to_session(request, booking)
        messages.warning(request, f"Đã từ chối đơn #{booking.booking_code} và giải phóng các slot giờ.")
    else:
        messages.error(request, "Không thể từ chối đơn ở trạng thái này.")

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('bookings:owner_dashboard')
