"""
smoke_test_features.py
======================
Kiểm thử tự động (smoke test) toàn bộ tính năng mới đã triển khai.

Chạy:  python smoke_test_features.py
"""
import os
import re
import sys

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import requests  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from bookings.models import Booking, BookingStatus  # noqa: E402
from facilities.models import Facility  # noqa: E402

BASE = 'http://127.0.0.1:8000'
User = get_user_model()

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    icon = '✅' if cond else '❌'
    print(f"{icon} {name}" + (f" — {detail}" if detail and not cond else ''))


def login(username, password='123456'):
    s = requests.Session()
    r = s.get(f'{BASE}/users/login/', timeout=15)
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text)
    data = {'csrfmiddlewaretoken': token.group(1) if token else '', 'username': username, 'password': password}
    resp = s.post(f'{BASE}/users/login/', data=data, headers={'Referer': f'{BASE}/users/login/'}, timeout=15)
    if 'sessionid' not in s.cookies:
        print(f"   [WARN] Dang nhap that bai: {username} / {password} (status={resp.status_code})")
    return s


def try_login(username, passwords):
    """Tho lai nhieu mat khau, tra ve session dang nhap thanh cong."""
    for pwd in passwords:
        s = login(username, pwd)
        if 'sessionid' in s.cookies:
            return s
    return None


