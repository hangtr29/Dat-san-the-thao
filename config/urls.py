from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('facilities:facility_list'), name='home'),
    path('users/', include('users.urls', namespace='users')),
    path('facilities/', include('facilities.urls', namespace='facilities')),
    path('bookings/', include('bookings.urls', namespace='bookings')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
