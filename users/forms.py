from django import forms
from django.contrib.auth.forms import UserCreationForm
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

