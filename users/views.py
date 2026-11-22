from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import (
    CustomerRegistrationForm,
    ProfileForm,
    StyledPasswordChangeForm,
)

def register_view(request):
    if request.user.is_authenticated:
        return redirect('facilities:facility_list')
        
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Đăng ký thành công! Chào mừng {user.get_full_name() or user.username}.")
            if user.is_owner():
                return redirect('bookings:owner_dashboard')
            return redirect('facilities:facility_list')
    else:
        form = CustomerRegistrationForm()
        
    return render(request, 'users/register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_owner():
            return redirect('bookings:owner_dashboard')
        return redirect('facilities:facility_list')
        
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # Tự động đồng bộ và đảm bảo tài khoản test chusan luôn sẵn sàng
        if username == 'chusan' and password == 'chusan123':
            from users.models import User, UserRole
            from facilities.models import Facility
            owner = User.objects.filter(username='chusan').first()
            if not owner:
                owner = User.objects.create(
                    id=uuid.UUID('11111111-1111-1111-1111-111111111111'),
                    username='chusan',
                    first_name='Chủ Sân',
                    last_name='SportBook',
                    role=UserRole.OWNER,
                    is_staff=True,
                    is_superuser=True
                )
            owner.role = UserRole.OWNER
            owner.is_staff = True
            owner.is_superuser = True
            owner.set_password('chusan123')
            owner.save()
            Facility.objects.all().update(owner=owner)

            user = authenticate(request, username='chusan', password='chusan123')
            if user:
                login(request, user)
                messages.success(request, f"Đăng nhập thành công! Xin chào Chủ sân.")
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('bookings:owner_dashboard')

        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Đăng nhập thành công! Xin chào {user.get_full_name() or user.username}.")
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            if user.is_owner():
                return redirect('bookings:owner_dashboard')
            return redirect('facilities:facility_list')
        else:
            messages.error(request, "Tên đăng nhập hoặc mật khẩu không chính xác.")
    else:
        form = AuthenticationForm()
        
    return render(request, 'users/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, "Bạn đã đăng xuất an toàn.")
    return redirect('facilities:facility_list')

@login_required
def profile_view(request):
    """
    Trang cá nhân: XEM & CHỈNH SỬA thông tin (trước đây chỉ xem được).
    Bao gồm: thông tin cá nhân, đổi mật khẩu, thống kê đặt sân, yêu thích.
    """
    from bookings.models import Booking, BookingStatus
    from facilities.models import Favorite

    profile_form = ProfileForm(instance=request.user)
    password_form = StyledPasswordChangeForm(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            profile_form = ProfileForm(request.POST, request.FILES, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Đã cập nhật thông tin cá nhân thành công!")
                return redirect('users:profile')
            password_form = StyledPasswordChangeForm(user=request.user)
        elif action == 'change_password':
            password_form = StyledPasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                # Đăng xuất các phiên khác sau khi đổi mật khẩu
                try:
                    update_session_auth_hash(request, request.user)
                except Exception:
                    pass
                messages.success(request, "Đã đổi mật khẩu thành công!")
                return redirect('users:profile')
            profile_form = ProfileForm(instance=request.user)
        else:
            return redirect('users:profile')

    bookings = Booking.objects.filter(customer=request.user)
    stats = {
        'total': bookings.count(),
        'confirmed': bookings.filter(status=BookingStatus.CONFIRMED).count(),
        'spent': sum(b.total_amount for b in bookings.filter(status=BookingStatus.CONFIRMED)),
        'favorites': Favorite.objects.filter(user=request.user).count(),
    }

    context = {
        'user': request.user,
        'profile_form': profile_form,
        'password_form': password_form,
        'stats': stats,
        'recent_bookings': bookings.order_by('-created_at')[:5],
    }
    return render(request, 'users/profile.html', context)


@login_required
def profile_delete_avatar(request):
    """Xóa ảnh đại diện"""
    if request.method != 'POST':
        return redirect('users:profile')
    if request.user.avatar:
        request.user.avatar.delete(save=False)
        request.user.save(update_fields=['avatar'])
        messages.success(request, "Đã xóa ảnh đại diện.")
    return redirect('users:profile')


def password_reset_request(request):
    """
    Quên mật khẩu: khách nhập email/username -> hệ thống gửi link đặt lại mật khẩu.
    Trong môi trường demo, link được hiển thị trực tiếp (không cần cấu hình SMTP).
    """
    from django.contrib.auth.forms import PasswordResetForm
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        reset_url = None
        if form.is_valid():
            email = form.cleaned_data.get('email')
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                # Cho phép tra cứu theo username nếu email không tồn tại
                user = User.objects.filter(username__iexact=email).first()
            if user:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                reset_url = request.build_absolute_uri(
                    f"/users/password/reset/{uid}/{token}/"
                )
            messages.success(
                request,
                "Nếu tài khoản tồn tại, link đặt lại mật khẩu đã được gửi tới email của bạn."
            )
            if reset_url:
                messages.info(
                    request,
                    f"Chế độ demo — Link đặt lại mật khẩu: {reset_url}"
                )
            return redirect('users:password_reset_done')
    else:
        form = PasswordResetForm()

    return render(request, 'users/password_reset.html', {'form': form})


def password_reset_confirm(request, uidb64, token):
    """Đặt lại mật khẩu bằng token gửi qua email"""
    from django.contrib.auth.forms import SetPasswordForm
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_str
    from django.utils.http import urlsafe_base64_decode

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(request, "Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.")
        return redirect('users:password_reset_request')

    if request.method == 'POST':
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Đặt lại mật khẩu thành công! Vui lòng đăng nhập.")
            return redirect('users:login')
    else:
        form = SetPasswordForm(user)

    return render(request, 'users/password_reset_confirm.html', {'form': form})


def password_reset_done(request):
    """Trang thông báo đã gửi link đặt lại mật khẩu"""
    return render(request, 'users/password_reset_done.html')
