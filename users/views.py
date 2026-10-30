from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CustomerRegistrationForm

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
        return redirect('facilities:facility_list')
        
    if request.method == 'POST':
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
    return render(request, 'users/profile.html', {'user': request.user})
