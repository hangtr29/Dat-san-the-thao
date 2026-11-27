import uuid
from decimal import Decimal
from datetime import datetime, date, timedelta
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Q
import json
from .models import Booking, BookingSlot, BookingStatus
from .services import BookingEngineService, CleanExpiredLocksService, SlotGeneratorService
from .services_extras import AddonServiceService, CouponService, RecurringBookingService, NotificationService
from facilities.models import Facility, Court, FacilityStatus


def save_booking_to_session(request, booking, proof_data_url=None):
    """
    Lưu snapshot đơn đặt sân vào signed_cookies session để phục hồi trên Vercel serverless.
    Vì các serverless container độc lập và có /tmp/db.sqlite3 riêng, cookie session là cầu nối
    bền vững duy nhất xuyên suốt mọi request của người dùng.

    LƯU Ý (đã sửa): KHÔNG lưu ảnh bill dạng base64/data-url vào cookie.
    Cookie session bị giới hạn ~4KB, ảnh bill nặng sẽ làm lỗi trang ("Cookie header too large")
    và khiến toàn bộ session mất. Ảnh bill được lưu trong DB (ImageField) / Media storage.
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
        'user_id': str(booking.customer_id) if booking.customer_id else None,
        # Đường dẫn ảnh bill trong media storage (KHÔNG nhúng base64 vào cookie)
        'proof_path': getattr(booking.payment_proof, 'name', '') or '',
    }
    request.session['saved_bookings'] = saved
    if hasattr(request.session, 'modified'):
        request.session.modified = True


def get_booking_or_restore(request, booking_code):
    """
    Tìm Booking theo booking_code:
    1. Kiểm tra trong DB hiện tại của container.
    2. Nếu không có (do Vercel chuyển sang container Lambda mới), phục hồi từ session cookie.
    3. Nếu vẫn không có -> trả về None (KHÔNG tự tạo đơn giả với dữ liệu ghi cứng,
       tránh làm sai lệch dữ liệu và gắp bừa khung giờ của sân thật).

    Bảo mật: Chỉ phục hồi đơn từ session nếu session đó thuộc về chính người đang yêu cầu.
    """
    # 1. Tra cứu trực tiếp trong Database (không phân biệt hoa/thường)
    normalized_code = (booking_code or '').strip().upper()
    booking = Booking.objects.filter(booking_code__iexact=normalized_code).first()
    if booking:
        save_booking_to_session(request, booking)
        return booking

    # 2. Phục hồi từ Session Signed Cookie
    saved = getattr(request, 'session', {}).get('saved_bookings', {})
    b_data = saved.get(normalized_code) or saved.get(booking_code)
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
                    'total_amount': Decimal(str(b_data.get('total_amount', '0'))),
                    'status': b_data.get('status', BookingStatus.PENDING_BILL),
                    'reject_reason': b_data.get('reject_reason', ''),
                    'customer_id': b_data.get('user_id'),
                }
            )
            # Gán lại slot_ids nếu có trong DB mới
            # (đã sửa: trường 'is_locked' KHÔNG tồn tại trong model BookingSlot,
            #  nên lệnh update trước đây luôn lỗi thầm lặng và bị bỏ qua)
            slot_ids = b_data.get('slot_ids', [])
            if slot_ids:
                BookingSlot.objects.filter(id__in=slot_ids).update(booking=booking)

            save_booking_to_session(request, booking)
            return booking
        except Exception:
            pass

    # 3. Không tìm thấy -> trả về None để view báo lỗi "Không tìm thấy đơn đặt sân"
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

    # Lọc chỉ nhận UUID hợp lệ -> tránh ValidationError 500 khi dữ liệu gửi lên sai định dạng
    valid_slot_ids = []
    for raw_id in slot_ids:
        try:
            valid_slot_ids.append(str(uuid.UUID(str(raw_id).strip())))
        except (ValueError, AttributeError, TypeError):
            continue

    if not valid_slot_ids:
        messages.error(request, "Khung giờ không hợp lệ. Vui lòng chọn lại trên bảng lịch.")
        if facility_id:
            return redirect(f"/facilities/{facility_id}/?date={date_str}")
        return redirect('facilities:facility_list')
    slot_ids = valid_slot_ids

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
        # Thông báo cho chủ sân có đơn mới (không cần tải lại trang)
        try:
            NotificationService.notify_owner_new_booking(booking)
        except Exception:
            pass
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
    total_hours_float = round(total_minutes / 60.0, 2) or 1

    sport_name = first_slot.court.category.name if (first_slot and first_slot.court.category) else "Thể thao"

    # Dịch vụ bổ sung (thuê vợt, thức uống...) theo bảng giá riêng của cụm sân
    addon_groups = AddonServiceService.get_services_for_facility(facility)

    if request.method == 'POST':
        customer_name = request.POST.get('customer_name', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        customer_note = request.POST.get('customer_note', '').strip()
        student_card_image = request.FILES.get('student_card_image')
        coupon_code = request.POST.get('coupon_code', '').strip()

        # Thu thập dịch vụ bổ sung khách đã chọn: addon_<service_id> = số lượng
        addon_selections = {}
        for key, value in request.POST.items():
            if key.startswith('addon_') and key != 'addon_services':
                try:
                    qty = int(value)
                except (TypeError, ValueError):
                    qty = 0
                if qty > 0:
                    addon_selections[key[6:]] = qty

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

            # Áp dụng dịch vụ bổ sung và tính lại tổng tiền
            people = AddonServiceService.booking_people(booking)
            AddonServiceService.apply_to_booking(
                booking, addon_selections,
                hours=total_hours_float, people=people,
            )
            booking.recalculate_totals()

            # Áp dụng mã giảm giá
            if coupon_code:
                ok, msg = CouponService.apply(booking, coupon_code, facility)
                if ok:
                    booking.recalculate_totals()
                    messages.success(request, msg)
                else:
                    messages.error(request, msg)
            else:
                booking.coupon = None
                booking.coupon_code = ''
                booking.save(update_fields=['coupon', 'coupon_code'])

            booking.recalculate_totals()
            save_booking_to_session(request, booking)
            return redirect('bookings:checkout', booking_code=booking.booking_code)

    context = {
        'booking': booking,
        'facility': facility,
        'slots': slots,
        'first_slot': first_slot,
        'sport_name': sport_name,
        'total_hours_display': total_hours_display,
        'total_hours_float': total_hours_float,
        'addon_groups': addon_groups,
        'addon_groups_flat': (
            list(facility.addon_services.filter(is_active=True)) if facility else []
        ),
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

    # Dịch vụ phụ khách đã chọn (dùng snapshot tại thời điểm đặt để giá không đổi sau này)
    addons_list = []
    addon_total = 0
    for ba in booking.addons.all():
        qty = ba.quantity or 1
        line_total = ba.subtotal or (ba.unit_price * qty)
        addon_total += line_total
        svc = ba.service
        addons_list.append({
            'name': ba.name,
            'category_label': svc.get_category_display() if svc else 'Dịch vụ',
            'unit_label': svc.get_unit_label() if svc else 'Theo món',
            'quantity': qty,
            'unit_price': f"{int(ba.unit_price):,} đ".replace(',', '.'),
            'line_total': f"{int(line_total):,} đ".replace(',', '.'),
        })
    addon_total_formatted = f"{int(addon_total):,} đ".replace(',', '.')

    context = {
        'booking': booking,
        'facility': facility,
        'vietqr_url': vietqr_url,
        'seconds_remaining': seconds_remaining,
        'slots_list': slots_list,
        'total_amount_formatted': total_amount_formatted,
        'addons_list': addons_list,
        'addon_total_formatted': addon_total_formatted,
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

    try:
        booking.upload_proof_and_submit(proof_file)
    except Exception:
        booking.status = BookingStatus.WAITING_APPROVAL
        booking.save()

    # KHÔNG nhúng ảnh base64 vào cookie session (đã sửa) - chỉ lưu đường dẫn trong media
    save_booking_to_session(request, booking)
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

    # Lấy URL ảnh minh chứng (từ media storage hoặc từ session snapshot)
    saved = getattr(request, 'session', {}).get('saved_bookings', {})
    payment_proof_url = ''
    if booking.payment_proof:
        try:
            payment_proof_url = booking.payment_proof.url
        except Exception:
            payment_proof_url = ''
    if not payment_proof_url:
        proof_path = saved.get(booking.booking_code, {}).get('proof_path', '')
        if proof_path:
            payment_proof_url = f"{settings.MEDIA_URL}{proof_path}"

    # Kiểm tra xem đơn này đã được khách hàng đánh giá hay chưa
    user_review = None
    try:
        from facilities.models import FacilityReview
        user_review = FacilityReview.objects.filter(booking=booking).first()
    except Exception:
        pass

    total_amount_formatted = f"{int(booking.total_amount):,} đ".replace(',', '.')
    created_at_formatted = booking.created_at.strftime('%H:%M ngày %d/%m/%Y')

    # Dịch vụ phụ đã chọn (snapshot tại thời điểm đặt)
    addons_list = []
    addon_total = 0
    for ba in booking.addons.all():
        qty = ba.quantity or 1
        line_total = ba.subtotal or (ba.unit_price * qty)
        addon_total += line_total
        svc = ba.service
        addons_list.append({
            'name': ba.name,
            'category_label': svc.get_category_display() if svc else 'Dịch vụ',
            'unit_label': svc.get_unit_label() if svc else 'Theo món',
            'quantity': qty,
            'unit_price': f"{int(ba.unit_price):,} đ".replace(',', '.'),
            'line_total': f"{int(line_total):,} đ".replace(',', '.'),
        })
    addon_total_formatted = f"{int(addon_total):,} đ".replace(',', '.')

    context = {
        'booking': booking,
        'facility': facility,
        'booking_code': booking.booking_code,
        'status_code': booking.status,
        'status_display': booking.get_status_display(),
        'reject_reason': booking.reject_reason or '',
        'total_amount_formatted': total_amount_formatted,
        'addons_list': addons_list,
        'addon_total_formatted': addon_total_formatted,
        'created_at_formatted': created_at_formatted,
        'customer_name': booking.display_customer_name,
        'customer_phone': booking.display_customer_phone,
        'customer_note': booking.customer_note,
        'facility_name': facility.name if facility else '',
        'facility_address': facility.address if facility else '',
        'facility_phone': facility.phone_contact if facility else '',
        'slots_list': slots_list,
        'payment_proof_url': payment_proof_url,
        'user_review': user_review,
    }
    return render(request, 'bookings/booking_detail.html', context)


def submit_court_review(request, booking_code):
    """
    Khách hàng gửi đánh giá chất lượng sân (Review & Rating 1-5 sao).
    Điều kiện: Chỉ khách hàng có mã đơn đặt sân đã được duyệt thành công (CONFIRMED) mới được đánh giá.
    Mỗi đơn đặt chỉ được đánh giá 1 lần duy nhất (1 booking = 1 review chống spam).
    """
    if request.method != 'POST':
        return redirect('bookings:booking_detail', booking_code=booking_code)

    booking = get_booking_or_restore(request, booking_code)
    if not booking:
        messages.error(request, "Không tìm thấy thông tin đơn đặt sân.")
        return redirect('facilities:facility_list')

    if booking.status != BookingStatus.CONFIRMED:
        messages.error(request, "Chỉ đơn đặt sân đã được Chủ sân xác nhận thành công mới có thể gửi đánh giá.")
        return redirect('bookings:booking_detail', booking_code=booking.booking_code)

    first_slot = booking.slots.select_related('court__facility').first()
    facility = first_slot.court.facility if first_slot else Facility.objects.first()
    if not facility:
        messages.error(request, "Không tìm thấy cụm sân cần đánh giá.")
        return redirect('bookings:booking_detail', booking_code=booking.booking_code)

    try:
        from facilities.models import FacilityReview
        if FacilityReview.objects.filter(booking=booking).exists():
            messages.warning(request, "Đơn đặt này đã được gửi đánh giá trước đó rồi. Xin cảm ơn bạn!")
            return redirect('bookings:booking_detail', booking_code=booking.booking_code)

        rating = int(request.POST.get('rating', 5))
        if rating < 1 or rating > 5:
            rating = 5
        comment = request.POST.get('comment', '').strip()
        reviewer_name = booking.display_customer_name

        FacilityReview.objects.create(
            facility=facility,
            booking=booking,
            user=booking.customer,
            reviewer_name=reviewer_name,
            rating=rating,
            comment=comment
        )
        # Thông báo cho chủ sân biết khách vừa đánh giá (tương tác 2 chiều)
        try:
            review = FacilityReview.objects.filter(booking=booking).first()
            if review:
                NotificationService.notify_owner_new_review(review)
        except Exception:
            pass

        messages.success(request, "🎉 Cảm ơn bạn đã gửi đánh giá chất lượng sân! Đánh giá đã được ghi nhận.")
    except Exception as e:
        messages.error(request, f"Không thể lưu đánh giá: {e}")

    return redirect('bookings:booking_detail', booking_code=booking.booking_code)


def customer_cancel_booking(request, booking_code):
    """
    Khách hàng HỦY đơn đặt sân thủ công.

    Trước đây khách KHÔNG có cách hủy đơn (chỉ hủy tự động khi quá hạn 10 phút),
    và khi khách hủy thì chủ sân không hề hay biết -> chủ sân bị mất lịch âm thầm.
    Sau khi triển khai:
      - Khách hủy -> giải phóng slot -> CHỦ SÂN nhận thông báo ngay.
    """
    if request.method != 'POST':
        return redirect('bookings:booking_detail', booking_code=booking_code)

    booking = get_booking_or_restore(request, booking_code)
    if not booking:
        messages.error(request, "Không tìm thấy thông tin đơn đặt sân.")
        return redirect('facilities:facility_list')

    # Chỉ được hủy khi đơn chưa được chủ sân duyệt/xác nhận
    if booking.status in [BookingStatus.CONFIRMED]:
        messages.error(
            request,
            "Đơn đã được chủ sân xác nhận. Vui lòng liên hệ trực tiếp hotline của cụm sân để hỗ trợ đổi lịch.",
        )
        return redirect('bookings:booking_detail', booking_code=booking.booking_code)

    reason = request.POST.get('cancel_reason', '').strip()

    previous_status = booking.status

    # Thông báo cho CHỦ SÂN biết khách đã hủy (gửi TRƯỚC khi giải phóng slot,
    # vì sau khi release_slot() thì booking.slots sẽ rỗng & không tra được cụm sân)
    try:
        NotificationService.notify_owner_booking_cancelled(booking, reason)
    except Exception:
        pass

    if previous_status == BookingStatus.PENDING_BILL:
        booking.cancel_booking()
    elif previous_status in [BookingStatus.WAITING_APPROVAL, BookingStatus.NEEDS_REUPLOAD]:
        # Hủy khi đang chờ duyệt: chuyển CANCELLED và giải phóng slot
        booking.status = BookingStatus.CANCELLED
        booking.save()
        for slot in booking.slots.all():
            slot.release_slot()
    else:
        messages.warning(request, "Không thể hủy đơn ở trạng thái hiện tại.")
        return redirect('bookings:booking_detail', booking_code=booking.booking_code)

    messages.success(request, "Đã hủy đơn đặt sân. Chủ sân đã được thông báo về việc hủy của bạn.")
    return redirect('bookings:booking_detail', booking_code=booking.booking_code)


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
        'is_rejected_hard': booking.status == BookingStatus.REJECTED,
        'needs_reupload': booking.status == BookingStatus.NEEDS_REUPLOAD,
        'reject_reason': booking.reject_reason or '',
    })


def coupon_validate_api(request):
    """
    API kiểm tra mã giảm giá / khuyến mãi (không tạo side-effect).
    Dùng cho nút "Áp dụng" ở trang xác nhận đặt sân.
    """
    code = (request.GET.get('code') or '').strip()
    booking_code = request.GET.get('booking_code') or ''
    if not code:
        return JsonResponse({'valid': False, 'message': 'Vui lòng nhập mã giảm giá.'})

    order_value = 0
    facility = None
    if booking_code:
        booking = Booking.objects.filter(booking_code=booking_code).first()
        if booking:
            order_value = booking.total_amount
            facility = booking.facility
    else:
        order_value = 0

    coupon, msg = CouponService.validate(code, order_value, facility)
    if not coupon:
        return JsonResponse({'valid': False, 'message': msg or 'Mã giảm giá không hợp lệ.'})
    return JsonResponse({
        'valid': True,
        'code': coupon.code,
        'message': f"Áp dụng mã {coupon.code}: giảm {coupon.calculate_discount(order_value):,} đ.",
        'discount': coupon.calculate_discount(order_value),
    })


def upload_payment_proof_retry(request, booking_code):
    """
    Khách tải lại bill khi đơn bị chủ sân từ chối (bill sai/lỗi).
    GIỮ NGUYÊN khung giờ đã giữ chỗ - không phải đặt lại từ đầu.
    """
    if request.method != 'POST':
        return redirect('bookings:booking_detail', booking_code=booking_code)

    booking = get_booking_or_restore(request, booking_code)
    if not booking:
        messages.error(request, "Không tìm thấy đơn đặt sân.")
        return redirect('facilities:facility_list')

    if booking.status not in [BookingStatus.REJECTED, BookingStatus.NEEDS_REUPLOAD]:
        messages.warning(request, "Đơn này hiện không cần tải lại bill.")
        return redirect('bookings:booking_detail', booking_code=booking.booking_code)

    if 'payment_proof' not in request.FILES:
        messages.error(request, "Vui lòng chọn ảnh bill chuyển khoản mới.")
        return redirect('bookings:booking_detail', booking_code=booking.booking_code)

    try:
        booking.reupload_proof_and_submit(request.FILES['payment_proof'])
        NotificationService.notify_booking_status(booking, BookingStatus.WAITING_APPROVAL)
        save_booking_to_session(request, booking)
        messages.success(request, "Đã tải lại bill thành công! Đơn của bạn đang chờ chủ sân duyệt lại.")
    except Exception as e:
        messages.error(request, f"Không tải lại được bill: {e}")

    return redirect('bookings:booking_detail', booking_code=booking.booking_code)


def booking_print(request, booking_code):
    """
    Trang in / lưu phiếu đặt sân (Phiếu thanh toán A4).
    Khách có thể in ra (Ctrl+P) hoặc lưu thành PDF từ trình duyệt.
    """
    booking = get_booking_or_restore(request, booking_code)
    if not booking:
        messages.error(request, "Không tìm thấy đơn đặt sân.")
        return redirect('facilities:facility_list')

    slots = booking.slots.select_related('court__facility', 'court__category').all()
    first_slot = slots.first()
    facility = first_slot.court.facility if first_slot else None

    slots_list = []
    for s in slots:
        slots_list.append({
            'court_name': s.court.court_name,
            'facility_name': s.court.facility.name,
            'category_name': s.court.category.name if s.court.category else '',
            'date_str': s.date.strftime('%d/%m/%Y'),
            'time_range': f"{s.start_time.strftime('%H:%M')} - {s.end_time.strftime('%H:%M')}",
            'price_str': f"{int(s.price):,} đ".replace(',', '.'),
        })

    addons_list = [
        {
            'name': a.name,
            'qty': a.quantity,
            'price_str': f"{int(a.unit_price):,} đ".replace(',', '.'),
            'subtotal_str': f"{int(a.subtotal):,} đ".replace(',', '.'),
        }
        for a in booking.addons.all()
    ]

    context = {
        'booking': booking,
        'facility': facility,
        'booking_code': booking.booking_code,
        'status_display': booking.get_status_display(),
        'customer_name': booking.display_customer_name,
        'customer_phone': booking.display_customer_phone,
        'slots_list': slots_list,
        'addons_list': addons_list,
        'court_amount_str': f"{int(booking.court_amount or 0):,} đ".replace(',', '.'),
        'addon_amount_str': f"{int(booking.addon_amount or 0):,} đ".replace(',', '.'),
        'discount_amount_str': f"{int(booking.discount_amount or 0):,} đ".replace(',', '.'),
        'total_amount_str': f"{int(booking.total_amount):,} đ".replace(',', '.'),
        'created_at_str': booking.created_at.strftime('%H:%M ngày %d/%m/%Y'),
        'print_time': timezone.now().strftime('%H:%M ngày %d/%m/%Y'),
    }
    return render(request, 'bookings/booking_print.html', context)


def recurring_booking_create(request):
    """
    Đặt lịch cố định theo tuần (Recurring booking).
    Khách chọn cụm sân, sân, khung giờ, ngày bắt đầu/kết thúc -> hệ thống tạo chuỗi đơn hàng tuần.
    """
    if request.method != 'POST':
        return redirect('facilities:facility_list')

    facility_id = request.POST.get('facility_id', '')
    court_id = request.POST.get('court_id', '')
    start_date_str = request.POST.get('start_date', '')
    end_date_str = request.POST.get('end_date', '')
    start_time_str = request.POST.get('start_time', '')
    end_time_str = request.POST.get('end_time', '')
    note = request.POST.get('note', '').strip()

    try:
        facility = Facility.objects.get(
            id=facility_id,
            active_status=True,
            status=FacilityStatus.ACTIVE,
            is_verified=True,
        )
        court = Court.objects.get(id=court_id, facility=facility)
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
    except Exception:
        messages.error(request, "Thông tin lịch cố định không hợp lệ. Vui lòng kiểm tra lại.")
        return redirect('facilities:facility_list')

    user = request.user if request.user.is_authenticated else None
    bookings, msg = RecurringBookingService.create_weekly_series(
        user, facility, court, start_date, end_date, start_time, end_time, note=note
    )
    if bookings:
        messages.success(request, msg)
        return redirect('bookings:booking_history')
    messages.error(request, msg)
    return redirect('facilities:facility_list')


def recurring_booking_list(request):
    """Danh sách các lịch đặt cố định theo tuần của khách"""
    if not request.user.is_authenticated:
        return redirect('bookings:booking_lookup')
    series = RecurringBookingService.get_user_series(request.user)
    return render(request, 'bookings/recurring_list.html', {'series': series})


@login_required
def notification_list(request):
    """
    Trung tâm thông báo kiểu Gmail:
      - Lọc theo tab: Tất cả / Chưa đọc (unread) / Đã đọc (read)
      - Nhóm theo ngày: HÔM NAY / HÔM QUA / CŨ HƠN
      - Đánh dấu đã đọc hàng loạt, đánh dấu đã đọc/chưa đọc từng cái
    """
    from .models import Notification

    qs = Notification.objects.filter(user=request.user)

    tab = request.GET.get('tab', 'all')
    if tab == 'unread':
        qs = qs.filter(is_read=False)
    elif tab == 'read':
        qs = qs.filter(is_read=True)

    notifications = list(qs[:150])

    # Nhóm theo ngày (giống Gmail)
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    groups = {'today': [], 'yesterday': [], 'older': []}
    for n in notifications:
        created_date = timezone.localtime(n.created_at).date()
        if created_date == today:
            groups['today'].append(n)
        elif created_date == yesterday:
            groups['yesterday'].append(n)
        else:
            groups['older'].append(n)

    grouped_labels = [
        ('today', 'Hôm nay'),
        ('yesterday', 'Hôm qua'),
        ('older', 'Cũ hơn'),
    ]

    return render(request, 'bookings/notifications.html', {
        'notifications': notifications,
        'groups': groups,
        'grouped_labels': grouped_labels,
        'tab': tab,
        'unread_count': NotificationService.unread_count(request.user),
        'read_count': Notification.objects.filter(user=request.user, is_read=True).count(),
        'total_count': Notification.objects.filter(user=request.user).count(),
    })


@login_required
def notification_mark_all_read(request):
    """Đánh dấu ĐÃ ĐỌC toàn bộ thông báo (nút 'Đánh dấu đã đọc' kiểu Gmail)"""
    from .models import Notification
    updated = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'ok': True,
            'updated': updated,
            'unread_count': NotificationService.unread_count(request.user),
        })
    return redirect('bookings:notification_list')


@login_required
def notification_toggle_read(request, notification_id):
    """
    Bật/tắt trạng thái đã đọc của MỘT thông báo (click chấm tròn tròn giống Gmail).
    Nhấn lần 1 -> đánh dấu đã đọc. Nhấn lần 2 -> chuyển lại thành chưa đọc.
    """
    from .models import Notification
    notif = get_object_or_404(Notification, id=notification_id, user=request.user)
    notif.is_read = not notif.is_read
    notif.save(update_fields=['is_read'])
    return JsonResponse({
        'ok': True,
        'id': str(notif.id),
        'is_read': notif.is_read,
        'unread_count': NotificationService.unread_count(request.user),
    })


@login_required
def notification_api(request):
    """API polling cho badge thông báo (không cần tải lại trang)"""
    from .models import Notification
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'ok': True})

    # Lấy cả đã đọc lẫn chưa đọc (mới nhất trước) để dropdown giống Gmail
    items = []
    for n in Notification.objects.filter(user=request.user).order_by('-created_at')[:15]:
        items.append({
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'url': n.link or '#',
            'is_read': n.is_read,
            'type': n.notification_type,
            'time_ago': n.created_at.strftime('%H:%M %d/%m/%Y'),
        })

    return JsonResponse({
        'unread_count': NotificationService.unread_count(request.user),
        'notifications': items,
    })


@login_required
def notification_mark_read(request):
    """Đánh dấu đã đọc một thông báo (POST JSON: {id: n})"""
    from .models import Notification
    notif_id = None
    if request.method == 'POST':
        content_type = (request.content_type or '')
        if 'application/json' in content_type:
            try:
                notif_id = (json.loads(request.body or '{}') or {}).get('id')
            except Exception:
                notif_id = None
        if notif_id is None:
            notif_id = request.POST.get('id')
    else:
        notif_id = request.GET.get('id')

    if notif_id:
        Notification.objects.filter(id=notif_id, user=request.user).update(is_read=True)
    else:
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'ok': True, 'unread_count': NotificationService.unread_count(request.user)})


def booking_history(request):
    """
    Task 4.1: Lập trình Lịch sử đặt sân (Booking History) cho Khách hàng.
    Có phân trang (9 đơn / trang) và lọc theo trạng thái.
    Nếu chưa đăng nhập, chuyển sang trang Tra cứu đơn đặt theo mã đơn/SĐT.
    """
    if not request.user.is_authenticated:
        return redirect('bookings:booking_lookup')

    bookings = Booking.objects.filter(customer=request.user).order_by('-created_at')

    # Lọc theo trạng thái
    status_filter = request.GET.get('status', 'ALL')
    if status_filter != 'ALL' and status_filter in BookingStatus.values:
        bookings = bookings.filter(status=status_filter)

    # Tìm kiếm theo mã đơn
    query = request.GET.get('q', '').strip()
    if query:
        bookings = bookings.filter(booking_code__icontains=query)

    # Phân trang
    from django.core.paginator import Paginator
    paginator = Paginator(bookings, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Thống kê nhanh
    all_bookings = Booking.objects.filter(customer=request.user)
    stats = {
        'total': all_bookings.count(),
        'pending': all_bookings.filter(status=BookingStatus.WAITING_APPROVAL).count(),
        'confirmed': all_bookings.filter(status=BookingStatus.CONFIRMED).count(),
        'cancelled': all_bookings.filter(status__in=[BookingStatus.CANCELLED, BookingStatus.REJECTED]).count(),
    }

    return render(request, 'bookings/booking_history.html', {
        'bookings': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'status_filter': status_filter,
        'query': query,
        'stats': stats,
    })


def booking_lookup(request):
    """
    Tra cứu đơn đặt sân nhanh qua mã đơn (booking_code) & số điện thoại.

    BẢO MẬT (đã sửa):
    - Tra cứu bằng SỐ ĐIỆN THOẠI giờ yêu cầu đăng nhập (hoặc chỉ chính chủ tài khoản
      mới được xem chi tiết). Trước đây ai biết SĐT cũng xem được toàn bộ chi tiết đơn.
    - Tra cứu bằng MÃ ĐƠN vẫn hoạt động cho khách vãng lai (mã đơn là bí mật ngẫu nhiên
      8 ký tự, không thể dò tuần tự trong thời gian hợp lý).
    """
    from django.db.models import Q

    query_code = request.GET.get('code', '').strip()
    booking = None
    searched = False
    lookup_denied = False
    lookup_by_phone = False

    if query_code:
        searched = True

        # Phân biệt mã đơn (tiền tố BK) với số điện thoại
        is_phone_query = query_code.replace(' ', '').replace('.', '').replace('-', '').isdigit() \
            and not query_code.upper().startswith('BK')

        if is_phone_query:
            lookup_by_phone = True
            # Chỉ chủ tài khoản đã đăng nhập mới được tra cứu bằng SĐT
            if not request.user.is_authenticated:
                lookup_denied = True
            else:
                booking = Booking.objects.filter(
                    Q(customer_phone=query_code) & Q(customer=request.user)
                ).first()
                # Fallback phục hồi từ session cookie trên Vercel serverless
                if not booking:
                    saved = getattr(request, 'session', {}).get('saved_bookings', {})
                    for code_key, b_data in saved.items():
                        if b_data.get('customer_phone') == query_code and str(b_data.get('user_id')) == str(request.user.id):
                            booking = get_booking_or_restore(request, code_key)
                            break
        else:
            # Tra cứu bằng mã đơn (không yêu cầu đăng nhập; có fallback phục hồi từ session cookie trên Vercel)
            booking = get_booking_or_restore(request, query_code)

    return render(request, 'bookings/booking_lookup.html', {
        'booking': booking,
        'query_code': query_code,
        'searched': searched,
        'lookup_denied': lookup_denied,
        'lookup_by_phone': lookup_by_phone,
    })


def booking_terms(request):
    """
    Trang Điều khoản đặt sân (thay thế link chết "href='#'").
    """
    return render(request, 'bookings/booking_terms.html', {'policy_type': 'terms'})


def booking_refund_policy(request):
    """
    Trang Chính sách hoàn tiền & huỷ lịch (thay thế link chết "href='#'").
    """
    return render(request, 'bookings/booking_refund_policy.html', {'policy_type': 'refund'})


def _get_managed_facilities(user):
    """Admin giám sát toàn bộ cụm sân trên nền tảng; Chủ sân chỉ quản lý cụm sân thuộc sở hữu của mình."""
    if getattr(user, 'role', '') == 'ADMIN' or user.is_superuser:
        return Facility.objects.all().order_by('name')
    return Facility.objects.filter(owner=user).order_by('name')


@login_required
def owner_dashboard(request):
    """
    Task 3.3 & Giai đoạn 2: Dashboard dành riêng cho Chủ sân.
    - Thống kê doanh thu: Hôm nay, Tháng này, Tổng tích lũy.
    - Dữ liệu biểu đồ 7 ngày gần nhất cho Chart.js.
    - Quản lý duyệt đơn / từ chối bill.
    - Bộ lọc thời gian & Tự động xuất báo cáo (Excel/CSV & PDF).
    """
    if not (request.user.is_owner() or request.user.is_staff):
        messages.warning(request, "Trang này chỉ dành riêng cho Chủ sân.")
        return redirect('facilities:facility_list')

    from django.db.models import Sum
    from datetime import timedelta

    my_facilities = _get_managed_facilities(request.user)
    facility_id = request.GET.get('facility_id', '')
    status_filter = request.GET.get('status', 'WAITING_APPROVAL')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    # Tìm kiếm đơn theo mã đơn hoặc số điện thoại khách
    search_query = (request.GET.get('q', '') or '').strip()

    target_facilities = my_facilities
    if facility_id:
        target_facilities = my_facilities.filter(id=facility_id)

    # Đơn đặt lọc theo trạng thái
    bookings_qs = Booking.objects.filter(
        slots__court__facility__in=target_facilities
    ).distinct().select_related('customer').prefetch_related('slots__court').order_by('-created_at')

    if status_filter != 'ALL':
        bookings_qs = bookings_qs.filter(status=status_filter)
    if date_from:
        bookings_qs = bookings_qs.filter(created_at__date__gte=date_from)
    if date_to:
        bookings_qs = bookings_qs.filter(created_at__date__lte=date_to)
    if search_query:
        bookings_qs = bookings_qs.filter(
            Q(booking_code__icontains=search_query)
            | Q(customer__phone__icontains=search_query)
            | Q(customer__first_name__icontains=search_query)
            | Q(customer__last_name__icontains=search_query)
            | Q(customer__username__icontains=search_query)
        )

    # Đếm số lượng
    pending_count = Booking.objects.filter(
        slots__court__facility__in=target_facilities,
        status=BookingStatus.WAITING_APPROVAL
    ).distinct().count()

    confirmed_count = Booking.objects.filter(
        slots__court__facility__in=target_facilities,
        status=BookingStatus.CONFIRMED
    ).distinct().count()

    today = timezone.localdate()
    # 1. Doanh thu hôm nay
    revenue_today = Booking.objects.filter(
        slots__court__facility__in=target_facilities,
        status=BookingStatus.CONFIRMED,
        created_at__date=today
    ).distinct().aggregate(total=Sum('total_amount'))['total'] or 0

    # 2. Doanh thu tháng này
    first_day_month = today.replace(day=1)
    revenue_month = Booking.objects.filter(
        slots__court__facility__in=target_facilities,
        status=BookingStatus.CONFIRMED,
        created_at__date__gte=first_day_month
    ).distinct().aggregate(total=Sum('total_amount'))['total'] or 0

    # 3. Tổng doanh thu tích lũy
    revenue_total = Booking.objects.filter(
        slots__court__facility__in=target_facilities,
        status=BookingStatus.CONFIRMED
    ).distinct().aggregate(total=Sum('total_amount'))['total'] or 0

    # 4. Doanh thu trong khoảng đang lọc
    revenue_filtered = bookings_qs.filter(status=BookingStatus.CONFIRMED).aggregate(total=Sum('total_amount'))['total'] or 0

    # 5. Dữ liệu 7 ngày gần nhất vẽ biểu đồ Chart.js
    daily_labels = []
    daily_revenues = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        rev = Booking.objects.filter(
            slots__court__facility__in=target_facilities,
            status=BookingStatus.CONFIRMED,
            created_at__date=d
        ).distinct().aggregate(total=Sum('total_amount'))['total'] or 0
        daily_labels.append(d.strftime('%d/%m'))
        daily_revenues.append(int(rev))

    from facilities.models import FacilityReview

    active_tab = request.GET.get('tab', 'orders')
    reviews_qs = FacilityReview.objects.filter(
        facility__in=target_facilities
    ).select_related('facility', 'booking').order_by('-created_at')

    # Cụm sân đang được chọn để cấu hình
    config_facility = target_facilities.first()
    if facility_id:
        config_facility = my_facilities.filter(id=facility_id).first() or config_facility

    current_facility_id = facility_id or (str(config_facility.id) if config_facility else '')

    # Phân trang danh sách đơn (15 đơn / trang)
    from django.core.paginator import Paginator
    bookings_list = list(bookings_qs)
    paginator = Paginator(bookings_list, 15)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except Exception:
        page_obj = paginator.page(1)

    context = {
        'my_facilities': my_facilities,
        'selected_facility_id': current_facility_id,
        'config_facility': config_facility,
        'active_tab': active_tab,
        'bookings': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'search_query': search_query,
        'reviews': reviews_qs,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'pending_count': pending_count,
        'confirmed_count': confirmed_count,
        'revenue_today_str': f"{int(revenue_today):,} đ".replace(',', '.'),
        'revenue_month_str': f"{int(revenue_month):,} đ".replace(',', '.'),
        'revenue_total_str': f"{int(revenue_total):,} đ".replace(',', '.'),
        'revenue_filtered_str': f"{int(revenue_filtered):,} đ".replace(',', '.'),
        'daily_labels_json': daily_labels,
        'daily_revenues_json': daily_revenues,
    }
    return render(request, 'bookings/owner_dashboard.html', context)


@login_required
def owner_export_revenue_csv(request):
    """
    Giai đoạn 3: Tự động xuất báo cáo doanh thu dạng file Excel / CSV cho Chủ sân.
    Sử dụng UTF-8 BOM (\ufeff) để Microsoft Excel mở trực tiếp hiển thị tiếng Việt hoàn hảo không lỗi font.
    """
    if not (request.user.is_owner() or request.user.is_staff):
        return HttpResponseForbidden("Chỉ Chủ sân mới có quyền xuất báo cáo doanh thu.")

    import csv
    from django.http import HttpResponse

    my_facilities = _get_managed_facilities(request.user)
    facility_id = request.GET.get('facility_id', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    target_facilities = my_facilities
    if facility_id:
        target_facilities = my_facilities.filter(id=facility_id)

    bookings_qs = Booking.objects.filter(
        slots__court__facility__in=target_facilities,
        status=BookingStatus.CONFIRMED
    ).distinct().select_related('customer').prefetch_related('slots__court__facility').order_by('-created_at')

    if date_from:
        bookings_qs = bookings_qs.filter(created_at__date__gte=date_from)
    if date_to:
        bookings_qs = bookings_qs.filter(created_at__date__lte=date_to)

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    timestamp_str = timezone.now().strftime('%Y%m%d_%H%M')
    response['Content-Disposition'] = f'attachment; filename="Bao_Cao_Doanh_Thu_SportBook_{timestamp_str}.csv"'

    writer = csv.writer(response)
    writer.writerow(['BÁO CÁO THỐNG KÊ DOANH THU ĐẶT SÂN - HỆ THỐNG SPORTBOOK'])
    writer.writerow(['Chủ sân / Quản trị:', request.user.get_full_name() or request.user.username])
    writer.writerow(['Thời gian kết xuất:', timezone.now().strftime('%H:%M ngày %d/%m/%Y')])
    writer.writerow(['Khoảng thời gian:', f"{date_from or 'Từ đầu'} đến {date_to or 'Hiện tại'}"])
    writer.writerow([])
    writer.writerow(['STT', 'Mã Đơn Đặt', 'Thời Gian Tạo', 'Khách Hàng', 'Số Điện Thoại', 'Cụm Sân', 'Sân Thi Đấu', 'Khung Giờ Đặt', 'Doanh Thu (VNĐ)', 'Trạng Thái'])

    total_revenue = Decimal('0')
    count = 0
    for idx, b in enumerate(bookings_qs, start=1):
        count += 1
        total_revenue += b.total_amount
        slots = b.slots.select_related('court__facility').all()
        courts_str = ", ".join(set(s.court.court_name for s in slots))
        times_str = ", ".join(f"{s.date.strftime('%d/%m')} ({s.start_time.strftime('%H:%M')}-{s.end_time.strftime('%H:%M')})" for s in slots)
        fac_name = slots[0].court.facility.name if slots else "N/A"

        writer.writerow([
            idx,
            b.booking_code,
            b.created_at.strftime('%d/%m/%Y %H:%M'),
            b.display_customer_name,
            b.display_customer_phone,
            fac_name,
            courts_str,
            times_str,
            int(b.total_amount),
            b.get_status_display()
        ])

    writer.writerow([])
    writer.writerow(['TỔNG KẾT:', f'Số đơn hoàn tất: {count}', '', '', '', '', '', 'TỔNG DOANH THU (VNĐ):', int(total_revenue)])

    return response


@login_required
def owner_export_revenue_pdf(request):
    """
    Giai đoạn 3: Giao diện In ấn / Xuất Báo Cáo Doanh Thu chuẩn khổ giấy A4 (Print to PDF).
    Bao gồm đầy đủ tiêu đề, kỳ báo cáo, bảng kê chi tiết, tổng kết tài chính và chữ ký phê duyệt.
    """
    if not (request.user.is_owner() or request.user.is_staff):
        return HttpResponseForbidden("Chỉ Chủ sân mới có quyền xem báo cáo doanh thu.")

    my_facilities = _get_managed_facilities(request.user)
    facility_id = request.GET.get('facility_id', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    target_facilities = my_facilities
    if facility_id:
        target_facilities = my_facilities.filter(id=facility_id)

    bookings_qs = Booking.objects.filter(
        slots__court__facility__in=target_facilities,
        status=BookingStatus.CONFIRMED
    ).distinct().select_related('customer').prefetch_related('slots__court__facility').order_by('-created_at')

    if date_from:
        bookings_qs = bookings_qs.filter(created_at__date__gte=date_from)
    if date_to:
        bookings_qs = bookings_qs.filter(created_at__date__lte=date_to)

    total_revenue = sum(b.total_amount for b in bookings_qs)
    total_count = bookings_qs.count()

    context = {
        'bookings': bookings_qs,
        'total_revenue': total_revenue,
        'total_revenue_formatted': f"{int(total_revenue):,} đ".replace(',', '.'),
        'total_count': total_count,
        'date_from': date_from,
        'date_to': date_to,
        'export_time': timezone.now().strftime('%H:%M ngày %d/%m/%Y'),
        'owner_name': request.user.get_full_name() or request.user.username,
        'my_facilities': my_facilities,
        'facility_selected': my_facilities.filter(id=facility_id).first() if facility_id else None,
    }
    return render(request, 'bookings/owner_revenue_report_print.html', context)


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
        NotificationService.notify_booking_status(booking, BookingStatus.CONFIRMED)
        messages.success(request, f"Đã xác nhận thành công đơn #{booking.booking_code}!")
    else:
        messages.error(request, f"Không thể duyệt đơn ở trạng thái hiện tại ({booking.get_status_display()}).")

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        if next_url.startswith('?'):
            next_url = f"/bookings/dashboard/{next_url}"
        return redirect(next_url)
    return redirect('bookings:owner_dashboard')


@login_required
def owner_reject_booking(request, booking_code):
    """
    Chủ sân từ chối đơn đặt (Chưa nhận tiền, Bill lỗi).

    Mặc định: chuyển sang NEEDS_REUPLOAD - GIỮ NGUYÊN khung giờ để khách chỉ cần
    tải lại bill (không phải đặt lại từ đầu).
    Nếu chọn "Từ chối hẳn": giải phóng toàn bộ slot.
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

    reason = request.POST.get('reject_reason', 'Không nhận được tiền hoặc thông tin bill không hợp lệ.').strip()
    allow_reupload = request.POST.get('allow_reupload', '1') != '0'

    # Tính đóng gói (Encapsulation)
    if booking.reject_by_owner(reason, allow_reupload=allow_reupload):
        save_booking_to_session(request, booking)
        if allow_reupload:
            NotificationService.notify_booking_status(booking, BookingStatus.NEEDS_REUPLOAD)
            messages.warning(
                request,
                f"Đã yêu cầu khách tải lại bill cho đơn #{booking.booking_code}. "
                "Khung giờ vẫn được giữ cho khách."
            )
        else:
            NotificationService.notify_booking_status(booking, BookingStatus.REJECTED)
            messages.warning(request, f"Đã từ chối đơn #{booking.booking_code} và giải phóng các slot giờ.")
    else:
        messages.error(request, "Không thể từ chối đơn ở trạng thái này.")

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        if next_url.startswith('?'):
            next_url = f"/bookings/dashboard/{next_url}"
        return redirect(next_url)
    return redirect('bookings:owner_dashboard')


