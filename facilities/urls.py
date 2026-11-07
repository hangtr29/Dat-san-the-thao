from django.urls import path
from . import views
from . import views_owner

app_name = 'facilities'

urlpatterns = [
    path('', views.facility_list, name='facility_list'),
    path('api/suggest/', views.search_suggest, name='search_suggest'),
    
    # Phân hệ Nghiệp vụ Chủ Sân (Owner Subsystem)
    path('owner/facility/manage/', views_owner.FacilityManageView.as_view(), name='owner_facility_manage'),
    path('owner/facility/<uuid:facility_id>/manage/', views_owner.FacilityManageView.as_view(), name='owner_facility_manage_detail'),
    path('owner/courts/', views_owner.CourtCreateUpdateView.as_view(), name='owner_court_manage_default'),
    path('owner/facility/<uuid:facility_id>/courts/', views_owner.CourtCreateUpdateView.as_view(), name='owner_court_manage'),
    path('owner/bookings/approval/', views_owner.OwnerBookingApprovalView.as_view(), name='owner_booking_approval'),

    path('<uuid:facility_id>/', views.facility_detail, name='facility_detail'),
]

