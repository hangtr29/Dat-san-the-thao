/**
 * Danh sách nhà cung cấp tile bản đồ (dự phòng nhiều nguồn).
 *
 * Một số nhà cung cấp (đặc biệt OpenStreetMap) có thể chặn IP người dùng
 * trả về HTTP 403. Vì vậy ta dò (probe) trước bằng <img> rồi mới add lớp tile.
 */
export const TILE_PROVIDERS = [
  {
    name: 'Google Maps',
    url: 'https://mt{s}.google.com/vt/lyrs=m&hl=vi&x={x}&y={y}&z={z}',
    subdomains: ['1', '2', '3', '0'],
    attribution: '&copy; Google Maps',
    enabled: true,
  },
  {
    name: 'Esri Street Map',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors',
    enabled: true,
  },
  {
    name: 'OpenStreetMap',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap',
    enabled: true,
  },
  {
    name: 'OpenStreetMap DE',
    url: 'https://tile.openstreetmap.de/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap (DE)',
    enabled: true,
  },
  {
    name: 'OpenStreetMap JP',
    url: 'https://tile.openstreetmap.jp/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap (JP)',
    enabled: true,
  },
  {
    name: 'OpenStreetMap FR',
    url: 'https://tile-a.openstreetmap.fr/hot/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap (FR/HOT)',
    enabled: true,
  },
  {
    name: 'CARTO Voyager',
    url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
    attribution: '&copy; CARTO &middot; &copy; OpenStreetMap',
    enabled: true,
  },
]

/**
 * Dò xem nhà cung cấp tile có dùng được không (bắt lỗi 403 / mạng).
 * Dùng <img> thay vì fetch() để tránh lỗi CORS và bắt chắc HTTP 403.
 */
export function probeProvider(map, index) {
  return new Promise((resolve) => {
    const provider = TILE_PROVIDERS[index]
    const z = map.getZoom() || 14
    const center = map.getCenter()
    const proj = map.project(center, z).divideBy(256).floor()
    const x = proj.x
    const y = proj.y

    const subdomains = provider.subdomains
      ? provider.subdomains
      : provider.url.indexOf('{s}') > -1
        ? ['a', 'b', 'c']
        : ['']

    let idx = 0

    const tryNext = () => {
      if (idx >= subdomains.length) {
        resolve(false)
        return
      }
      const s = subdomains[idx++]
      const url = provider.url
        .replace('{s}', s)
        .replace('{z}', z)
        .replace('{x}', x)
        .replace('{y}', y)

      const img = new Image()
      let settled = false
      const finish = (ok) => {
        if (settled) return
        settled = true
        img.onload = null
        img.onerror = null
        if (ok) resolve(true)
        else tryNext()
      }
      // Timeout 6s: nhà cung cấp treo quá lâu cũng coi như không dùng được
      const timer = setTimeout(() => finish(false), 6000)
      img.onload = () => {
        clearTimeout(timer)
        finish(true)
      }
      img.onerror = () => {
        clearTimeout(timer)
        finish(false)
      }
      img.src = url
    }

    tryNext()
  })
}

export function escapeHtml(str) {
  return (str || '').replace(/[&<>"']/g, (m) => {
    return {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;',
    }[m]
  })
}
