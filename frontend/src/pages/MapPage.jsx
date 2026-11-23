/**
 * Trang bản đồ - Leaflet + OpenStreetMap (đồng bộ với bản Django gốc).
 *
 * Dữ liệu marker lấy từ RESTful API: GET /api/facilities/map/
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { facilityApi, getErrorMessage } from '@/lib/api'
import { ErrorAlert, LoadingScreen } from '@/components/ui'
import { TILE_PROVIDERS, probeProvider, escapeHtml } from '@/pages/mapHelpers'
import '@/pages/MapPage.css'

export default function MapPage() {
  const [markers, setMarkers] = useState([])
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [activeId, setActiveId] = useState(null)
  const [tileError, setTileError] = useState(false)
  const [providerName, setProviderName] = useState('OpenStreetMap')

  const mapRef = useRef(null)
  const mapInstance = useRef(null)
  const tileLayerRef = useRef(null)
  const markerMapRef = useRef(new Map())
  const currentProviderRef = useRef(0)
  const switchingRef = useRef(false)

  // ---- Tải dữ liệu ----
  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await facilityApi.map()
      const list = data.results || []
      setMarkers(list)
      renderMap(list, data.center_lat, data.center_lng)
    } catch (e) {
      setError(getErrorMessage(e, 'Không tải được dữ liệu bản đồ.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    facilityApi.categories().then(setCategories).catch(() => {})
    load()
  }, [load])

  // ---- Khởi tạo bản đồ ----
  function renderMap(list, cLat, cLng) {
    if (typeof window.L === 'undefined') return

    if (!mapInstance.current) {
      const map = window.L.map(mapRef.current, {
        zoomControl: true,
        scrollWheelZoom: true,
      }).setView([cLat ?? 10.7769, cLng ?? 106.7009], 14)
      mapInstance.current = map

      // Tải provider đầu tiên, sau đó dò & thay thế nếu bị chặn
      const first = TILE_PROVIDERS.findIndex((p) => p.enabled !== false)
      currentProviderRef.current = first >= 0 ? first : 0
      loadTileLayer(map, currentProviderRef.current)

      if (!switchingRef.current) {
        switchingRef.current = true
        selectProvider(map).then(() => {
          const badge = document.getElementById('tile-provider-badge')
          if (badge) badge.textContent = TILE_PROVIDERS[currentProviderRef.current].name
          setProviderName(TILE_PROVIDERS[currentProviderRef.current].name)
        })
      }

      // Cảnh báo nếu sau 10s vẫn không có tile nào tải được
      setTimeout(() => {
        const tiles = document.querySelectorAll('.leaflet-tile')
        let ok = 0
        tiles.forEach((t) => {
          if (t.complete && t.naturalWidth > 0) ok++
        })
        if (ok === 0) setTileError(true)
      }, 10000)

      // Kiểm tra định kỳ khi người dùng kéo/zoom sang vùng mới
      let timer = null
      map.on('moveend zoomend', () => {
        clearTimeout(timer)
        timer = setTimeout(() => {
          const tiles = document.querySelectorAll('.leaflet-tile')
          let total = 0
          let ok = 0
          tiles.forEach((t) => {
            if (t.complete) {
              total++
              if (t.naturalWidth > 0) ok++
            }
          })
          if (total > 0 && ok === 0) {
            selectProvider(map)
            setTileError(true)
          } else if (ok > 0) {
            setTileError(false)
          }
        }, 1200)
      })

      // Vô hiệu hoá tải bản đồ khi cuộn trong sidebar
      document.getElementById('map-list')?.addEventListener(
        'wheel',
        (e) => e.stopPropagation(),
        { passive: true },
      )
    }

    drawMarkers(mapInstance.current, list)
  }

  function loadTileLayer(map, index) {
    const provider = TILE_PROVIDERS[index]
    if (tileLayerRef.current) {
      map.removeLayer(tileLayerRef.current)
      tileLayerRef.current = null
    }
    const options = { maxZoom: 19, attribution: provider.attribution }
    if (provider.subdomains) options.subdomains = provider.subdomains
    tileLayerRef.current = window.L.tileLayer(provider.url, options)
    tileLayerRef.current.addTo(map)
  }

  async function selectProvider(map) {
    for (let i = 0; i < TILE_PROVIDERS.length; i++) {
      if (TILE_PROVIDERS[i].enabled === false) continue
      const ok = await probeProvider(map, i)
      if (ok) {
        if (i !== currentProviderRef.current) {
          currentProviderRef.current = i
          loadTileLayer(map, i)
        }
        return
      }
    }
  }

  // ---- Vẽ marker ----
  function drawMarkers(map, list) {
    const markerMap = markerMapRef.current
    markerMap.forEach((m) => map.removeLayer(m))
    markerMap.clear()

    list.forEach((m) => {
      const icon = window.L.divIcon({
        className: 'custom-marker',
        html: '<div class="marker-pin"><i class="fa-solid fa-volleyball-ball"></i></div>',
        iconSize: [40, 40],
        iconAnchor: [20, 40],
        popupAnchor: [0, -38],
      })

      const marker = window.L.marker([m.lat, m.lng], { icon, title: m.name }).addTo(map)
      marker.bindPopup(buildPopup(m), {
        className: 'alobo-popup',
        maxWidth: 300,
        minWidth: 290,
        autoPan: false,
      })

      markerMap.set(m.id, marker)

      marker.on('click', () => {
        markerMap.forEach((mk) => {
          if (mk !== marker) {
            mk.getElement()?.querySelector('.marker-pin')?.classList.remove('is-active')
          }
        })
        setTimeout(() => {
          marker.getElement()?.querySelector('.marker-pin')?.classList.add('is-active')
        }, 50)
        setActiveId(m.id)
        document.querySelectorAll('.map-list-item').forEach((el) => {
          el.classList.toggle('active', el.dataset.facilityId === m.id)
        })
      })
    })
  }

  // ---- Popup nội dung ----
  function buildPopup(m) {
    const sports = (m.sports || [])
      .map(
        (s) =>
          `<span class="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-black">${escapeHtml(s)}</span>`,
      )
      .join(' ')

    const priceHtml = m.price_from
      ? `<span class="text-[#c2410c] font-black">${m.price_from.toLocaleString('vi-VN')} đ/h</span>`
      : '<span class="text-slate-400">Liên hệ sân</span>'

    return `
      <div class="alobo-popup-content">
        <div class="relative h-32 bg-slate-200 overflow-hidden">
          <img src="${escapeHtml(m.image)}" alt="${escapeHtml(m.name)}"
               class="w-full h-full object-cover" loading="lazy"
               onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1626224583764-f87db24ac4ea?w=800&auto=format&fit=crop&q=80';">
          <div class="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent"></div>
          <div class="absolute top-2.5 left-2.5 flex items-center gap-1.5">
            <span class="px-2 py-0.5 rounded-full bg-white/95 text-slate-800 text-[10px] font-black flex items-center gap-1">
              <i class="fa-solid fa-star text-amber-400 text-[9px]"></i> ${m.rating}
              <span class="text-slate-400 font-bold">(${m.reviews})</span>
            </span>
            ${
              m.is_verified
                ? '<span class="px-2 py-0.5 rounded-full bg-sky-500 text-white text-[10px] font-black"><i class="fa-solid fa-circle-check"></i> Tích xanh</span>'
                : ''
            }
          </div>
          <div class="absolute bottom-2 left-2.5 right-2.5">
            <h3 class="text-sm font-black text-white leading-tight drop-shadow">${escapeHtml(m.name)}</h3>
          </div>
        </div>

        <div class="p-3.5 space-y-2.5">
          <p class="text-[11px] text-slate-600 leading-relaxed flex items-start gap-1.5">
            <i class="fa-solid fa-map-pin text-[#0b6b3a] mt-0.5 flex-shrink-0"></i>
            <span>${
              m.distance
                ? `<span class="text-[#c2410c] font-bold mr-1">(${escapeHtml(m.distance)})</span>`
                : ''
            }${escapeHtml(m.address)}</span>
          </p>

          <div class="flex items-center justify-between text-[11px] font-bold text-slate-600">
            <span class="flex items-center gap-1.5">
              <i class="fa-regular fa-clock text-slate-400"></i>
              ${m.open_time} - ${m.close_time}
            </span>
            <span class="flex items-center gap-1.5">
              <i class="fa-solid fa-layer-group text-slate-400"></i>
              ${m.courts_count} sân
            </span>
          </div>

          ${sports ? `<div class="flex flex-wrap gap-1.5">${sports}</div>` : ''}

          <div class="flex items-center justify-between pt-2.5 border-t border-slate-100">
            <div class="text-[11px]">
              <span class="text-slate-400 font-bold block leading-tight">Giá từ</span>
              ${priceHtml}
            </div>
            <a href="${m.url}"
               class="px-4 py-2 rounded-xl bg-[#e5b63d] hover:bg-[#d8a834] text-white text-[11px] font-black uppercase tracking-wide transition shadow-md shadow-amber-500/25">
              Đặt lịch
            </a>
          </div>

          <a href="${m.directions_url || ''}" target="_blank" rel="noopener"
             class="block text-center text-[11px] font-bold text-[#065f46] hover:text-emerald-700 transition">
            <i class="fa-solid fa-diamond-turn-right"></i> Chỉ đường đến sân
          </a>
        </div>
      </div>
    `
  }

  // ---- Bấm item trong danh sách -> bay tới marker ----
  function focusFacility(id) {
    const map = mapInstance.current
    const marker = markerMapRef.current.get(id)
    if (!map || !marker) return

    document.querySelectorAll('.map-list-item').forEach((el) => {
      el.classList.toggle('active', el.dataset.facilityId === id)
    })
    setActiveId(id)

    // Đồng bộ trạng thái active của marker (gradient cam)
    markerMapRef.current.forEach((mk) => {
      mk.getElement()?.querySelector('.marker-pin')?.classList.remove('is-active')
    })
    marker.getElement()?.querySelector('.marker-pin')?.classList.add('is-active')

    const target = marker.getLatLng()
    map.setView(target, 17, { animate: true, duration: 0.6 })

    let popupOpened = false
    const openIt = () => {
      if (popupOpened) return
      popupOpened = true
      marker.openPopup()
    }
    map.once('moveend', openIt)
    setTimeout(openIt, 800)
  }

  // ---- Định vị vị trí người dùng ----
  const handleLocate = () => {
    const map = mapInstance.current
    if (!map) return
    if (!navigator.geolocation) {
      window.alert('Trình duyệt của bạn không hỗ trợ định vị.')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords
        map.flyTo([latitude, longitude], 15, { duration: 0.8 })
        const meIcon = window.L.divIcon({
          className: 'custom-marker',
          html: '<div style="width:22px;height:22px;border-radius:50%;background:#2563eb;border:3px solid #fff;box-shadow:0 0 0 6px rgba(37,99,235,.25)"></div>',
          iconSize: [22, 22],
          iconAnchor: [11, 11],
        })
        window.L.marker([latitude, longitude], { icon: meIcon, zIndexOffset: 1000 })
          .addTo(map)
          .bindPopup('<b>Vị trí của bạn</b>')
      },
      () => {
        window.alert('Không thể lấy vị trí của bạn. Vui lòng bật quyền truy cập vị trí.')
      },
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  // ---- Đổi nền bản đồ ----
  const handleSwitchTile = () => {
    const map = mapInstance.current
    if (!map) return
    const enabled = TILE_PROVIDERS
      .map((p, i) => ({ p, i }))
      .filter((x) => x.p.enabled !== false)
    const curPos = enabled.findIndex((x) => x.i === currentProviderRef.current)
    const next = enabled[(curPos + 1) % enabled.length].i
    currentProviderRef.current = next
    loadTileLayer(map, next)
    setProviderName(TILE_PROVIDERS[next].name)
    setTileError(false)
  }

  // ---- Lọc danh sách theo tìm kiếm ----
  const visible = markers.filter(
    (m) =>
      !query ||
      m.name.toLowerCase().includes(query.toLowerCase()) ||
      (m.address || '').toLowerCase().includes(query.toLowerCase()),
  )

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-5 sm:px-6 lg:px-8">
      {/* Header: Tieu de + tim kiem + dinh vi */}
      <div className="mb-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-[#0b6b3a] to-[#032614] text-xl text-white shadow-lg shadow-emerald-900/20">
              <i className="fa-solid fa-map-location-dot" />
            </div>
            <div>
              <h1 className="text-base font-black tracking-wide text-[#04331b] sm:text-xl">
                BẢN ĐỒ SÂN THỂ THAO
              </h1>
              <p className="mt-0.5 text-xs font-semibold text-slate-500">
                <i className="fa-solid fa-location-dot text-[#0b6b3a]" />
                {markers.length} cụm sân đang hoạt động — bấm vào marker để xem
                chi tiết
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-[220px] flex-1">
              <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400">
                <i className="fa-solid fa-magnifying-glass text-xs" />
              </span>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Tìm tên sân hoặc địa chỉ..."
                className="w-full rounded-xl border border-transparent bg-slate-100 py-2.5 pl-9 pr-3 text-xs font-bold text-slate-700 transition placeholder:text-slate-400 focus:border-emerald-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#0b6b3a]/20"
              />
            </div>
            <button
              type="button"
              onClick={handleLocate}
              title="Định vị vị trí của tôi"
              className="flex items-center gap-1.5 whitespace-nowrap rounded-xl bg-[#0b6b3a] px-4 py-2.5 text-xs font-black text-white shadow-md transition hover:bg-[#064e2a]"
            >
              <i className="fa-solid fa-location-crosshairs" /> Vị trí tôi
            </button>
          </div>
        </div>

        {/* Chips loc mon the thao */}
        {categories.length > 0 && (
          <div className="mt-4 flex items-center gap-2 overflow-x-auto pb-1 text-xs font-black">
            <span className="flex shrink-0 items-center gap-1.5 rounded-full bg-[#0b6b3a] px-4 py-2 text-white shadow-sm">
              <i className="fa-solid fa-border-all" /> Tất cả
            </span>
            {categories.map((c) => (
              <span
                key={c.id}
                className="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full bg-slate-100 px-4 py-2 text-slate-700 shadow-sm transition hover:bg-slate-200"
              >
                <span>{c.icon_url || '🏸'}</span> {c.name}
                <span className="rounded-full bg-slate-200 px-1.5 py-0.5 text-[10px] text-slate-600">
                  {c.facility_count}
                </span>
              </span>
            ))}
          </div>
        )}
      </div>

      {error && <ErrorAlert message={error} onRetry={load} />}

      {/* Khu vuc chinh: Ban do + Danh sach */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* BAN DO */}
        <div className="order-2 lg:order-1 lg:col-span-8 xl:col-span-9">
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            {loading ? (
              <LoadingScreen label="Đang tải bản đồ..." />
            ) : (
              <div
                ref={mapRef}
                className="h-[500px] w-full bg-slate-100 sm:h-[600px] lg:h-[680px]"
              />
            )}

            {/* Canh bao khong tai duoc nen ban do */}
            {tileError && (
              <div className="flex items-center gap-2 border-t border-amber-200 bg-amber-50 px-4 py-2.5 text-[11px] font-bold text-amber-800">
                <i className="fa-solid fa-triangle-exclamation text-amber-500" />
                <span>
                  Không tải được nền bản đồ (có thể nhà cung cấp tile đang chặn
                  mạng của bạn). Vị trí các cụm sân vẫn hiển thị đúng — hãy tải
                  lại trang hoặc đổi mạng.
                </span>
              </div>
            )}

            {/* Chu thich */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-slate-50 px-4 py-3">
              <div className="flex items-center gap-4 text-[11px] font-bold text-slate-600">
                <span className="flex items-center gap-1.5">
                  <span className="inline-block h-3 w-3 rounded-full bg-[#0b6b3a]" />{' '}
                  Cụm sân
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block h-3 w-3 rounded-full bg-[#c2410c]" />{' '}
                  Đang chọn
                </span>
                <span className="flex items-center gap-1.5">
                  <i className="fa-solid fa-circle-check text-emerald-600" /> Tích
                  xanh KYC
                </span>
              </div>
              <span className="flex items-center gap-2 text-[11px] font-bold text-slate-500">
                <button
                  type="button"
                  onClick={handleSwitchTile}
                  className="flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-black text-emerald-700 transition hover:bg-emerald-100"
                >
                  <i className="fa-solid fa-repeat" /> Đổi nền bản đồ
                </button>
                <span
                  id="tile-provider-badge"
                  className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-black text-slate-600"
                >
                  {providerName}
                </span>
                <i className="fa-solid fa-arrows-up-down-left-right text-slate-400" />{' '}
                Có thể kéo để di chuyển
              </span>
            </div>
          </div>
        </div>

        {/* DANH SACH SAN */}
        <div className="order-1 lg:order-2 lg:col-span-4 xl:col-span-3">
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm lg:sticky lg:top-28">
            <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
              <h2 className="flex items-center justify-between text-xs font-black uppercase tracking-wider text-slate-700">
                <span>Danh sách cụm sân</span>
                <span className="rounded-full bg-[#0b6b3a] px-2 py-0.5 text-[10px] font-black text-white">
                  {visible.length}
                </span>
              </h2>
            </div>

            <div
              id="map-list"
              className="map-sidebar-scroll max-h-[560px] divide-y divide-slate-100 overflow-y-auto"
            >
              {visible.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => focusFacility(f.id)}
                  data-facility-id={f.id}
                  className={`map-list-item w-full border-l-4 border-transparent p-3.5 text-left transition hover:bg-emerald-50/50 ${
                    activeId === f.id ? 'active' : ''
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl border border-emerald-200 bg-emerald-50 text-[10px] font-black uppercase text-[#0b6b3a]">
                      {f.name.slice(0, 2)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="flex items-center gap-1 truncate text-xs font-black text-slate-800">
                        <span className="truncate">{f.name}</span>
                        {f.is_verified && (
                          <i className="fa-solid fa-circle-check flex-shrink-0 text-[10px] text-emerald-500" />
                        )}
                      </h3>
                      <p className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-slate-500">
                        {f.address}
                      </p>
                      <div className="mt-1.5 flex items-center gap-3 text-[10px] font-bold text-slate-500">
                        <span className="flex items-center gap-1">
                          <i className="fa-regular fa-clock text-slate-400" />
                          {f.open_time}-{f.close_time}
                        </span>
                        <span className="flex items-center gap-1 text-amber-600">
                          <i className="fa-solid fa-star text-[9px]" /> {f.rating}
                        </span>
                        <span className="flex items-center gap-1 text-emerald-700">
                          <i className="fa-solid fa-layer-group text-[9px]" />{' '}
                          {f.courts_count} sân
                        </span>
                      </div>
                    </div>
                  </div>
                </button>
              ))}

              {visible.length === 0 && (
                <div className="p-8 text-center">
                  <i className="fa-solid fa-map-location-dot mb-2 text-3xl text-slate-300" />
                  <p className="text-xs font-bold text-slate-500">
                    Không tìm thấy cụm sân nào
                  </p>
                  <Link
                    to="/facilities"
                    className="mt-3 inline-block rounded-xl bg-[#0b6b3a] px-4 py-2 text-xs font-bold text-white"
                  >
                    Xem tất cả sân
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
