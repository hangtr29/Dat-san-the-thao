"""
Forms cho khu vực tài khoản người dùng:
- ProfileForm: sửa thông tin cá nhân (họ tên, email, số điện thoại, ảnh đại diện)
- PasswordChangeForm: đổi mật khẩu
"""
from django import forms
from django.contrib.auth.forms import (
    PasswordChangeForm as DjangoPasswordChangeForm,
    UserCreationForm,
)
from .models import User, UserRole


class CustomerRegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=255, label="Họ và tên", widget=forms.TextInput(attrs={
        'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-emerald-500',
        'placeholder': 'Nguyễn Văn A'
    }))
    phone = forms.CharField(max_length=15, label="Số điện thoại / Zalo", widget=forms.TextInput(attrs={
        'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-emerald-500',
        'placeholder': '0901234567'
    }))
    role = forms.ChoiceField(
        choices=[(UserRole.CUSTOMER, 'Khách hàng (Đặt sân)'), (UserRole.OWNER, 'Chủ sân (Quản lý cụm sân)')],
        label="Bạn tham gia với vai trò",
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-emerald-500'})
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'full_name', 'phone', 'email', 'role')

    def save(self, commit=True):
        user = super().save(commit=False)
        full_name = self.cleaned_data.get('full_name', '')
        parts = full_name.split()
        if len(parts) > 1:
            user.first_name = " ".join(parts[1:])
            user.last_name = parts[0]
        else:
            user.first_name = full_name
        user.phone = self.cleaned_data.get('phone')
        user.role = self.cleaned_data.get('role')
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    """Sửa thông tin cá nhân"""
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'avatar')
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl bg-white text-slate-800 border border-slate-200 text-xs sm:text-sm font-bold focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500',
                'placeholder': 'Tên',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl bg-white text-slate-800 border border-slate-200 text-xs sm:text-sm font-bold focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500',
                'placeholder': 'Họ / Tên đệm',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl bg-white text-slate-800 border border-slate-200 text-xs sm:text-sm font-bold focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500',
                'placeholder': 'email@example.com',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl bg-white text-slate-800 border border-slate-200 text-xs sm:text-sm font-bold focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500',
                'placeholder': '0901234567',
            }),
            'avatar': forms.ClearableFileInput(attrs={
                'class': 'w-full text-xs font-bold text-slate-500 file:mr-3 file:py-2 file:px-4 file:rounded-xl file:border-0 file:bg-emerald-100 file:text-emerald-800 file:text-xs file:font-black',
            }),
        }

    def clean_phone(self):
        """Kiểm tra định dạng số điện thoại Việt Nam & trùng lặp"""
        phone = (self.cleaned_data.get('phone') or '').strip()
        if not phone:
            return phone
        # Chuẩn hoá về định dạng 10 số bắt đầu bằng 0
        digits = ''.join(ch for ch in phone if ch.isdigit())
        if digits.startswith('84') and len(digits) == 11:
            digits = '0' + digits[2:]
        if not (digits.startswith('0') and len(digits) == 10):
            raise forms.ValidationError("Số điện thoại không đúng định dạng Việt Nam (VD: 0901234567).")
        qs = User.objects.filter(phone=digits).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Số điện thoại này đã được sử dụng bởi tài khoản khác.")
        return digits


class StyledPasswordChangeForm(DjangoPasswordChangeForm):
    """Đổi mật khẩu (giao diện đồng bộ với hệ thống)"""
    old_password = forms.CharField(
        label="Mật khẩu hiện tại",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl bg-white text-slate-800 border border-slate-200 text-xs sm:text-sm font-bold focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500',
            'placeholder': 'Nhập mật khẩu hiện tại',
        })
    )
    new_password1 = forms.CharField(
        label="Mật khẩu mới",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl bg-white text-slate-800 border border-slate-200 text-xs sm:text-sm font-bold focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500',
            'placeholder': 'Nhập mật khẩu mới',
        })
    )
    new_password2 = forms.CharField(
        label="Xác nhận mật khẩu mới",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl bg-white text-slate-800 border border-slate-200 text-xs sm:text-sm font-bold focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500',
            'placeholder': 'Nhập lại mật khẩu mới',
        })
    )
