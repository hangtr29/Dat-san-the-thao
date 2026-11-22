from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/avatar/delete/', views.profile_delete_avatar, name='profile_delete_avatar'),

    # Quên mật khẩu / Đặt lại mật khẩu
    path('password/reset/', views.password_reset_request, name='password_reset_request'),
    path('password/reset/done/', views.password_reset_done, name='password_reset_done'),
    path('password/reset/<str:uidb64>/<str:token>/', views.password_reset_confirm, name='password_reset_confirm'),
]