@login_required
def owner_update_facility(request):
    """
    Cập nhật thông tin cụm sân, thông tin ngân hàng VietQR và ảnh bìa ngay trên giao diện Chủ Sân.
    """
    if not (request.user.is_owner() or request.user.is_staff):
        return HttpResponseForbidden("Chỉ Chủ sân mới có quyền cập nhật thông tin sân.")

    if request.method != 'POST':
        return redirect('bookings:owner_dashboard')

    facility_id = request.POST.get('facility_id')
    facility = Facility.objects.filter(id=facility_id).first()
    if not facility:
        messages.error(request, "Không tìm thấy cụm sân.")
        return redirect('bookings:owner_dashboard')

    if facility.owner != request.user and not request.user.is_staff:
        return HttpResponseForbidden("Bạn không có quyền quản lý cụm sân này.")

    facility.name = request.POST.get('name', facility.name).strip()
    facility.address = request.POST.get('address', facility.address).strip()
    facility.phone_contact = request.POST.get('phone_contact', facility.phone_contact).strip()
    facility.bank_name = request.POST.get('bank_name', facility.bank_name).strip()
    facility.bank_account_no = request.POST.get('bank_account_no', facility.bank_account_no).strip()
    facility.bank_account_name = request.POST.get('bank_account_name', facility.bank_account_name).strip()

    if 'image' in request.FILES:
        facility.image = request.FILES['image']
    if 'custom_qr_image' in request.FILES:
        facility.custom_qr_image = request.FILES['custom_qr_image']

    facility.save()
    messages.success(request, f"Đã lưu thành công thông tin & cấu hình VietQR cho sân '{facility.name}'!")
    return redirect(f"{request.POST.get('next') or '/bookings/dashboard/'}?tab=settings&facility_id={facility.id}")


