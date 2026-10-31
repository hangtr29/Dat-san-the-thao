from datetime import datetime, date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Facility, SportCategory, Court, PricingRule
from bookings.models import BookingSlot, BookingStatus
from bookings.services import SlotGeneratorService, CleanExpiredLocksService

def search_suggest(request):
    """
    API Gợi ý tìm kiếm (Auto-suggest) theo thời gian thực khi người dùng gõ từ khóa.
    Trả về danh sách Cụm sân và Môn thể thao phù hợp.
    """
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 1:
        return JsonResponse({'facilities': [], 'categories': []})

    # 1. Tìm cụm sân theo tên hoặc địa chỉ
    facilities = Facility.objects.filter(
        Q(name__icontains=query) | Q(address__icontains=query),
        active_status=True
    ).prefetch_related('courts')[:5]

    fac_data = []
    for f in facilities:
        fac_data.append({
            'id': str(f.id),
            'name': f.name,
            'address': f.address,
            'courts_count': f.courts.count(),
            'url': f'/facilities/{f.id}/',
        })

    # 2. Tìm môn thể thao phù hợp
    categories = SportCategory.objects.filter(name__icontains=query)[:3]
    cat_data = []
    for c in categories:
        cat_data.append({
            'name': c.name,
            'icon': c.icon_url or '🏸',
            'slug': c.slug,
            'facilities_count': c.count_facilities(),
            'url': f'/?category={c.slug}',
        })

    return JsonResponse({
        'query': query,
        'facilities': fac_data,
        'categories': cat_data,
    })


def facility_list(request):
    """
    Trang chủ & Danh sách Cụm sân Thể thao (Theo phong cách Alobo).
    """
    CleanExpiredLocksService.cleanup()

    categories = SportCategory.objects.all()
    selected_category_slug = request.GET.get('category')
    search_query = request.GET.get('q', '').strip()

    total_facilities_count = Facility.objects.filter(active_status=True).count()
    facilities = Facility.objects.filter(active_status=True).prefetch_related('courts')

    if selected_category_slug:
        facilities = facilities.filter(courts__category__slug=selected_category_slug).distinct()

    if search_query:
        facilities = facilities.filter(name__icontains=search_query) | facilities.filter(address__icontains=search_query)

    context = {
        'facilities': facilities,
        'categories': categories,
        'selected_category': selected_category_slug,
        'search_query': search_query,
        'total_facilities_count': total_facilities_count,
    }
    return render(request, 'facilities/facility_list.html', context)


def facility_detail(request, facility_id):
    """
    Alobo Grid Matrix 2D (Chuẩn hóa chính xác theo Image 2):
    - Hàng (Rows) = Sân thi đấu (Nhóm theo Sân trong nhà / Sân tiêu chuẩn)
    - Cột (Columns) = Dải thời gian nằm ngang (Timeline: 06:00 -> 22:00)
    """
    CleanExpiredLocksService.cleanup()

    facility = get_object_or_404(Facility, id=facility_id, active_status=True)
    
    # Xử lý chọn ngày (mặc định hôm nay)
    date_str = request.GET.get('date')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()

    # Tự động sinh slot cho ngày này nếu chưa có
    SlotGeneratorService.generate_slots_for_facility(facility, target_date)

    courts = facility.courts.filter(is_active=True).order_by('court_name')
    slots = BookingSlot.objects.filter(
        court__in=courts,
        date=target_date
    ).select_related('court', 'locked_by', 'booking').order_by('start_time')

    # Danh sách các mốc giờ duy nhất (Cột thời gian nằm ngang)
    time_headers = sorted(list(set((s.start_time, s.end_time) for s in slots)), key=lambda x: x[0])

    # Tạo map tra cứu nhanh: (court_id, start_time) -> slot
    slot_map = {}
    for s in slots:
        slot_map[(s.court_id, s.start_time)] = s

    now = timezone.localtime()
    is_today = (target_date == now.date())
    current_time = now.time()

    # Nhóm các sân theo Khu Vực (Sân trong nhà vs Sân ngoài trời - chuẩn như Alobo)
    area_groups = []
    # Lấy thứ tự các khu vực duy nhất
    unique_areas = list(dict.fromkeys(courts.values_list('court_area', flat=True)))
    
    for area in unique_areas:
        courts_in_area = courts.filter(court_area=area)
        area_rows = []
        for court in courts_in_area:
            court_cells = []
            for start_t, end_t in time_headers:
                slot = slot_map.get((court.id, start_t))
                is_past = (target_date < now.date()) or (is_today and start_t <= current_time)
                court_cells.append({
                    'start_time': start_t,
                    'end_time': end_t,
                    'slot': slot,
                    'is_past': is_past,
                })
            area_rows.append({
                'court': court,
                'cells': court_cells,
            })
        area_groups.append({
            'area_name': area,
            'rows': area_rows,
            'rowspan': len(area_rows),
        })

    # Danh sách 7 ngày tiếp theo để đổi ngày nhanh
    today = timezone.localdate()
    upcoming_dates = [today + timedelta(days=i) for i in range(7)]

    context = {
        'facility': facility,
        'courts': courts,
        'time_headers': time_headers,
        'area_groups': area_groups,
        'target_date': target_date,
        'upcoming_dates': upcoming_dates,
        'today': today,
    }
    return render(request, 'facilities/facility_detail.html', context)
