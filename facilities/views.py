import json
from datetime import datetime, date, timedelta, time
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from .models import (
    Facility, SportCategory, Court, PricingRule, FacilityStatus, Favorite,
    AddonService,
)
from bookings.models import BookingSlot, BookingStatus
from bookings.services import SlotGeneratorService, CleanExpiredLocksService

def search_suggest(request):
    """
    API Gợi ý tìm kiếm (Auto-suggest) theo thời gian thực khi người dùng gõ từ khóa.
    Chỉ hiển thị các cụm sân đã được xác minh tích xanh (is_verified=True) và đang hoạt động (ACTIVE).
    """
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 1:
        return JsonResponse({'facilities': [], 'categories': []})

    # 1. Tìm cụm sân theo tên hoặc địa chỉ (Chống sân ma)
    facilities = Facility.objects.filter(
        Q(name__icontains=query) | Q(address__icontains=query),
        active_status=True,
        is_verified=True,
        status=FacilityStatus.ACTIVE
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


def toggle_favorite(request, facility_id):
    """
    API bật/tắt yêu thích cụm sân (nút hình trái tim ở danh sách sân).
    Yêu cầu đăng nhập để gắn yêu thích với tài khoản.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'message': 'Phải dùng phương thức POST.'}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({
            'ok': False,
            'message': 'Vui lòng đăng nhập để lưu sân yêu thích.',
            'require_login': True,
        }, status=401)

    facility = get_object_or_404(Facility, id=facility_id)
    favorite = Favorite.objects.filter(user=request.user, facility=facility).first()

    if favorite:
        favorite.delete()
        return JsonResponse({
            'ok': True,
            'is_favorite': False,
            'count': facility.favorited_by.count(),
            'message': f"Đã bỏ yêu thích '{facility.name}'.",
        })

    Favorite.objects.create(user=request.user, facility=facility)
    return JsonResponse({
        'ok': True,
        'is_favorite': True,
        'count': facility.favorited_by.count(),
        'message': f"Đã thêm '{facility.name}' vào danh sách yêu thích.",
    })


def facility_info_api(request, facility_id):
    """
    API trả về dữ liệu bảng thông tin chi tiết của cụm sân (chuẩn Alobo).
    Dùng để đổ bảng thông tin vào Modal ngay trên trang danh sách /facilities/
    mà không phải tải lại toàn bộ trang.
    """
    facility = get_object_or_404(
        Facility.objects.prefetch_related(
            'courts', 'courts__category', 'gallery_images',
            'pricing_rules', 'addon_services',
        ),
        id=facility_id,
        active_status=True,
        status=FacilityStatus.ACTIVE,
        is_verified=True,
    )

    courts = list(facility.courts.filter(is_active=True).select_related('category'))

    # Bảng giá theo quy tắc định giá của từng cụm sân (gom theo khung giờ)
    DAY_LABELS = {
        0: 'Thứ Hai', 1: 'Thứ Ba', 2: 'Thứ Tư', 3: 'Thứ Năm',
        4: 'Thứ Sáu', 5: 'Thứ Bảy', 6: 'Chủ Nhật',
    }
    pricing_rules = [
        {
            'day': rule.day_of_week,
            'day_label': DAY_LABELS.get(rule.day_of_week, ''),
            'start_time': rule.start_time.strftime('%H:%M'),
            'end_time': rule.end_time.strftime('%H:%M'),
            'price': int(rule.price_per_hour),
        }
        for rule in facility.pricing_rules.all().order_by('day_of_week', 'start_time')
    ]

    # Dịch vụ bổ sung (thuê vợt, nước uống...) của riêng cụm sân này
    addon_services = [
        {
            'name': svc.name,
            'description': svc.description,
            'category': svc.category,
            'category_label': dict(AddonService.CATEGORY_CHOICES).get(svc.category, svc.category),
            'unit_type': svc.unit_type,
            'unit_label': svc.get_unit_label(),
            'price': int(svc.unit_price),
            'icon': svc.icon,
        }
        for svc in facility.addon_services.filter(is_active=True)
    ]

    data = {
        'id': str(facility.id),
        'name': facility.name,
        'address': facility.address,
        'hotline': facility.get_display_hotline(),
        'phone_contact': facility.phone_contact,
        'rating': facility.get_average_rating(),
        'reviews_count': facility.get_total_reviews(),
        'open_time': facility.open_time.strftime('%H:%M'),
        'close_time': facility.close_time.strftime('%H:%M'),
        'is_open_now': facility.is_open_at(timezone.localtime().time()),
        'is_verified': facility.is_verified,
        'distance': facility.get_distance_display(),
        'distance_km': facility.get_distance_km(),
        'sports': facility.get_sport_names(),
        'surfaces': facility.get_surface_types(),
        'courts_count': len(courts),
        'min_price': facility.get_min_price(),
        'max_price': facility.get_max_price(),
        'cover_image': facility.get_cover_image_url(),
        'gallery': facility.get_gallery_images(),
        'description': facility.description,
        'highlights': facility.get_highlight_list(),
        'pricing_rules': pricing_rules,
        'addon_services': addon_services,
        'booking_url': f"/facilities/{facility.id}/",
        'map_url': (
            'https://www.google.com/maps/dir/?api=1'
            f"&destination={round(float(facility.latitude), 7)},{round(float(facility.longitude), 7)}"
        ),
        'facility_detail_url': f"/facilities/{facility.id}/",
        'is_favorite': (
            request.user.is_authenticated
            and Favorite.objects.filter(user=request.user, facility=facility).exists()
        ),
    }

    return JsonResponse(data)


def facility_list(request):
    """
    Trang chủ & Danh sách Cụm sân Thể thao (Theo phong cách Alobo).
    Mục tiêu 1: Chỉ cho phép các sân đã xác minh tích xanh (is_verified=True)
    và đang hoạt động (status='ACTIVE') xuất hiện trên công cụ tìm kiếm của khách hàng.

    Bộ lọc nâng cao (Task: Lọc & sắp xếp sân):
    - Lọc theo khoảng giá (min_price / max_price) - thanh kéo giá trong thanh tìm kiếm
    - Lọc theo đánh giá tối thiểu (min_rating)
    - Lọc theo khoảng cách tối đa (max_distance) - km
    - Lọc theo trạng thái đang mở cửa (open_now)
    - Sắp xếp theo: giá, khoảng cách, đánh giá, mặc định (liên quan)
    """
    try:
        CleanExpiredLocksService.cleanup()
    except Exception:
        pass

    categories = SportCategory.objects.all()
    selected_category_slug = request.GET.get('category')
    search_query = request.GET.get('q', '').strip()

    # Bộ lọc chống sân ma: Phải có tích xanh và ở trạng thái ACTIVE
    base_qs = Facility.objects.filter(
        active_status=True,
        is_verified=True,
        status=FacilityStatus.ACTIVE
    )

    total_facilities_count = base_qs.count()
    facilities = base_qs.prefetch_related(
        'courts', 'courts__category', 'gallery_images', 'addon_services',
    )

    if selected_category_slug:
        facilities = facilities.filter(courts__category__slug=selected_category_slug).distinct()

    if search_query:
        facilities = facilities.filter(name__icontains=search_query) | facilities.filter(address__icontains=search_query)

    # ---------------- BỘ LỌC NÂNG CAO ----------------
    def _get_float(key, default=None):
        raw = request.GET.get(key, '').strip()
        if raw == '':
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    min_price = _get_float('min_price')
    max_price = _get_float('max_price')
    min_rating = _get_float('min_rating')
    max_distance = _get_float('max_distance')
    open_now = request.GET.get('open_now') == '1'
    sort_by = request.GET.get('sort', 'default')

    # Lấy danh sách dạng list để áp dụng các bộ lọc tính toán (giá, khoảng cách, rating)
    facility_list = list(facilities.distinct())

    def _passes(f):
        if min_price is not None and f.get_min_price() < min_price:
            return False
        if max_price is not None and f.get_min_price() > max_price:
            return False
        if min_rating is not None and f.get_average_rating() < min_rating:
            return False
        if max_distance is not None and f.get_distance_km() > max_distance:
            return False
        if open_now and not f.is_open_at(timezone.localtime().time()):
            return False
        return True

    if any(v is not None for v in [min_price, max_price, min_rating, max_distance]) or open_now:
        facility_list = [f for f in facility_list if _passes(f)]

    # ---------------- SẮP XẾP ----------------
    if sort_by == 'price_asc':
        facility_list.sort(key=lambda f: f.get_min_price())
    elif sort_by == 'price_desc':
        facility_list.sort(key=lambda f: -f.get_min_price())
    elif sort_by == 'distance':
        facility_list.sort(key=lambda f: f.get_distance_km())
    elif sort_by == 'rating':
        facility_list.sort(key=lambda f: (-f.get_average_rating(), -f.get_total_reviews()))
    elif sort_by == 'popular':
        facility_list.sort(key=lambda f: -f.get_total_reviews())

    # Khoảng giá toàn hệ thống để cấu hình thanh kéo giá
    # Chỉ tính cụm sân đã được duyệt & đang hoạt động (đồng bộ bộ lọc chống sân ma)
    all_prices = []
    for f in Facility.objects.filter(
        active_status=True,
        status=FacilityStatus.ACTIVE,
        is_verified=True,
    ):
        p = f.get_min_price()
        if p:
            all_prices.append(p)
    price_floor = (min(all_prices) // 10000) * 10000 if all_prices else 0
    price_ceiling = (max(all_prices) // 10000) * 10000 if all_prices else 500000

    # Tổng số sân thi đấu (đang hoạt động) trên toàn hệ thống - dùng cho hero banner
    total_courts_count = (
        Court.objects.filter(is_active=True, facility__in=base_qs).count()
    )

    context = {
        'facilities': facility_list,
        'categories': categories,
        'selected_category': selected_category_slug,
        'search_query': search_query,
        'total_facilities_count': total_facilities_count,
        'total_courts_count': total_courts_count,
        'favorite_ids': _get_favorite_ids(request, facility_list),
        # Bộ lọc nâng cao
        'min_price': min_price,
        'max_price': max_price,
        'min_rating': min_rating,
        'max_distance': max_distance,
        'open_now': open_now,
        'sort_by': sort_by,
        'price_floor': price_floor,
        'price_ceiling': price_ceiling,
        'filter_active': any([
            min_price is not None, max_price is not None, min_rating is not None,
            max_distance is not None, open_now, sort_by != 'default',
        ]),
    }
    return render(request, 'facilities/facility_list.html', context)


def facility_map(request):
    """
    Trang Bản đồ sân (chuẩn phong cách datlich.alobo.vn):
    - Hiển thị TẤT CẢ cụm sân đang hoạt động trên nền bản đồ Leaflet (OpenStreetMap).
    - Marker tương tác: bấm vào sân -> hiện Popup thông tin chi tiết (tên, địa chỉ, giá, số sân, nút Đặt lịch).
    - Bộ lọc theo môn thể thao & tìm kiếm theo tên/địa chỉ.
    - Nút định vị vị trí người dùng (Geolocation API) + tính khoảng cách.
    """
    try:
        CleanExpiredLocksService.cleanup()
    except Exception:
        pass

    categories = SportCategory.objects.all()
    selected_category_slug = request.GET.get('category', '')
    search_query = request.GET.get('q', '').strip()

    # Chỉ hiển thị sân đã xác minh tích xanh & đang hoạt động (chống sân ma)
    facilities = Facility.objects.filter(
        active_status=True,
        is_verified=True,
        status=FacilityStatus.ACTIVE
    ).prefetch_related('courts', 'courts__category', 'gallery_images', 'addon_services')

    if selected_category_slug:
        facilities = facilities.filter(courts__category__slug=selected_category_slug).distinct()

    if search_query:
        facilities = facilities.filter(
            Q(name__icontains=search_query) | Q(address__icontains=search_query)
        ).distinct()

    facilities = list(facilities)

    # Chuẩn bị dữ liệu JSON cho Leaflet (đóng gói dữ liệu trước khi render)
    markers = []
    for f in facilities:
        courts = list(f.courts.filter(is_active=True))
        sport_names = list({
            c.category.name for c in courts if c.category
        })
        # Lấy giá thấp nhất trong ngày để hiển thị "giá từ"
        min_price = None
        for c in courts:
            rule = f.pricing_rules.filter(day_of_week=request_date_weekday()).first()
            if rule and (min_price is None or rule.price_per_hour < min_price):
                min_price = rule.price_per_hour

        markers.append({
            'id': str(f.id),
            'name': f.name,
            'address': f.address,
            'lat': f.latitude,
            'lng': f.longitude,
            'hotline': f.get_display_hotline(),
            'rating': f.get_average_rating(),
            'reviews': f.get_total_reviews(),
            'courts_count': len(courts),
            'sports': sport_names,
            'open_time': f.open_time.strftime('%H:%M'),
            'close_time': f.close_time.strftime('%H:%M'),
            'price_from': int(min_price) if min_price else None,
            'image': f.get_cover_image_url(),
            'is_verified': f.is_verified,
            'url': f'/facilities/{f.id}/',
            # Khoảng cách hiển thị (giống trang danh sách)
            'distance': f.get_distance_display(),
            # URL chỉ đường Google Maps (dấu thập phân chuẩn)
            'directions_url': (
                'https://www.google.com/maps/dir/?api=1'
                f'&destination={round(float(f.latitude), 7)},{round(float(f.longitude), 7)}'
            ),
        })

    # Tâm bản đồ: trung bình các marker (nếu không có thì dùng TP.HCM)
    if markers:
        center_lat = sum(m['lat'] for m in markers) / len(markers)
        center_lng = sum(m['lng'] for m in markers) / len(markers)
    else:
        center_lat, center_lng = 10.7769, 106.7009

    # Truyền tọa độ tâm bản đồ dưới dạng chuỗi để tránh Django format số theo locale
    # (ví dụ 10.78 -> "10,78" gây lỗi cú pháp JavaScript)
    context = {
        'facilities': facilities,
        'categories': categories,
        'selected_category': selected_category_slug,
        'search_query': search_query,
        'total_facilities_count': len(facilities),
        'markers_json': json.dumps(markers, ensure_ascii=False),
        'center_lat': repr(float(center_lat)),
        'center_lng': repr(float(center_lng)),
        # Cấu hình nhà cung cấp bản đồ
        'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
        'google_maps_keyless': getattr(settings, 'GOOGLE_MAPS_KEYLESS_TILES', True),
    }
    return render(request, 'facilities/facility_map.html', context)

def request_date_weekday():
    """Lấy thứ trong tuần hiện tại (0 = Thứ 2 ... 6 = Chủ Nhật) để tra quy tắc giá"""
    from django.utils import timezone
    return timezone.localdate().weekday()


def _get_favorite_ids(request, facilities):
    """
    Lấy danh sách id cụm sân đã yêu thích của người dùng hiện tại.
    Dùng để đánh dấu trạng thái nút trái tim (đã thích / chưa thích) khi render danh sách.
    """
    if not request.user.is_authenticated:
        return set()
    return set(
        Favorite.objects.filter(user=request.user, facility__in=facilities)
        .values_list('facility_id', flat=True)
    )


def favorites_list(request):
    """
    Trang danh sách sân yêu thích của khách hàng.
    """
    if not request.user.is_authenticated:
        messages.info(request, "Vui lòng đăng nhập để xem danh sách sân yêu thích.")
        return redirect(f"/users/login/?next={request.path}")

    fav_qs = (
        Favorite.objects.filter(user=request.user)
        .select_related('facility')
        .order_by('-created_at')
    )
    facilities = [f.facility for f in fav_qs]

    context = {
        'facilities': facilities,
        'favorite_ids': {f.id for f in facilities},
        'categories': SportCategory.objects.all(),
        'selected_category': None,
        'search_query': '',
        'total_facilities_count': len(facilities),
        'is_favorites_page': True,
        'sort_by': 'default',
        'open_now': False,
        'filter_active': False,
        'price_floor': 0,
        'price_ceiling': 500000,
    }
    return render(request, 'facilities/facility_list.html', context)


def facility_detail(request, facility_id):
    """
    Alobo Grid Matrix 2D (Chuẩn hóa chính xác theo Image 2):
    - Hàng (Rows) = Sân thi đấu (Nhóm theo Sân trong nhà / Sân tiêu chuẩn)
    - Cột (Columns) = Dải thời gian nằm ngang (Timeline: 06:00 -> 22:00)
    """
    try:
        CleanExpiredLocksService.cleanup()
    except Exception:
        pass

    facility = get_object_or_404(
        Facility.objects.prefetch_related(
            'courts', 'courts__category', 'gallery_images',
            'pricing_rules', 'addon_services',
        ),
        id=facility_id,
        active_status=True,
        status=FacilityStatus.ACTIVE,
        is_verified=True,
    )
    
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

    # ---- Mốc hiển thị: KHÁCH có thể chọn xem lịch theo bước 30 phút hoặc 1 giờ ----
    # step=30 (mặc định): hiện từng slot 30 phút -> khách đặt linh hoạt nửa giờ
    # step=60: gộp 2 slot 30 phút liền kề thành khung 1 giờ -> gọn, dễ nhìn
    try:
        step_minutes = int(request.GET.get('step', 30))
    except (TypeError, ValueError):
        step_minutes = 30
    if step_minutes not in (30, 60):
        step_minutes = 30

    # Danh sách các mốc giờ duy nhất (Cột thời gian nằm ngang)
    if step_minutes == 60:
        # Gộp slot 30 phút thành khung 1 giờ
        grouped = {}
        for s in slots:
            hour_start = s.start_time.replace(minute=0)
            key = (s.court_id, hour_start)
            g = grouped.setdefault(key, {
                'start_time': hour_start,
                'end_time': hour_start.replace(hour=(hour_start.hour + 1) % 24),
                'parts': [],
            })
            g['parts'].append(s)

        time_headers = sorted({
            (g['start_time'], g['end_time']) for g in grouped.values()
        }, key=lambda x: x[0])

        # Mỗi ô = 1 giờ, gồm 2 slot 30 phút con
        slot_map = {}
        for (court_id, hour_start), g in grouped.items():
            parts = sorted(g['parts'], key=lambda s: s.start_time)
            slot_map[(court_id, hour_start)] = {
                'parts': parts,
                'price': sum(p.price for p in parts),
                'booking': parts[0].booking if parts else None,
                'is_locked': any(p.lock_time for p in parts),
                'is_past': parts[0].is_past() if parts else False,
            }
    else:
        time_headers = sorted(list(set((s.start_time, s.end_time) for s in slots)), key=lambda x: x[0])
        # Tạo map tra cứu nhanh: (court_id, start_time) -> slot
        slot_map = {}
        for s in slots:
            slot_map[(s.court_id, s.start_time)] = {
                'parts': [s],
                'price': s.price,
                'booking': s.booking,
                'is_locked': bool(s.lock_time),
                'is_past': s.is_past(),
            }

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
                slot_data = slot_map.get((court.id, start_t))
                slot = slot_data['parts'][0] if slot_data else None
                is_past = (target_date < now.date()) or (is_today and start_t <= current_time)
                if slot_data:
                    is_past = is_past or slot_data['is_past']
                court_cells.append({
                    'start_time': start_t,
                    'end_time': end_t,
                    'slot': slot,
                    'parts': slot_data['parts'] if slot_data else [],
                    'total_price': slot_data['price'] if slot_data else None,
                    'is_booked': bool(slot_data and slot_data['booking']),
                    'is_locked': bool(slot_data and slot_data['is_locked']),
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
        'step_minutes': step_minutes,
    }
    return render(request, 'facilities/facility_detail.html', context)