@login_required
def owner_reply_review(request, review_id):
    """
    Chủ sân phản hồi đánh giá của khách hàng ngay trên giao diện web.
    """
    if not (request.user.is_owner() or request.user.is_staff):
        return HttpResponseForbidden("Chỉ Chủ sân mới có quyền phản hồi đánh giá.")

    if request.method != 'POST':
        return redirect('bookings:owner_dashboard')

    from facilities.models import FacilityReview
    review = FacilityReview.objects.filter(id=review_id).first()
    if not review:
        messages.error(request, "Không tìm thấy đánh giá.")
        return redirect('bookings:owner_dashboard')

    if review.facility.owner != request.user and not request.user.is_staff:
        return HttpResponseForbidden("Bạn không có quyền quản lý cụm sân này.")

    reply_text = request.POST.get('owner_reply', '').strip()
    review.owner_reply = reply_text
    review.owner_reply_at = timezone.now() if reply_text else None
    review.save()

    # Thông báo cho KHÁCH biết chủ sân đã phản hồi (tương tác 2 chiều)
    if reply_text:
        try:
            NotificationService.notify_customer_owner_reply(review)
        except Exception:
            pass

    messages.success(request, "Đã cập nhật phản hồi của Chủ sân thành công!")
    return redirect(f"{request.POST.get('next') or '/bookings/dashboard/'}?tab=reviews")


