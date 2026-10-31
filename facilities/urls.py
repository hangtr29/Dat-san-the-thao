from django.urls import path
from . import views

app_name = 'facilities'

urlpatterns = [
    path('', views.facility_list, name='facility_list'),
    path('api/suggest/', views.search_suggest, name='search_suggest'),
    path('<uuid:facility_id>/', views.facility_detail, name='facility_detail'),
]

