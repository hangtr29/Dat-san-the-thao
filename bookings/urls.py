from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('lock-slots/', views.lock_and_book_slots, name='lock_slots'),
    path('confirm/<str:booking_code>/', views.booking_confirm, name='booking_confirm'),
    path('checkout/<str:booking_code>/', views.checkout_view, name='checkout'),
    path('upload-proof/<str:booking_code>/', views.upload_payment_proof, name='upload_proof'),
    path('detail/<str:booking_code>/', views.booking_detail, name='booking_detail'),
    path('history/', views.booking_history, name='booking_history'),
    path('lookup/', views.booking_lookup, name='booking_lookup'),
    
    # Khu vực dành cho Chủ sân (Owner)
    path('dashboard/', views.owner_dashboard, name='owner_dashboard'),
    path('owner/approve/<str:booking_code>/', views.owner_approve_booking, name='owner_approve'),
    path('owner/reject/<str:booking_code>/', views.owner_reject_booking, name='owner_reject'),
]