# ============================================================================
#                    KÊNH CHỦ SÂN - CÁC TÍNH NĂNG MỚI
# ============================================================================


@login_required
def owner_booking_detail(request, booking_code):
    """Xem chi tiết đầy đủ một đơn đặt (chủ sân)"""
    if not (request.user.is_owner() or request.user.is_staff):
        return HttpResponseForbidden("Chỉ Chủ sân mới có quyền xem chi tiết đơn đặt.")

    booking = Booking.objects.filter(booking_code=booking_code).first()
    if not booking:
        messages.error(request, "Không tìm thấy đơn đặt.")
        return redirect('bookings:owner_dashboard')

    slots = booking.slots.select_related('court__facility', 'court__category').all()
    if slots:
        facility = slots.first().court.facility
        if facility.owner != request.user and not request.user.is_staff:
            return HttpResponseForbidden("Bạn không có quyền xem đơn đặt của sân này.")

    slots_list = [{
        'court_name': s.court.court_name,
        'category_name': s.court.category.name if s.court.category else '',
        'date_str': s.date.strftime('%d/%m/%Y'),
        'time_range': f"{s.start_time.strftime('%H:%M')} - {s.end_time.strftime('%H:%M')}",
        'price_str': f"{int(s.price):,} đ".replace(',', '.'),
    } for s in slots]

    addons_list = [{
        'name': a.name,
        'qty': a.quantity,
        'subtotal_str': f"{int(a.subtotal):,} đ".replace(',', '.'),
    } for a in booking.addons.all()]

    proof_url = ''
    if booking.payment_proof:
        try:
            proof_url = booking.payment_proof.url
        except Exception:
            proof_url = ''

    context = {
        'booking': booking,
        'booking_code': booking.booking_code,
        'status_display': booking.get_status_display(),
        'customer_name': booking.display_customer_name,
        'customer_phone': booking.display_customer_phone,
        'customer_note': booking.customer_note,
        'slots_list': slots_list,
        'addons_list': addons_list,
        'proof_url': proof_url,
        'court_amount_str': f"{int(booking.court_amount or 0):,} đ".replace(',', '.'),
        'addon_amount_str': f"{int(booking.addon_amount or 0):,} đ".replace(',', '.'),
        'discount_amount_str': f"{int(booking.discount_amount or 0):,} đ".replace(',', '.'),
        'total_amount_str': f"{int(booking.total_amount):,} đ".replace(',', '.'),
        'created_at_str': booking.created_at.strftime('%H:%M ngày %d/%m/%Y'),
    }
    return render(request, 'bookings/owner_booking_detail.html', context)


