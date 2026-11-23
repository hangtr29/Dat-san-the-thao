/**
 * Trang bản đồ - Hiển thị cụm sân bằng Leaflet (OpenStreetMap).
 *
 * Dữ liệu marker lấy từ RESTful API: GET /api/facilities/map/
 */
import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { facilityApi, getErrorMessage } from '@/lib/api'
import { ErrorAlert, LoadingScreen } from '@/components/ui'

export default function MapPage() {
  const [markers, setMarkers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const mapRef = useRef(null)
  const layerRef = useRef(null)

  useEffect(() => {
    load()
  }, [])

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await facilityApi.map()
      setMarkers(data)
      renderMap(data)
    } catch (e) {
      setError(getErrorMessage(e, 'Khong tai duoc du lieu ban do.'))
    } finally {
      setLoading(false)
    }
  }

  const renderMap = (data) => {
    // Leaflet được nạp qua CDN trong index.html
    if (typeof window.L === 'undefined') return

    const map = window.L.map(mapRef.current, {
      center: [10.7769, 106.7009],
      zoom: 12,
      scrollWheelZoom: false,
    })

    window.L.tileLayer(
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      },
    ).addTo(map)

    const layer = window.L.layerGroup().addTo(map)

    data.forEach((m) => {
      const marker = window.L.marker([m.latitude, m.longitude], {
        icon: window.L.divIcon({
          className: '',
          html: `<div style="background:#16a34a;color:#fff;width:32px;height:32px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(0,0,0,.3)"><span style="transform:rotate(45deg);font-size:15px">🏟</span></div>`,
          iconSize: [32, 32],
          iconAnchor: [16, 32],
        }),
      })

      const popupHtml = `
        <div style="min-width:180px;font-family:system-ui,sans-serif">
          <div style="font-weight:700;font-size:14px;margin-bottom:4px">${m.name}</div>
          <div style="font-size:12px;color:#64748b;margin-bottom:6px">${m.address}</div>
          <div style="font-size:12px;margin-bottom:8px">
            ⭐ ${m.average_rating || 0} (${m.total_reviews || 0}) · 🏸 ${m.total_courts} sân
          </div>
          <a href="/facilities/${m.id}"
             style="display:inline-block;background:#16a34a;color:#fff;padding:6px 12px;border-radius:8px;font-size:12px;font-weight:600;text-decoration:none">
            Xem chi tiết
          </a>
        </div>
      `

      marker.bindPopup(popupHtml)
      marker.addTo(layer)
    })

    layerRef.current = layer
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 sm:text-3xl">
          Bản đồ cụm sân
        </h1>
        <p className="mt-1.5 text-sm text-slate-500">
          {loading ? 'Đang tải...' : `${markers.length} cụm sân trên bản đồ`}
        </p>
      </div>

      {error && <ErrorAlert message={error} onRetry={load} />}

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* Map */}
        <div className="card overflow-hidden">
          {loading ? (
            <LoadingScreen label="Đang tải bản đồ..." />
          ) : (
            <div
              ref={mapRef}
              className="h-[520px] w-full"
              style={{ zIndex: 0 }}
            />
          )}
        </div>

        {/* List */}
        <aside className="card max-h-[520px] overflow-y-auto scrollbar-thin p-2">
          <div className="sticky top-0 bg-white px-3 py-2 text-xs font-bold uppercase tracking-wider text-slate-500">
            Danh sách cụm sân
          </div>
          {markers.map((m) => (
            <Link
              key={m.id}
              to={`/facilities/${m.id}`}
              className="block rounded-xl p-3 transition-colors hover:bg-brand-50"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-sm font-semibold text-slate-800">
                  {m.name}
                </span>
                {m.is_verified && (
                  <span className="shrink-0 text-brand-600" title="Đã xác thực">
                    ✓
                  </span>
                )}
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-slate-500">
                {m.address}
              </p>
              <div className="mt-1.5 flex items-center gap-3 text-xs text-slate-400">
                <span>⭐ {m.average_rating || 0}</span>
                <span>🏸 {m.total_courts} sân</span>
              </div>
            </Link>
          ))}
        </aside>
      </div>
    </div>
  )
}
