/**
 * Trang chủ - Hero + tìm kiếm nhanh + cụm sân nổi bật.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { facilityApi } from '@/lib/api'
import { CardSkeleton, ErrorAlert, RatingStars } from '@/components/ui'

const SPORTS = [
  { name: 'Cau long', icon: '🏸', color: 'from-emerald-500 to-teal-600' },
  { name: 'Pickleball', icon: '🏓', color: 'from-blue-500 to-indigo-600' },
  { name: 'Bong ban', icon: '🏓', color: 'from-amber-500 to-orange-600' },
]

export default function Home() {
  const [facilities, setFacilities] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [keyword, setKeyword] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await facilityApi.list({ page_size: 6 })
      setFacilities(data.results || data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Không tải được danh sách cụm sân.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleSearch = (e) => {
    e.preventDefault()
    const params = new URLSearchParams()
    if (keyword) params.set('q', keyword)
    window.location.href = `/facilities?${params.toString()}`
  }

  return (
    <div>
      {/* ---------------- HERO ---------------- */}
      <section className="relative overflow-hidden bg-gradient-to-br from-brand-700 via-brand-600 to-emerald-500">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute -left-20 top-10 h-72 w-72 rounded-full bg-white/20 blur-3xl" />
          <div className="absolute right-0 top-40 h-96 w-96 rounded-full bg-yellow-200/20 blur-3xl" />
        </div>

        <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <span className="inline-flex items-center gap-2 rounded-full bg-white/15 px-4 py-1.5 text-xs font-semibold text-white backdrop-blur">
              ⚡ Xem lịch sân trống theo thời gian thực
            </span>

            <h1 className="mt-6 text-4xl font-extrabold leading-tight tracking-tight text-white sm:text-5xl">
              Đặt sân thể thao
              <span className="block bg-gradient-to-r from-yellow-200 to-orange-300 bg-clip-text text-transparent">
                nhanh chóng & minh bạch
              </span>
            </h1>

            <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-brand-50 sm:text-lg">
              Kết nối trực tiếp với các chủ sân cầu lông, Pickleball và bóng bàn
              trong khu vực của bạn. Xem lịch trống theo thời gian thực, thanh toán
              VietQR và đánh giá chất lượng sân.
            </p>

            {/* Search box */}
            <form
              onSubmit={handleSearch}
              className="mx-auto mt-9 flex max-w-xl flex-col gap-2.5 sm:flex-row"
            >
              <div className="relative flex-1">
                <svg
                  className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z"
                  />
                </svg>
                <input
                  type="text"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder="Tìm cụm sân, địa chỉ..."
                  className="w-full rounded-xl border border-white/20 bg-white/95 py-3.5 pl-12 pr-4 text-slate-900 shadow-lg outline-none placeholder:text-slate-400 focus:ring-2 focus:ring-white/60"
                />
              </div>
              <button
                type="submit"
                className="rounded-xl bg-slate-900 px-7 py-3.5 font-semibold text-white shadow-lg transition-all hover:bg-slate-800 hover:shadow-xl active:scale-[0.98]"
              >
                Tìm sân
              </button>
            </form>

            {/* Sport quick links */}
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              {SPORTS.map((sport) => (
                <Link
                  key={sport.name}
                  to={`/facilities?sport=${encodeURIComponent(sport.name)}`}
                  className="group flex items-center gap-2.5 rounded-full bg-white/15 px-4 py-2 text-sm font-medium text-white backdrop-blur transition-all hover:bg-white/25"
                >
                  <span className="text-lg">{sport.icon}</span>
                  {sport.name}
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Stats bar */}
        <div className="relative border-t border-white/15 bg-black/10 backdrop-blur">
          <div className="mx-auto grid max-w-7xl grid-cols-2 gap-6 px-4 py-6 sm:px-6 md:grid-cols-4 lg:px-8">
            {[
              { value: '30+', label: 'Cụm sân' },
              { value: '3', label: 'Môn thể thao' },
              { value: '24/7', label: 'Đặt lịch online' },
              { value: 'VietQR', label: 'Thanh toán nhanh' },
            ].map((stat) => (
              <div key={stat.label} className="text-center text-white">
                <div className="text-2xl font-extrabold sm:text-3xl">{stat.value}</div>
                <div className="mt-1 text-xs text-brand-100 sm:text-sm">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- FEATURES ---------------- */}
      <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <h2 className="text-center text-2xl font-bold text-slate-900 sm:text-3xl">
          Vì sao chọn SportBook?
        </h2>
        <p className="mx-auto mt-2 max-w-2xl text-center text-sm text-slate-500">
          Giải pháp toàn diện cho cả người chơi và chủ sân
        </p>

        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {[
            {
              icon: '📅',
              title: 'Lịch trống realtime',
              desc: 'Ma trận khung giờ cập nhật tức thì, không lo trùng lịch.',
            },
            {
              icon: '💳',
              title: 'Thanh toán VietQR',
              desc: 'Quét mã QR có sẵn số tiền và mã đơn, chủ sân nhận tiền trực tiếp.',
            },
            {
              icon: '⭐',
              title: 'Đánh giá chất lượng',
              desc: 'Xem điểm uy tín và nhận xét thật từ người đã chơi.',
            },
            {
              icon: '🔒',
              title: 'Giữ chỗ an toàn',
              desc: 'Hệ thống khóa slot 10 phút chống tranh chấp khi thanh toán.',
            },
          ].map((feature) => (
            <div key={feature.title} className="card-hover p-6">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-2xl">
                {feature.icon}
              </div>
              <h3 className="font-bold text-slate-900">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-500">
                {feature.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------------- FACILITIES ---------------- */}
      <section className="bg-white py-14">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex items-end justify-between">
            <div>
              <h2 className="text-2xl font-bold text-slate-900 sm:text-3xl">
                Cụm sân nổi bật
              </h2>
              <p className="mt-2 text-sm text-slate-500">
                Những điểm đến được nhiều người chơi lựa chọn
              </p>
            </div>
            <Link
              to="/facilities"
              className="hidden items-center gap-1.5 text-sm font-semibold text-brand-600 transition-colors hover:text-brand-700 sm:flex"
            >
              Xem tất cả
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>

          {error && (
            <div className="mt-6">
              <ErrorAlert message={error} onRetry={load} />
            </div>
          )}

          <div className="mt-8">
            {loading ? (
              <CardSkeleton count={3} />
            ) : facilities.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-300 py-12 text-center text-slate-500">
                Chưa có cụm sân nào.
              </div>
            ) : (
              <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {facilities.map((f) => (
                  <FacilityCard key={f.id} facility={f} />
                ))}
              </div>
            )}
          </div>

          <Link
            to="/facilities"
            className="btn-secondary mt-8 w-full sm:hidden"
          >
            Xem tất cả cụm sân
          </Link>
        </div>
      </section>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Card hiển thị cụm sân
// ---------------------------------------------------------------------------
export function FacilityCard({ facility }) {
  const image = facility.image_url || '/placeholder-court.svg'

  return (
    <Link
      to={`/facilities/${facility.id}`}
      className="card-hover group flex flex-col overflow-hidden"
    >
      <div className="relative h-48 overflow-hidden bg-slate-100">
        <img
          src={image}
          alt={facility.name}
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
          onError={(e) => {
            e.currentTarget.style.display = 'none'
          }}
        />
        {facility.is_verified && (
          <span className="absolute left-3 top-3 flex items-center gap-1 rounded-full bg-brand-600 px-2.5 py-1 text-[11px] font-bold text-white shadow-sm">
            ✓ Đã xác thực
          </span>
        )}
        {facility.total_courts > 0 && (
          <span className="absolute right-3 top-3 rounded-full bg-slate-900/70 px-2.5 py-1 text-[11px] font-semibold text-white backdrop-blur">
            {facility.total_courts} sân
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col p-5">
        <h3 className="font-bold text-slate-900 transition-colors group-hover:text-brand-700">
          {facility.name}
        </h3>

        <p className="mt-1.5 line-clamp-2 text-sm text-slate-500">
          {facility.address}
        </p>

        {/* Sports */}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {(facility.category_names || []).map((name) => (
            <span key={name} className="badge-gray !text-[11px]">
              {name}
            </span>
          ))}
        </div>

        <div className="mt-auto flex items-end justify-between pt-4">
          <div>
            {facility.average_rating > 0 && (
              <RatingStars value={facility.average_rating} count={facility.total_reviews} />
            )}
            {facility.min_price && (
              <div className="mt-1 text-sm text-slate-500">
                từ{' '}
                <span className="font-bold text-brand-700">
                  {facility.min_price.toLocaleString('vi-VN')}đ
                </span>
                /giờ
              </div>
            )}
          </div>
          <span className="text-sm font-semibold text-brand-600 transition-transform group-hover:translate-x-1">
            →
          </span>
        </div>
      </div>
    </Link>
  )
}