@login_required
def owner_calendar(request):
    """
    Lịch xem nhanh: sân nào trống / đã đặt theo NGÀY và TUẦN.
    Chế độ ngày: ma trận sân x khung giờ trong 1 ngày.
    Chế độ tuần: bảng tổng hợp 7 ngày x các sân (số khung giờ đã đặt / tổng).
    """
    if not (request.user.is_owner() or request.user.is_staff):
        return HttpResponseForbidden("Chỉ Chủ sân mới có quyền xem lịch.")

    my_facilities = _get_managed_facilities(request.user)
    facility_id = request.GET.get('facility_id', '')
    target_facilities = my_facilities
    if facility_id:
        target_facilities = my_facilities.filter(id=facility_id)
    facility = target_facilities.first()

    today = timezone.localdate()
    view_mode = request.GET.get('view', 'day')

    try:
        date_offset = int(request.GET.get('offset', '0'))
    except ValueError:
        date_offset = 0

    if view_mode == 'week':
        start_of_week = today + timedelta(days=date_offset * 7)
        week_dates = [start_of_week + timedelta(days=i) for i in range(7)]
    else:
        target_date = today + timedelta(days=date_offset)
        week_dates = [target_date]

    context = {
        'my_facilities': my_facilities,
        'selected_facility_id': facility_id or (str(facility.id) if facility else ''),
        'facility': facility,
        'view_mode': view_mode,
        'date_offset': date_offset,
        'today': today,
        'week_dates': week_dates,
        'day_grid': [],
        'week_rows': [],
        'week_labels': ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'Chủ Nhật'],
    }

    if not facility:
        return render(request, 'bookings/owner_calendar.html', context)

    courts = list(facility.courts.filter(is_active=True).select_related('category').order_by('court_name'))

    # Sinh slot cho các ngày cần xem
    for d in week_dates:
        try:
            SlotGeneratorService.generate_slots_for_facility(facility, d)
        except Exception:
            pass

    if view_mode == 'week':
        # Mỗi dòng = 1 sân, mỗi cột = 1 ngày trong tuần
        rows = []
        for court in courts:
            cells = []
            for d in week_dates:
                slots = BookingSlot.objects.filter(court=court, date=d).select_related('booking')
                booked = [s for s in slots if s.booking and s.booking.status in [
                    BookingStatus.WAITING_APPROVAL, BookingStatus.CONFIRMED, BookingStatus.NEEDS_REUPLOAD
                ]]
                cells.append({
                    'date': d,
                    'total': len(slots),
                    'booked': len(booked),
                    'free': len(slots) - len(booked),
                    'revenue': sum(s.price for s in booked),
                })
            rows.append({'court': court, 'cells': cells})
        context['week_rows'] = rows
    else:
        # Ma trận ngày: sân x khung giờ
        target_date = week_dates[0]
        slots = BookingSlot.objects.filter(
            court__in=courts, date=target_date
        ).select_related('booking').order_by('start_time')
        time_headers = sorted(set((s.start_time, s.end_time) for s in slots), key=lambda x: x[0])
        slot_map = {(s.court_id, s.start_time): s for s in slots}

        rows = []
        for court in courts:
            cells = []
            for start_t, end_t in time_headers:
                slot = slot_map.get((court.id, start_t))
                status = 'free'
                booking_code = ''
                if slot and slot.booking:
                    if slot.booking.status == BookingStatus.CONFIRMED:
                        status = 'confirmed'
                    elif slot.booking.status in [BookingStatus.WAITING_APPROVAL, BookingStatus.NEEDS_REUPLOAD]:
                        status = 'pending'
                    booking_code = slot.booking.booking_code
                cells.append({
                    'slot': slot,
                    'status': status,
                    'booking_code': booking_code,
                    'start_time': start_t,
                    'end_time': end_t,
                })
            rows.append({'court': court, 'cells': cells})
        context['day_grid'] = rows
        context['time_headers'] = time_headers
        context['target_date'] = target_date

    return render(request, 'bookings/owner_calendar.html', context)