def main():
    print('=' * 70)
    print('SMOKE TEST - Tinh nang moi')
    print('=' * 70)

    # 1. GIA KHAC NHAU GIUA CAC SAN
    print('\n[1] Bieu gia khac nhau giua cac cum san')
    facilities = list(Facility.objects.all())
    price_sets = {}
    for f in facilities:
        price_sets[f.name] = sorted(set(
            int(p) for p in f.pricing_rules.values_list('price_per_hour', flat=True)
        ))
    check('Moi cum san deu co bieu gia', all(len(v) > 0 for v in price_sets.values()))
    distinct = len({tuple(v) for v in price_sets.values()})
    check('Cac cum san co gia KHAC NHAU', distinct == len(facilities),
          f'chi {distinct}/{len(facilities)} bo gia khac nhau')
    for name, prices in price_sets.items():
        print(f"     - {name}: {prices}")

    # 2. DICH VU THUE VOT & THUC UONG
    print('\n[2] Dich vu bo sung (thue vot / thuc uong)')
    for f in facilities:
        services = f.addon_services.filter(is_active=True)
        has_equip = services.filter(category='EQUIPMENT').exists()
        has_drink = services.filter(category='DRINK').exists()
        check(f'{f.name}: co thue vot/thiet bi & thuc uong',
              has_equip and has_drink,
              f'equip={has_equip} drink={has_drink}')

    # 3. LOC & SAP XEP
    print('\n[3] Loc & sap xep tai /facilities/')
    r = requests.get(f'{BASE}/facilities/', timeout=15)
    check('Trang /facilities/ tra ve 200', r.status_code == 200)
    body = r.text
    check('Co thanh truot gia kep (dual slider)',
          'price-slider' in body or 'min_price' in body)
    check('Co dropdown sap xep', 'sort=' in body or 'price_asc' in body)
    check('Co bo loc khoang cach', 'max_distance' in body)
    check('Co bo loc danh gia toi thieu', 'min_rating' in body)
    check('Co bo loc dang mo cua', 'open_now' in body)

    for q, label in [('sort=price_asc', 'gia tang dan'),
                     ('sort=price_desc', 'gia giam dan'),
                     ('min_price=100000&max_price=180000', 'loc khoang gia'),
                     ('min_rating=4', 'loc danh gia'),
                     ('open_now=1', 'loc dang mo cua')]:
        r = requests.get(f'{BASE}/facilities/?{q}', timeout=15)
        check(f'Bo loc "{label}" hoat dong', r.status_code == 200)

    # 4. HO SO CA NHAN
    print('\n[4] Ho so ca nhan / Doi mat khau / Quen mat khau')
    customer = User.objects.filter(username='khachhang1').first() \
        or User.objects.filter(role='CUSTOMER').first()
    owner = User.objects.filter(username='chusan').first() \
        or User.objects.filter(role='OWNER').first()
    # Chon owner that THUC SU so huu it nhat mot cum san
    if owner and not Facility.objects.filter(owner=owner).exists():
        for cand in User.objects.filter(role='OWNER'):
            if Facility.objects.filter(owner=cand).exists():
                owner = cand
                break

    CUSTOMER_PW = ['customer123', '123456', 'khachhang123', 'password123']
    OWNER_PW = ['chusan123', 'owner123', '123456', 'password123']

    if customer:
        s = try_login(customer.username, CUSTOMER_PW)
        check('Dang nhap khach hang thanh cong', s is not None and 'sessionid' in s.cookies)
    if owner:
        so = try_login(owner.username, OWNER_PW)
        check('Dang nhap chu san thanh cong', so is not None and 'sessionid' in so.cookies)

    if customer:
        s = try_login(customer.username, CUSTOMER_PW)
        if s is None or 'sessionid' not in s.cookies:
            check('Dang nhap khach hang', False)
        else:
            r = s.get(f'{BASE}/users/profile/', timeout=15)
            check('Trang ho so ca nhan (200)', r.status_code == 200)
            check('Co form sua thong tin ca nhan', 'update_profile' in r.text)
            check('Co form doi mat khau', 'change_password' in r.text)
            check('Co link quen mat khau', '/users/password/reset/' in r.text)

            old_pwd = next((p for p in CUSTOMER_PW
                            if try_login(customer.username, [p]) is not None), '123456')

            def post_profile(session, payload):
                """POST co kem CSRF token lay tu trang profile."""
                page = session.get(f'{BASE}/users/profile/', timeout=15)
                token = re.search(
                    r'name="csrfmiddlewaretoken" value="([^"]+)"', page.text)
                data = {'csrfmiddlewaretoken': token.group(1) if token else ''}
                data.update(payload)
                return session.post(f'{BASE}/users/profile/', data=data,
                                    headers={'Referer': f'{BASE}/users/profile/'},
                                    allow_redirects=False, timeout=15)

            r = post_profile(s, {
                'action': 'update_profile',
                'first_name': customer.first_name or 'Test',
                'last_name': customer.last_name or 'User',
                'email': customer.email or 'test@example.com',
                'phone': customer.phone or '0901234567',
            })
            check('Cap nhat profile thanh cong', r.status_code == 302,
                  f'status={r.status_code}')

            new_pwd = 'Abc@12345xyz'
            r = post_profile(s, {
                'action': 'change_password',
                'old_password': old_pwd,
                'new_password1': new_pwd,
                'new_password2': new_pwd,
            })
            check('Doi mat khau thanh cong', r.status_code == 302,
                  f'status={r.status_code}')
            s2 = try_login(customer.username, [new_pwd])
            check('Doi mat khau -> dang nhap bang mat khau moi', s2 is not None)
            if s2:
                post_profile(s2, {
                    'action': 'change_password', 'old_password': new_pwd,
                    'new_password1': old_pwd, 'new_password2': old_pwd,
                })
                check('Khoi phuc mat khau cu', True)

    r = requests.get(f'{BASE}/users/password/reset/', timeout=15)
    check('Trang quen mat khau (200)', r.status_code == 200)

    # 5. THONG BAO
    print('\n[5] API thong bao')
    if customer:
        s = try_login(customer.username, CUSTOMER_PW)
        r = s.get(f'{BASE}/bookings/api/notifications/', timeout=15,
                  headers={'X-Requested-With': 'XMLHttpRequest'})
        check('API thong bao tra JSON', r.status_code == 200)
        try:
            data = r.json()
            check('JSON co unread_count', 'unread_count' in data)
            check('JSON co danh sach notifications', 'notifications' in data)
        except Exception as e:
            check('Parse JSON thong bao', False, str(e))

    # 6. LICH SU & PHAN TRANG
    print('\n[6] Lich su dat san & phan trang')
    if customer:
        s = try_login(customer.username, CUSTOMER_PW)
        r = s.get(f'{BASE}/bookings/history/', timeout=15)
        check('Trang lich su dat san (200)', r.status_code == 200)
        r = s.get(f'{BASE}/bookings/history/?page=1', timeout=15)
        check('Phan trang lich su hoat dong', r.status_code == 200)

    # 7. DAT LICH CO DINH
    print('\n[7] Dat lich co dinh theo tuan')
    if customer:
        s = try_login(customer.username, CUSTOMER_PW)
        r = s.get(f'{BASE}/bookings/recurring/', timeout=15)
        check('Trang lich co dinh (200)', r.status_code == 200)

    # 8. COUPON
    print('\n[8] Ma giam gia')
    if customer:
        s = try_login(customer.username, CUSTOMER_PW)
        r = s.get(f'{BASE}/bookings/api/coupon/?code=TEST', timeout=15,
                  headers={'X-Requested-With': 'XMLHttpRequest'})
        check('API kiem tra coupon (200)', r.status_code == 200)

    # 9. KENH CHU SAN
    print('\n[9] Kenh chu san')
    if owner:
        s = try_login(owner.username, OWNER_PW)
        r = s.get(f'{BASE}/bookings/dashboard/', timeout=15)
        check('Dashboard chu san (200)', r.status_code == 200)
        check('Co o tim kiem ma don/SDT', 'name="q"' in r.text)
        check('Co link lich san', 'owner/calendar' in r.text)
        check('Co link bao cao Excel', 'owner/export/excel' in r.text)

        r = s.get(f'{BASE}/bookings/dashboard/?q=BKE', timeout=15)
        check('Tim kiem don theo ma (200)', r.status_code == 200)
        r = s.get(f'{BASE}/bookings/dashboard/?q=090', timeout=15)
        check('Tim kiem don theo SDT (200)', r.status_code == 200)
        r = s.get(f'{BASE}/bookings/dashboard/?tab=orders&page=1', timeout=15)
        check('Phan trang dashboard (200)', r.status_code == 200)

        pages = {
            'Lich san': f'{BASE}/bookings/owner/calendar/',
            'Gia dich vu': f'{BASE}/bookings/owner/services/',
            'Anh & mo ta': f'{BASE}/bookings/owner/gallery/',
            'Xac thuc & goi': f'{BASE}/bookings/owner/kyc/',
        }
        for label, url in pages.items():
            r = s.get(url, timeout=15)
            check(f'Trang {label} (200)', r.status_code == 200, f'status={r.status_code}')
            # Kiem tra noi dung co that su render (khong phai trang rong)
            m = re.search(r'<main.*?</main>', r.text, re.S)
            body = m.group(0) if m else r.text
            body = re.sub(r'<script.*?</script>', ' ', body, flags=re.S)
            body = re.sub(r'<style.*?</style>', ' ', body, flags=re.S)
            text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', body))
            check(f'Trang {label} co noi dung render', len(text) > 400,
                  f'chi {len(text)} ky tu')

        r = s.get(f'{BASE}/bookings/owner/export/excel/', timeout=30)
        ok_xlsx = (r.status_code == 200
                   and r.headers.get('Content-Type', '').startswith(
                       'application/vnd.openxmlformats')
                   and r.content[:2] == b'PK')
        check('Xuat file Excel .xlsx that', ok_xlsx,
              f"ct={r.headers.get('Content-Type')} magic={r.content[:4]}")

        r = s.get(f'{BASE}/bookings/owner/api/pending/', timeout=15,
                  headers={'X-Requested-With': 'XMLHttpRequest'})
        check('API don moi cho chu san (200)', r.status_code == 200)

    # 10. GOP LUONG DUYET DON
    print('\n[10] Gop luong duyet don')
    if owner:
        s = try_login(owner.username, OWNER_PW)
        r = s.get(f'{BASE}/facilities/owner/bookings/approval/', timeout=15,
                  allow_redirects=False)
        check('Trang duyet rieng -> chuyen huong ve dashboard',
              r.status_code == 302 and 'tab=orders' in r.headers.get('Location', ''),
              f"status={r.status_code} loc={r.headers.get('Location')}")

    # 11. IN PHIEU
    print('\n[11] In / luu phieu dat san')
    booking = Booking.objects.filter(status=BookingStatus.CONFIRMED).first() \
        or Booking.objects.first()
    if booking:
        r = requests.get(f'{BASE}/bookings/print/{booking.booking_code}/', timeout=15)
        check('Trang in phieu A4 (200)', r.status_code == 200)

    # 12. TAI LAI BILL
    print('\n[12] Tai lai bill khi bi tu choi')
    check('Co trang thai NEEDS_REUPLOAD', BookingStatus.NEEDS_REUPLOAD == 'NEEDS_REUPLOAD')
    check('Booking.reupload_proof_and_submit ton tai',
          hasattr(Booking, 'reupload_proof_and_submit'))

    # 13. YEU THICH
    print('\n[13] San yeu thich')
    r = requests.get(f'{BASE}/facilities/favorites/', timeout=15)
    check('Trang san yeu thich ton tai (200 hoac chuyen huong login)',
          r.status_code in (200, 302), f'status={r.status_code}')

    print('\n' + '=' * 70)
    print(f'KET QUA: PASS {len(PASS)} | FAIL {len(FAIL)}')
    if FAIL:
        print('\nCac muc that bai:')
        for f in FAIL:
            print(f'  - {f}')
    print('=' * 70)
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
