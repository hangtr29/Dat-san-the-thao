from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from facilities.models import Coupon, Facility, FacilityStatus
from users.models import (
    KYCStatus,
    OwnerProfile,
    SubscriptionOrder,
    SubscriptionOrderStatus,
)


@login_required
def admin_platform_hub(request):
    """
    Trung tâm Quản trị Nền tảng trực quan dành riêng cho Admin trung gian
    (thay thế giao diện Django Admin kỹ thuật rối mắt).
    Gồm 4 tab gọn gàng:
    - facilities    : Duyệt cụm sân & cấp Tích Xanh
    - kyc           : Duyệt hồ sơ KYC Chủ sân
    - subscriptions : Duyệt đơn gia hạn gói duy trì
    - coupons       : Quản lý & bật/tắt mã giảm giá
    """
    if not (getattr(request.user, 'role', '') == 'ADMIN' or request.user.is_superuser):
        messages.warning(request, "Khu vực này chỉ dành riêng cho Quản trị viên (Admin).")
        return redirect('bookings:owner_dashboard')

    tab = request.GET.get('tab', 'facilities')
    if tab not in ('facilities', 'kyc', 'subscriptions', 'coupons'):
        tab = 'facilities'

    # Xử lý các thao tác duyệt nhanh 1-click
    if request.method == 'POST':
        action = request.POST.get('action', '')
        target_id = request.POST.get('target_id', '')
        next_tab = request.POST.get('tab', tab)

        if action == 'approve_facility' and target_id:
            fac = get_object_or_404(Facility, id=target_id)
            fac.status = FacilityStatus.ACTIVE
            fac.is_verified = True
            fac.active_status = True
            fac.save(update_fields=['status', 'is_verified', 'active_status'])
            messages.success(request, f"Đã duyệt & cấp Tích Xanh cho cụm sân '{fac.name}'.")

        elif action == 'suspend_facility' and target_id:
            fac = get_object_or_404(Facility, id=target_id)
            fac.status = FacilityStatus.SUSPENDED
            fac.active_status = False
            fac.save(update_fields=['status', 'active_status'])
            messages.warning(request, f"Đã tạm ngưng hoạt động cụm sân '{fac.name}'.")

        elif action == 'approve_kyc' and target_id:
            profile = get_object_or_404(OwnerProfile, id=target_id)
            profile.kyc_status = KYCStatus.KYC_VERIFIED
            profile.kyc_rejection_reason = ''
            profile.save(update_fields=['kyc_status', 'kyc_rejection_reason'])
            messages.success(request, f"Đã duyệt hồ sơ KYC cho chủ sân '{profile.user.username}'.")

        elif action == 'reject_kyc' and target_id:
            profile = get_object_or_404(OwnerProfile, id=target_id)
            reason = request.POST.get('reason', '').strip() or 'Hồ sơ chưa đầy đủ giấy tờ hợp lệ.'
            profile.kyc_status = KYCStatus.KYC_REJECTED
            profile.kyc_rejection_reason = reason
            profile.save(update_fields=['kyc_status', 'kyc_rejection_reason'])
            messages.warning(request, f"Đã từ chối hồ sơ KYC của '{profile.user.username}'.")

        elif action == 'approve_subscription' and target_id:
            order = get_object_or_404(SubscriptionOrder, id=target_id)
            if order.approve_order(request.user):
                messages.success(
                    request,
                    f"Đã duyệt đơn gói duy trì [{order.order_code}] và tự động gia hạn cho '{order.owner.username}'.",
                )
            else:
                messages.info(request, f"Đơn [{order.order_code}] đã được duyệt trước đó.")

        elif action == 'reject_subscription' and target_id:
            order = get_object_or_404(SubscriptionOrder, id=target_id)
            reason = request.POST.get('reason', '').strip() or 'Chưa đối soát được giao dịch chuyển khoản.'
            order.reject_order(reason)
            messages.warning(request, f"Đã từ chối đơn gói duy trì [{order.order_code}].")

        elif action == 'toggle_coupon' and target_id:
            coupon = get_object_or_404(Coupon, id=target_id)
            coupon.is_active = not coupon.is_active
            coupon.save(update_fields=['is_active'])
            state = 'BẬT' if coupon.is_active else 'TẮT'
            messages.success(request, f"Đã {state} mã giảm giá '{coupon.code}'.")

        elif action == 'create_coupon':
            code = request.POST.get('code', '').strip().upper()
            description = request.POST.get('description', '').strip() or 'Khuyến mãi SportBook'
            discount_type = request.POST.get('discount_type', 'PERCENT')
            try:
                discount_value = Decimal(request.POST.get('discount_value', '10') or '10')
                max_discount = Decimal(request.POST.get('max_discount', '50000') or '50000')
                min_order_value = Decimal(request.POST.get('min_order_value', '100000') or '100000')
                valid_days = int(request.POST.get('valid_days', '60') or '60')
            except Exception:
                messages.error(request, "Giá trị số không hợp lệ, vui lòng kiểm tra lại.")
                return redirect(f"/bookings/admin-panel/?tab={next_tab}")

            if not code:
                messages.error(request, "Vui lòng nhập mã giảm giá.")
            elif Coupon.objects.filter(code__iexact=code).exists():
                messages.error(request, f"Mã giảm giá '{code}' đã tồn tại.")
            else:
                now = timezone.now()
                Coupon.objects.create(
                    code=code,
                    description=description,
                    discount_type=discount_type,
                    discount_value=discount_value,
                    max_discount=max_discount,
                    min_order_value=min_order_value,
                    is_active=True,
                    valid_from=now,
                    valid_to=now + timedelta(days=max(1, valid_days)),
                )
                messages.success(request, f"Đã tạo mã giảm giá '{code}' thành công!")

        return redirect(f"/bookings/admin-panel/?tab={next_tab}")

    # Nạp dữ liệu cho các tab
    all_facilities = Facility.objects.select_related('owner').order_by('-created_at', 'name')
    all_kycs = OwnerProfile.objects.select_related('user').order_by('-updated_at')
    all_subs = SubscriptionOrder.objects.select_related('owner', 'plan').order_by('-created_at')
    all_coupons = Coupon.objects.all().order_by('-is_active', 'code')

    context = {
        'active_menu': f'admin_{tab}',
        'admin_tab': tab,
        'my_facilities': all_facilities,
        'facilities_list': all_facilities,
        'kyc_list': all_kycs,
        'sub_orders': all_subs,
        'coupons_list': all_coupons,
        'stats': {
            'total_facilities': all_facilities.count(),
            'pending_facilities': all_facilities.filter(status=FacilityStatus.PENDING_REVIEW).count(),
            'total_kyc': all_kycs.count(),
            'pending_kyc': all_kycs.filter(kyc_status=KYCStatus.KYC_PENDING).count(),
            'pending_subs': all_subs.filter(status=SubscriptionOrderStatus.PENDING).count(),
            'active_coupons': all_coupons.filter(is_active=True).count(),
        },
    }
    return render(request, 'bookings/admin_hub.html', context)