@login_required
def owner_export_excel(request):
    """
    Xuất báo cáo Excel THẬT (.xlsx) dùng thư viện openpyxl.
    Báo cáo gồm 3 sheet: Tổng hợp, Theo cụm sân, Theo môn thể thao.
    """
    if not (request.user.is_owner() or request.user.is_staff):
        return HttpResponseForbidden("Chỉ Chủ sân mới có quyền xuất báo cáo.")

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse

    my_facilities = _get_managed_facilities(request.user)
    facility_id = request.GET.get('facility_id', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    report_type = request.GET.get('type', 'all')  # all | facility | sport

    target_facilities = my_facilities
    if facility_id:
        target_facilities = my_facilities.filter(id=facility_id)

    bookings_qs = Booking.objects.filter(
        slots__court__facility__in=target_facilities,
        status=BookingStatus.CONFIRMED
    ).distinct().select_related('customer').prefetch_related('slots__court__category').order_by('-created_at')

    if date_from:
        bookings_qs = bookings_qs.filter(created_at__date__gte=date_from)
    if date_to:
        bookings_qs = bookings_qs.filter(created_at__date__lte=date_to)

    wb = Workbook()

    # --- Style helpers ---
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="166534", end_color="166534", fill_type="solid")
    title_font = Font(bold=True, size=14, color="166534")
    thin = Side(style='thin', color='D1D5DB')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    money_fmt = '#,##0 "đ"'

    def style_header(ws, row_idx, ncols):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=row_idx, column=c)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = border

    def auto_width(ws, min_width=12, max_width=42):
        for col in ws.columns:
            letter = get_column_letter(col[0].column)
            length = 0
            for cell in col:
                if cell.value is not None:
                    try:
                        length = max(length, len(str(cell.value)))
                    except Exception:
                        pass
            ws.column_dimensions[letter].width = min(max(length + 3, min_width), max_width)

    # ================= SHEET 1: TỔNG HỢP =================
    ws = wb.active
    ws.title = "Tổng hợp"
    ws["A1"] = "BÁO CÁO DOANH THU ĐẶT SÂN - SPORTBOOK"
    ws["A1"].font = title_font
    ws["A2"] = f"Chủ sân: {request.user.get_full_name() or request.user.username}"
    ws["A3"] = f"Khoảng thời gian: {date_from or 'Từ đầu'} đến {date_to or 'Hiện tại'}"
    ws["A4"] = f"Kết xuất lúc: {timezone.now().strftime('%H:%M ngày %d/%m/%Y')}"

    headers = ['STT', 'Mã đơn', 'Thời gian tạo', 'Khách hàng', 'Số điện thoại',
               'Cụm sân', 'Sân thi đấu', 'Môn thể thao', 'Khung giờ', 'Giá sân',
               'Tiền dịch vụ', 'Giảm giá', 'Tổng thanh toán']
    header_row = 6
    for i, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=i, value=h)
    style_header(ws, header_row, len(headers))

    total_revenue = Decimal('0')
    total_court = Decimal('0')
    total_addon = Decimal('0')
    row = header_row + 1
    for idx, b in enumerate(bookings_qs, start=1):
        slots = b.slots.all()
        court_names = ", ".join(sorted(set(s.court.court_name for s in slots)))
        sport_names = ", ".join(sorted(set(s.court.category.name for s in slots if s.court.category)))
        fac_names = ", ".join(sorted(set(s.court.facility.name for s in slots)))
        times = ", ".join(
            f"{s.date.strftime('%d/%m')} ({s.start_time.strftime('%H:%M')}-{s.end_time.strftime('%H:%M')})"
            for s in sorted(slots, key=lambda x: (x.date, x.start_time))
        )
        court_total = sum((s.price for s in slots), Decimal('0'))
        total_court += court_total
        total_addon += Decimal(b.addon_amount or 0)
        total_revenue += Decimal(b.total_amount or 0)

        ws.cell(row=row, column=1, value=idx)
        ws.cell(row=row, column=2, value=b.booking_code)
        ws.cell(row=row, column=3, value=b.created_at.strftime('%d/%m/%Y %H:%M'))
        ws.cell(row=row, column=4, value=b.display_customer_name)
        ws.cell(row=row, column=5, value=b.display_customer_phone)
        ws.cell(row=row, column=6, value=fac_names)
        ws.cell(row=row, column=7, value=court_names)
        ws.cell(row=row, column=8, value=sport_names)
        ws.cell(row=row, column=9, value=times)
        ws.cell(row=row, column=10, value=float(court_total)).number_format = money_fmt
        ws.cell(row=row, column=11, value=float(b.addon_amount or 0)).number_format = money_fmt
        ws.cell(row=row, column=12, value=float(b.discount_amount or 0)).number_format = money_fmt
        ws.cell(row=row, column=13, value=float(b.total_amount or 0)).number_format = money_fmt
        for c in range(1, len(headers) + 1):
            ws.cell(row=row, column=c).border = border
        row += 1

    # Dòng tổng kết
    ws.cell(row=row, column=1, value="TỔNG KẾT")
    ws.cell(row=row, column=2, value=f"{bookings_qs.count()} đơn hoàn tất")
    ws.cell(row=row, column=10, value=float(total_court)).number_format = money_fmt
    ws.cell(row=row, column=11, value=float(total_addon)).number_format = money_fmt
    ws.cell(row=row, column=13, value=float(total_revenue)).number_format = money_fmt
    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
        cell.border = border
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    auto_width(ws)

    # ================= SHEET 2: THEO CỤM SÂN =================
    ws2 = wb.create_sheet("Theo cụm sân")
    ws2["A1"] = "BÁO CÁO TÁCH THEO TỪNG CỤM SÂN"
    ws2["A1"].font = title_font
    h2 = ['Cụm sân', 'Số đơn', 'Số khung giờ', 'Tiền sân', 'Tiền dịch vụ', 'Giảm giá', 'Tổng doanh thu', 'Tỷ lệ %']
    for i, h in enumerate(h2, start=1):
        ws2.cell(row=3, column=i, value=h)
    style_header(ws2, 3, len(h2))

    agg = {}
    for b in bookings_qs:
        slots = b.slots.all()
        for s in slots:
            key = s.court.facility.name
            d = agg.setdefault(key, {'orders': set(), 'slots': 0, 'court': Decimal('0'),
                                    'addon': Decimal('0'), 'discount': Decimal('0'), 'total': Decimal('0')})
            d['orders'].add(b.id)
            d['slots'] += 1
            d['court'] += s.price
        d2 = agg[next(iter(s.court.facility.name for s in slots))]
        d2['addon'] += Decimal(b.addon_amount or 0)
        d2['discount'] += Decimal(b.discount_amount or 0)
        d2['total'] += Decimal(b.total_amount or 0)

    r = 4
    for fac_name, d in sorted(agg.items(), key=lambda x: -x[1]['total']):
        pct = (d['total'] / total_revenue * 100) if total_revenue else 0
        ws2.cell(row=r, column=1, value=fac_name)
        ws2.cell(row=r, column=2, value=len(d['orders']))
        ws2.cell(row=r, column=3, value=d['slots'])
        ws2.cell(row=r, column=4, value=float(d['court'])).number_format = money_fmt
        ws2.cell(row=r, column=5, value=float(d['addon'])).number_format = money_fmt
        ws2.cell(row=r, column=6, value=float(d['discount'])).number_format = money_fmt
        ws2.cell(row=r, column=7, value=float(d['total'])).number_format = money_fmt
        ws2.cell(row=r, column=8, value=round(float(pct), 2)).number_format = '0.00"%"'
        for c in range(1, len(h2) + 1):
            ws2.cell(row=r, column=c).border = border
        r += 1
    ws2.cell(row=r, column=1, value="TỔNG CỘNG").font = Font(bold=True)
    ws2.cell(row=r, column=7, value=float(total_revenue)).number_format = money_fmt
    ws2.cell(row=r, column=7).font = Font(bold=True)
    auto_width(ws2)

    # ================= SHEET 3: THEO MÔN THỂ THAO =================
    ws3 = wb.create_sheet("Theo môn thể thao")
    ws3["A1"] = "BÁO CÁO TÁCH THEO MÔN THỂ THAO"
    ws3["A1"].font = title_font
    h3 = ['Môn thể thao', 'Số đơn', 'Số khung giờ', 'Tiền sân', 'Tiền dịch vụ', 'Tổng doanh thu', 'Tỷ lệ %']
    for i, h in enumerate(h3, start=1):
        ws3.cell(row=3, column=i, value=h)
    style_header(ws3, 3, len(h3))

    agg3 = {}
    for b in bookings_qs:
        slots = b.slots.all()
        for s in slots:
            sport = s.court.category.name if s.court.category else 'Khác'
            d = agg3.setdefault(sport, {'orders': set(), 'slots': 0, 'court': Decimal('0'), 'total': Decimal('0')})
            d['orders'].add(b.id)
            d['slots'] += 1
            d['court'] += s.price
            d['total'] += Decimal(b.total_amount or 0) / max(1, len(slots))

    r = 4
    for sport, d in sorted(agg3.items(), key=lambda x: -x[1]['total']):
        pct = (d['total'] / total_revenue * 100) if total_revenue else 0
        ws3.cell(row=r, column=1, value=sport)
        ws3.cell(row=r, column=2, value=len(d['orders']))
        ws3.cell(row=r, column=3, value=d['slots'])
        ws3.cell(row=r, column=4, value=float(d['court'])).number_format = money_fmt
        ws3.cell(row=r, column=5, value=float(total_addon)).number_format = money_fmt
        ws3.cell(row=r, column=6, value=float(d['total'])).number_format = money_fmt
        ws3.cell(row=r, column=7, value=round(float(pct), 2)).number_format = '0.00"%"'
        for c in range(1, len(h3) + 1):
            ws3.cell(row=r, column=c).border = border
        r += 1
    ws3.cell(row=r, column=1, value="TỔNG CỘNG").font = Font(bold=True)
    ws3.cell(row=r, column=6, value=float(total_revenue)).number_format = money_fmt
    ws3.cell(row=r, column=6).font = Font(bold=True)
    auto_width(ws3)

    timestamp_str = timezone.now().strftime('%Y%m%d_%H%M')
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="Bao_Cao_Doanh_Thu_{timestamp_str}.xlsx"'
    wb.save(response)
    return response


