"""
Tải ảnh chất lượng cao từ Wikimedia Commons cho từng cụm sân (Nguồn ảnh minh bạch,
giấy phép tự do - phù hợp cho đồ án học phật).

Dùng: python download_facility_images.py
"""
import os
import time

import requests

H = {'User-Agent': 'SportBookEdu/1.0 (HTTT14 course project)'}
API = 'https://commons.wikimedia.org/w/api.php'

# mapping: key -> (tên file trên Commons, tên file lưu trong media/facilities/)
PHOTOS = {
    'bad_iitd': 'Badminton Court at IITD.jpg',
    'bad_view': 'Badminton court view.jpg',
    'bad_court': 'Badminton Court.jpg',
    'bad_thoddoo1': '2025-08-20 AA. Thoddoo indoor badminton court construction commencement ceremony (1).jpg',
    'bad_thoddoo3': '2025-08-20 AA. Thoddoo indoor badminton court construction commencement ceremony (3).jpg',
    'bad_thoddoo5': '2025-08-20 AA. Thoddoo indoor badminton court construction commencement ceremony (5).jpg',
    'bad_thoddoo9': '2025-08-20 AA. Thoddoo indoor badminton court construction commencement ceremony (9).jpg',
    'pick_aerial': 'Aerial Pickleball Courts.jpg',
    'pick_1_3': 'Harry B. Anderson Tennis Center - Pickleball Courts 1-3.jpg',
    'pick_4_6': 'Harry B. Anderson Tennis Center - Pickleball Courts 4-6.jpg',
    'pick_7_9': 'Harry B. Anderson Tennis Center - Pickleball Courts 7-9.jpg',
    'pick_10_12': 'Harry B. Anderson Tennis Center - Pickleball Courts 10-12.jpg',
    'pick_mckey': 'McKey Park pickleball courts.jpg',
    'pick_guangzhou': 'Guangzhou Metro Pickleball Center, Pazhou Station, Guangzhou Metro 20251002.jpg',
    'tt_haikou': 'Haikou People\'s Park - people playing ping pong - 01.jpg',
    'tt_room': 'Table Tennis room at Manor Resort.jpg',
    'tt_hirano': 'Hirano table tennis center.jpg',
    'tt_china_01': '雁塔 陕师大附中分校在打乒乓球 01.jpg',
    'tt_china_05': '雁塔 陕师大附中分校在打乒乓球 05.jpg',
}

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media', 'facilities', 'source')


def resolve_thumburl(title, width=1600):
    """Tra cứu URL ảnh thu nhỏ (thumb) từ Wikimedia Commons API."""
    params = {
        'action': 'query',
        'titles': 'File:' + title,
        'prop': 'imageinfo',
        'iiprop': 'url|size|extmetadata',
        'iiurlwidth': width,
        'format': 'json',
    }
    resp = requests.get(API, params=params, timeout=40, headers=H)
    resp.raise_for_status()
    pages = resp.json().get('query', {}).get('pages', {})
    for _, page in pages.items():
        info = (page.get('imageinfo') or [None])[0]
        if info:
            meta = info.get('extmetadata', {})
            return {
                'url': info.get('thumburl') or info.get('url'),
                'license': (meta.get('LicenseShortName') or {}).get('value', ''),
                'artist': (meta.get('Artist') or {}).get('value', ''),
                'descurl': info.get('descriptionurl', ''),
            }
    return None


def download(url, dest):
    resp = requests.get(url, timeout=60, headers=H)
    resp.raise_for_status()
    with open(dest, 'wb') as fh:
        fh.write(resp.content)
    return len(resp.content)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    credits = []
    for key, title in PHOTOS.items():
        dest = os.path.join(OUT_DIR, key + '.jpg')
        if os.path.exists(dest) and os.path.getsize(dest) > 20000:
            print(f" -> BỎ QUA (đã tải): {key}")
            continue
        try:
            meta = resolve_thumburl(title)
            if not meta or not meta['url']:
                print(f" -> KHÔNG TÌM THẤY: {title}")
                continue
            size = download(meta['url'], dest)
            print(f" -> ĐÃ TẢI: {key} ({size // 1024} KB) | {meta['license']}")
            credits.append((key, title, meta['license'], meta['artist'], meta['descurl']))
        except Exception as exc:
            print(f" -> LỖI {key}: {exc}")
        time.sleep(1.5)

    with open(os.path.join(OUT_DIR, 'CREDITS.txt'), 'w', encoding='utf-8') as fh:
        fh.write('Nguồn ảnh: Wikimedia Commons\n\n')
        for key, title, lic, artist, desc in credits:
            fh.write(f"{key}\n  File: {title}\n  License: {lic}\n  Author: {artist}\n  {desc}\n\n")
    print("--- HOÀN TẤT ---")


if __name__ == '__main__':
    main()