@login_required
def owner_manage_addons(request):
    """
    Quản lý bảng giá dịch vụ bổ sung (thuê vợt, thức uống) của từng cụm sân.
    Chủ sân tự sửa giá - không còn giá ghi cứng chung cho mọi sân.
    """
    if not (request.user.is_owner() or request.user.is_staff):
        return HttpResponseForbidden("Chỉ Chủ sân mới có quyền quản lý dịch vụ.")

    my_facilities = _get_managed_facilities(request.user)
    facility_id = request.GET.get('facility_id') or request.POST.get('facility_id')
    facility = None
    if facility_id:
        facility = my_facilities.filter(id=facility_id).first()
    else:
        facility = my_facilities.first()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'delete':
            from facilities.models import AddonService
            svc = AddonService.objects.filter(id=request.POST.get('service_id'), facility=facility).first()
            if svc:
                svc.delete()
                messages.success(request, f"Đã xóa dịch vụ '{svc.name}'.")
            return redirect(f"{request.POST.get('next') or '/bookings/dashboard/'}?tab=services&facility_id={facility.id}")

        if action == 'toggle':
            from facilities.models import AddonService
            svc = AddonService.objects.filter(id=request.POST.get('service_id'), facility=facility).first()
            if svc:
                svc.is_active = not svc.is_active
                svc.save(update_fields=['is_active'])
                messages.success(request, "Đã cập nhật trạng thái dịch vụ.")
            return redirect(f"{request.POST.get('next') or '/bookings/dashboard/'}?tab=services&facility_id={facility.id}")

        if action in ('add', 'update'):
            from facilities.models import AddonService
            from decimal import Decimal as D
            service_id = request.POST.get('service_id')
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, "Vui lòng nhập tên dịch vụ.")
                return redirect(f"/bookings/dashboard/?tab=services&facility_id={facility.id}")

            try:
                price = D((request.POST.get('unit_price', '0') or '0').replace('.', '').replace(',', ''))
            except Exception:
                price = D('0')

            svc = AddonService.objects.filter(id=service_id, facility=facility).first() if service_id else None
            if svc:
                svc.name = name
                svc.description = request.POST.get('description', '').strip()
                svc.category = request.POST.get('category', 'DRINK')
                svc.unit_type = request.POST.get('unit_type', 'PER_ITEM')
                svc.unit_price = price
                svc.is_active = request.POST.get('is_active') == 'on'
                svc.save()
                messages.success(request, f"Đã cập nhật dịch vụ '{svc.name}'.")
            else:
                AddonService.objects.create(
                    facility=facility,
                    name=name,
                    description=request.POST.get('description', '').strip(),
                    category=request.POST.get('category', 'DRINK'),
                    unit_type=request.POST.get('unit_type', 'PER_ITEM'),
                    unit_price=price,
                    is_active=request.POST.get('is_active') == 'on',
                )
                messages.success(request, f"Đã thêm dịch vụ '{name}'.")
            return redirect(f"{request.POST.get('next') or '/bookings/dashboard/'}?tab=services&facility_id={facility.id}")

    services = []
    if facility:
        services = list(facility.addon_services.all())

    from facilities.models import AddonService
    context = {
        'my_facilities': my_facilities,
        'selected_facility_id': str(facility.id) if facility else '',
        'config_facility': facility,
        'facility': facility,
        'services': services,
        'unit_choices': AddonService.UNIT_CHOICES,
        'category_choices': AddonService.CATEGORY_CHOICES,
        'edit_service': None,
    }
    edit_id = request.GET.get('edit')
    if edit_id:
        context['edit_service'] = AddonService.objects.filter(id=edit_id, facility=facility).first()

    return render(request, 'bookings/owner_services.html', context)


@login_required
def owner_manage_gallery(request):
    """
    Quản lý thư viện ảnh + mô tả giới thiệu của cụm sân.
    Chủ sân có thể viết mô tả và đăng nhiều ảnh minh hoạ.
    """
    if not (request.user.is_owner() or request.user.is_staff):
        return HttpResponseForbidden("Chỉ Chủ sân mới có quyền quản lý ảnh.")

    my_facilities = _get_managed_facilities(request.user)
    facility_id = request.GET.get('facility_id') or request.POST.get('facility_id')
    facility = None
    if facility_id:
        facility = my_facilities.filter(id=facility_id).first()
    else:
        facility = my_facilities.first()

    if not facility:
        messages.warning(request, "Bạn chưa có cụm sân nào.")
        return redirect('bookings:owner_dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'delete_image':
            from facilities.models import FacilityGalleryImage
            img = FacilityGalleryImage.objects.filter(id=request.POST.get('image_id'), facility=facility).first()
            if img:
                img.delete()
                messages.success(request, "Đã xoá ảnh khỏi thư viện.")
            return redirect(f"/bookings/dashboard/?tab=gallery&facility_id={facility.id}")

        if action == 'update_caption':
            from facilities.models import FacilityGalleryImage
            img = FacilityGalleryImage.objects.filter(id=request.POST.get('image_id'), facility=facility).first()
            if img:
                img.caption = request.POST.get('caption', '').strip()
                img.save(update_fields=['caption'])
                messages.success(request, "Đã cập nhật chú thích ảnh.")
            return redirect(f"/bookings/dashboard/?tab=gallery&facility_id={facility.id}")

        if action == 'save_profile':
            facility.description = request.POST.get('description', '').strip()
            facility.highlights = request.POST.get('highlights', '').strip()
            facility.save(update_fields=['description', 'highlights'])
            messages.success(request, "Đã lưu mô tả giới thiệu cụm sân.")
            return redirect(f"/bookings/dashboard/?tab=gallery&facility_id={facility.id}")

        if action == 'upload':
            from facilities.models import FacilityGalleryImage
            images = request.FILES.getlist('gallery_images')
            captions = request.POST.getlist('captions')
            count = 0
            for i, img in enumerate(images):
                cap = captions[i] if i < len(captions) else ''
                FacilityGalleryImage.objects.create(
                    facility=facility,
                    image=img,
                    caption=cap.strip(),
                    sort_order=FacilityGalleryImage.objects.filter(facility=facility).count(),
                )
                count += 1
            if count:
                messages.success(request, f"Đã đăng {count} ảnh lên thư viện cụm sân!")
            else:
                messages.warning(request, "Chưa chọn ảnh nào để tải lên.")
            return redirect(f"/bookings/dashboard/?tab=gallery&facility_id={facility.id}")

    context = {
        'my_facilities': my_facilities,
        'selected_facility_id': str(facility.id),
        'config_facility': facility,
        'facility': facility,
        'gallery_images': facility.gallery_images.all(),
    }
    return render(request, 'bookings/owner_gallery.html', context)


@login_required
def owner_kyc(request):
    """
    Gửi hồ sơ xác thực (KYC) + mua/gia hạn gói duy trì từ giao diện Chủ sân.
    Trước đây hệ thống tự duyệt sẵn - nay chủ sân phải nộp hồ sơ thật.
    """
    if not (request.user.is_owner() or request.user.is_staff):
        return HttpResponseForbidden("Chỉ Chủ sân mới có quyền thực hiện thao tác này.")

    from users.models import OwnerProfile, SubscriptionPlan, SubscriptionOrder, KYCStatus
    from django.utils import timezone as tz

    profile, _ = OwnerProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'submit_kyc':
            profile.id_card_number = request.POST.get('id_card_number', '').strip()
            profile.bank_name = request.POST.get('bank_name', '').strip()
            profile.bank_account_number = request.POST.get('bank_account_number', '').strip()
            profile.bank_account_holder = request.POST.get('bank_account_holder', '').strip()
            if 'id_card_front' in request.FILES:
                profile.id_card_front = request.FILES['id_card_front']
            if 'id_card_back' in request.FILES:
                profile.id_card_back = request.FILES['id_card_back']
            if 'business_license' in request.FILES:
                profile.business_license = request.FILES['business_license']
            if 'bank_qr_image' in request.FILES:
                profile.bank_qr_image = request.FILES['bank_qr_image']
            # Chủ sân nộp hồ sơ -> chờ Ban quản trị duyệt (KHÔNG tự duyệt sẵn)
            profile.kyc_status = KYCStatus.KYC_PENDING
            profile.kyc_rejection_reason = ''
            profile.save()

            # Thông báo cho Ban quản trị biết có hồ sơ KYC mới chờ duyệt
            from users.models import User
            for admin in User.objects.filter(is_superuser=True).exclude(pk=request.user.pk):
                NotificationService.notify(
                    admin, 'SYSTEM',
                    "Hồ sơ xác thực KYC chủ sân mới chờ duyệt",
                    f"{request.user.get_full_name() or request.user.username} vừa gửi hồ sơ KYC. "
                    f"Vui lòng kiểm tra CCCD, giấy phép KD và thông tin ngân hàng.",
                    "/admin/users/ownerprofile/?kyc_status__exact=KYC_PENDING",
                )

            messages.success(request, "Đã gửi hồ sơ xác thực! Ban quản trị sẽ kiểm tra và phản hồi.")
            return redirect('bookings:owner_kyc')

        if action == 'buy_plan':
            plan_id = request.POST.get('plan_id')
            plan = SubscriptionPlan.objects.filter(id=plan_id, is_active=True).first()
            if not plan:
                messages.error(request, "Không tìm thấy gói dịch vụ.")
                return redirect('bookings:owner_kyc')

            order_code = f"SUB{tz.now().strftime('%Y%m%d%H%M%S')}"
            SubscriptionOrder.objects.create(
                order_code=order_code,
                owner=request.user,
                plan=plan,
                amount=plan.price,
                status='PENDING',
            )
            if 'payment_proof' in request.FILES:
                order = SubscriptionOrder.objects.filter(order_code=order_code).first()
                order.payment_proof = request.FILES['payment_proof']
                order.save()
            messages.success(request, f"Đã tạo đơn đăng ký gói '{plan.name}'. Vui lòng chuyển khoản & tải biên lai.")
            return redirect('bookings:owner_kyc')

    plans = SubscriptionPlan.objects.filter(is_active=True)
    my_orders = SubscriptionOrder.objects.filter(owner=request.user).order_by('-created_at')

    context = {
        'profile': profile,
        'kyc_status_display': profile.get_kyc_status_display(),
        'kyc_status': profile.kyc_status,
        'plans': plans,
        'my_orders': my_orders,
        'is_subscription_active': profile.is_subscription_active(),
        'subscription_expires_at': profile.subscription_expires_at,
    }
    return render(request, 'bookings/owner_kyc.html', context)


@login_required
def owner_pending_orders_api(request):
    """API polling: số đơn chờ duyệt mới của chủ sân (thông báo không cần tải lại trang)"""
    if not (request.user.is_owner() or request.user.is_staff):
        return JsonResponse({'ok': False}, status=403)

    my_facilities = _get_managed_facilities(request.user)
    pending = Booking.objects.filter(
        slots__court__facility__in=my_facilities,
        status=BookingStatus.WAITING_APPROVAL
    ).distinct()

    latest = []
    for b in pending.order_by('-created_at')[:5]:
        slots = b.slots.select_related('court__facility').all()
        latest.append({
            'code': b.booking_code,
            'customer': b.display_customer_name,
            'phone': b.display_customer_phone,
            'facility': slots.first().court.facility.name if slots else '',
            'court': slots.first().court.court_name if slots else '',
            'total': int(b.total_amount or 0),
            'created_at': b.created_at.strftime('%H:%M %d/%m'),
        })

    return JsonResponse({
        'ok': True,
        'pending_count': pending.count(),
        'unread_notifications': NotificationService.unread_count(request.user),
        'latest': latest,
    })


