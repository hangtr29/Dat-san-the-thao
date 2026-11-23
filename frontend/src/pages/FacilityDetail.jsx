/**
 * Trang chi tiết cụm sân + MA TRẬN ĐẶT SÂN (30 phút/slot).
 *
 * Ma trận: Hàng = khung giờ (30 phút), Cột = sân thi đấu.
 * Trạng thái ô: TRỐNG (chọn được) / ĐÃ ĐẶT / ĐANG GIỮ CHỖ / ĐÃ QUA.
 */
import { useEffect, useMemo, useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  facilityApi,
  slotApi,
  bookingApi,
  favoriteApi,
  getErrorMessage,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import {
  LoadingScreen,
  ErrorAlert,
  Modal,
  RatingStars,
  toast,
} from '@/components/ui'

const SPORTS = {
  'Cầu lông': '🏸',
  Pickleball: '🏓',
  'Bóng bàn': '🏓',
}

export default function FacilityDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { isAuthenticated, user } = useAuth()

  const [facility, setFacility] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [slots, setSlots] = useState([])
  const [slotsLoading, setSlotsLoading] = useState(false)
  const [selected, setSelected] = useState([]) // danh sách slot đã chọn

  const [isFavorite, setIsFavorite] = useState(false)
  const [showCheckout, setShowCheckout] = useState(false)
  const [booking, setBooking] = useState(null)

  // --- Load facility ---
  const loadFacility = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await facilityApi.detail(id)
      setFacility(data)
    } catch (e) {
      setError(getErrorMessage(e, 'Không tìm thấy cụm sân.'))
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    loadFacility()
  }, [loadFacility])

  // --- Check favorite ---
  useEffect(() => {
    if (!isAuthenticated) return
    favoriteApi
      .list()
      .then((list) => {
        setIsFavorite(list.some((f) => f.facility === id))
      })
      .catch(() => {})
  }, [isAuthenticated, id])

  // --- Load slots theo ngày ---
  const loadSlots = useCallback(async () => {
    setSlotsLoading(true)
    setSelected([])
    try {
      const list = await slotApi.list({ facility: id, date })
      setSlots(list)
    } catch (e) {
      toast(getErrorMessage(e, 'Không tải được lịch sân.'), 'error')
    } finally {
      setSlotsLoading(false)
    }
  }, [id, date])

  useEffect(() => {
    if (facility) loadSlots()
  }, [facility, loadSlots])

  // --- Tăng/giảm ngày ---
  const shiftDate = (delta) => {
    const d = new Date(date)
    d.setDate(d.getDate() + delta)
    const next = d.toISOString().slice(0, 10)
    const today = new Date().toISOString().slice(0, 10)
    setDate(next < today ? today : next)
  }

  // --- Gom slot theo cụm sân + giờ ---
  const matrix = useMemo(() => {
    const byCourt = {}
    const timeSet = new Set()

    slots.forEach((slot) => {
      if (!byCourt[slot.court]) byCourt[slot.court] = []
      byCourt[slot.court].push(slot)
      timeSet.add(slot.start_time_str)
    })

    const times = [...timeSet].sort()
    const courts = Object.keys(byCourt)

    return { times, courts, byCourt }
  }, [slots])

  // --- Chọn / bỏ chọn slot ---
  const toggleSlot = (slot) => {
    if (!slot.is_available) return
    setSelected((prev) => {
      const exists = prev.find((s) => s.id === slot.id)
      if (exists) return prev.filter((s) => s.id !== slot.id)
      // Chặn chọn slot không liên tiếp trong cùng sân (bắt buộc cho luồng đặt)
      return [...prev, slot]
    })
  }

  const totalPrice = selected.reduce((sum, s) => sum + Number(s.price), 0)

  // --- Toggle favorite ---
  const handleToggleFavorite = async () => {
    if (!isAuthenticated) {
      toast('Vui lòng đăng nhập để lưu sân yêu thích.', 'warning')
      navigate('/login')
      return
    }
    try {
      const res = await favoriteApi.toggle(id)
      setIsFavorite(res.is_favorite)
      toast(res.message || (res.is_favorite ? 'Đã lưu yêu thích.' : 'Đã bỏ lưu yêu thích.'))
    } catch (e) {
      toast(getErrorMessage(e), 'error')
    }
  }

  // --- Tạo đơn ---
  const handleBook = async () => {
    if (!isAuthenticated) {
      toast('Vui lòng đăng nhập để đặt sân.', 'warning')
      navigate('/login')
      return
    }
    if (!selected.length) {
      toast('Vui lòng chọn ít nhất 1 khung giờ.', 'warning')
      return
    }
    try {
      const res = await bookingApi.create({
        slotIds: selected.map((s) => s.id),
        customerName: user?.full_name || user?.username || '',
        customerPhone: user?.phone || '',
      })
      setBooking(res.booking)
      setShowCheckout(true)
      // Refresh lịch để cập nhật trạng thái giữ chỗ
      loadSlots()
    } catch (e) {
      toast(getErrorMessage(e, 'Không đặt sân được.'), 'error')
    }
  }

  if (loading) return <LoadingScreen label="Đang tải thông tin cụm sân..." />
  if (error)
    return (
      <div className="mx-auto max-w-3xl px-4 py-12">
        <ErrorAlert message={error} onRetry={loadFacility} />
      </div>
    )
  if (!facility) return null

  return (
    <div className="bg-slate-50">
      {/* ---------------- HEADER ---------------- */}
      <div className="relative h-56 overflow-hidden bg-gradient-to-br from-slate-800 to-slate-900 sm:h-72">
        {facility.image_url && (
          <img
            src={facility.image_url}
            alt={facility.name}
            className="h-full w-full object-cover opacity-40"
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-slate-900/80 to-transparent" />

        <div className="relative mx-auto flex h-full max-w-7xl flex-col justify-end px-4 pb-6 sm:px-6 lg:px-8">
          <Link
            to="/facilities"
            className="mb-3 inline-flex w-fit items-center gap-1.5 text-sm text-white/80 transition-colors hover:text-white"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Quay lai danh sach
          </Link>

          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <div className="mb-2 flex flex-wrap items-center gap-2">
                {facility.is_verified && (
                  <span className="flex items-center gap-1 rounded-full bg-brand-600 px-2.5 py-1 text-[11px] font-bold text-white">
                    ✓ Xác thực
                  </span>
                )}
                {(facility.category_names || []).map((name) => (
                  <span key={name} className="rounded-full bg-white/15 px-2.5 py-1 text-[11px] font-semibold text-white backdrop-blur">
                    {SPORTS[name] || '🏟'} {name}
                  </span>
                ))}
              </div>
              <h1 className="text-2xl font-bold text-white sm:text-3xl">
                {facility.name}
              </h1>
              <p className="mt-1.5 flex items-center gap-1.5 text-sm text-white/80">
                <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0zM15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                {facility.address}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleToggleFavorite}
                className={`flex h-10 w-10 items-center justify-center rounded-xl backdrop-blur transition-colors ${
                  isFavorite
                    ? 'bg-red-500/90 text-white'
                    : 'bg-white/15 text-white hover:bg-white/25'
                }`}
                title={isFavorite ? 'Bỏ yêu thích' : 'Lưu yêu thích'}
              >
                <svg className="h-5 w-5" fill={isFavorite ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z" />
                </svg>
              </button>
              <a
                href={`tel:${facility.hotline || facility.phone_contact}`}
                className="flex items-center gap-2 rounded-xl bg-white/15 px-4 py-2.5 text-sm font-semibold text-white backdrop-blur transition-colors hover:bg-white/25"
              >
                📞 {facility.hotline || facility.phone_contact}
              </a>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
          {/* ---------------- MA TRẬN SLOT ---------------- */}
          <div className="space-y-6">
            {/* Chọn ngày */}
            <div className="card p-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="font-bold text-slate-900">Lịch sân trống</h2>
                  <p className="mt-0.5 text-sm text-slate-500">
                    Chọn khung giờ 30 phút để đặt sân
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => shiftDate(-1)}
                    className="rounded-lg border border-slate-300 p-2 text-slate-600 transition-colors hover:bg-slate-50"
                    title="Ngày trước"
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                    </svg>
                  </button>
                  <input
                    type="date"
                    value={date}
                    min={new Date().toISOString().slice(0, 10)}
                    onChange={(e) => setDate(e.target.value)}
                    className="input w-auto"
                  />
                  <button
                    onClick={() => shiftDate(1)}
                    className="rounded-lg border border-slate-300 p-2 text-slate-600 transition-colors hover:bg-slate-50"
                    title="Ngày sau"
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Legend */}
              <div className="mt-4 flex flex-wrap gap-4 border-t border-slate-100 pt-4 text-xs">
                <span className="flex items-center gap-1.5">
                  <span className="h-4 w-4 rounded border border-slate-200 bg-white" />
                  Trống
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-4 w-4 rounded bg-brand-600" />
                  Đang chọn
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-4 w-4 rounded bg-slate-300" />
                  Đã đặt
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-4 w-4 rounded bg-amber-300" />
                  Đang giữ chỗ
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-4 w-4 rounded bg-slate-100" />
                  Đã qua
                </span>
              </div>
            </div>

            {/* Matrix */}
            <div className="card overflow-hidden">
              {slotsLoading ? (
                <LoadingScreen label="Đang tải lịch sân..." />
              ) : matrix.courts.length === 0 ? (
                <div className="px-6 py-14 text-center text-slate-500">
                  <div className="mb-2 text-4xl">📅</div>
                  Ngày này chưa có lịch sân. Vui lòng chọn ngày khác.
                </div>
              ) : (
                <div className="overflow-x-auto scrollbar-thin">
                  <table className="w-full min-w-[640px] border-collapse">
                    <thead>
                      <tr className="border-b border-slate-200 bg-slate-50">
                        <th className="sticky left-0 z-10 bg-slate-50 px-4 py-3 text-left text-xs font-bold uppercase tracking-wider text-slate-500">
                          Khung giờ
                        </th>
                        {matrix.courts.map((courtId) => {
                          const court = facility.courts.find((c) => c.id === courtId)
                          return (
                            <th
                              key={courtId}
                              className="px-2 py-3 text-center text-xs font-bold text-slate-700"
                            >
                              <div>{court?.court_name || 'Sân'}</div>
                              {court?.category_name && (
                                <div className="mt-0.5 font-normal text-slate-400">
                                  {SPORTS[court.category_name] || ''} {court.category_name}
                                </div>
                              )}
                            </th>
                          )
                        })}
                      </tr>
                    </thead>
                    <tbody>
                      {matrix.times.map((time) => (
                        <tr key={time} className="border-b border-slate-100 last:border-0">
                          <td className="sticky left-0 z-10 bg-white px-4 py-2 text-xs font-semibold text-slate-600">
                            {time}
                          </td>
                          {matrix.courts.map((courtId) => {
                            const slot = matrix.byCourt[courtId].find(
                              (s) => s.start_time_str === time,
                            )
                            if (!slot) {
                              return (
                                <td key={courtId} className="px-2 py-2">
                                  <div className="h-10 rounded-lg bg-slate-50" />
                                </td>
                              )
                            }
                            return (
                              <td key={courtId} className="px-2 py-2">
                                <SlotCell
                                  slot={slot}
                                  selected={selected.some((s) => s.id === slot.id)}
                                  onClick={() => toggleSlot(slot)}
                                />
                              </td>
                            )
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Thông tin cụm sân */}
            <div className="card p-6">
              <h2 className="font-bold text-slate-900">Giới thiệu</h2>
              <p className="mt-2.5 whitespace-pre-line text-sm leading-relaxed text-slate-600">
                {facility.description || 'Chưa có mô tả.'}
              </p>
              {facility.highlights && (
                <div className="mt-4 space-y-2 border-t border-slate-100 pt-4">
                  {facility.highlights.split('|').map((h, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm text-slate-600">
                      <span className="mt-0.5 text-brand-500">✓</span>
                      {h.trim()}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Đánh giá */}
            {facility.reviews?.length > 0 && (
              <div className="card p-6">
                <h2 className="font-bold text-slate-900">
                  Đánh giá ({facility.reviews.length})
                </h2>
                <div className="mt-4 space-y-4">
                  {facility.reviews.map((review) => (
                    <div key={review.id} className="border-b border-slate-100 pb-4 last:border-0 last:pb-0">
                      <div className="flex items-center justify-between gap-3">
                        <div className="font-semibold text-slate-800">
                          {review.reviewer_name}
                        </div>
                        <RatingStars value={review.rating} size="sm" />
                      </div>
                      <p className="mt-2 text-sm text-slate-600">{review.comment}</p>
                      {review.owner_reply && (
                        <div className="mt-2.5 rounded-lg bg-brand-50 p-3 text-sm">
                          <div className="mb-1 text-xs font-bold text-brand-700">
                            Phản hồi từ chủ sân
                          </div>
                          <p className="text-slate-700">{review.owner_reply}</p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* ---------------- SIDEBAR ---------------- */}
          <aside className="space-y-5 lg:sticky lg:top-24 lg:self-start">
            {/* Giá & đặt sân */}
            <div className="card p-5">
              {facility.average_rating > 0 && (
                <div className="mb-4 flex items-center gap-3 border-b border-slate-100 pb-4">
                  <span className="text-3xl font-bold text-slate-900">
                    {facility.average_rating.toFixed(1)}
                  </span>
                  <div>
                    <RatingStars value={facility.average_rating} size="md" />
                    <div className="mt-0.5 text-xs text-slate-500">
                      {facility.total_reviews} đánh giá
                    </div>
                  </div>
                </div>
              )}

              <div className="space-y-2 text-sm">
                <InfoRow label="Giờ mở cửa" value={`${facility.open_time} - ${facility.close_time}`} />
                <InfoRow label="Tổng số sân" value={`${facility.total_courts} sân`} />
                <InfoRow
                  label="Giá từ"
                  value={
                    facility.min_price
                      ? `${facility.min_price.toLocaleString('vi-VN')}đ / giờ`
                      : 'Liên hệ'
                  }
                />
                <InfoRow label="Hotline" value={facility.hotline || facility.phone_contact} />
              </div>

              {/* Dịch vụ phụ */}
              {facility.addon_services?.length > 0 && (
                <div className="mt-4 border-t border-slate-100 pt-4">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    Dịch vụ phụ
                  </h3>
                  <div className="mt-2 space-y-1.5">
                    {facility.addon_services.slice(0, 6).map((addon) => (
                      <div
                        key={addon.id}
                        className="flex items-center justify-between text-sm"
                      >
                        <span className="text-slate-600">
                          {addon.icon} {addon.name}
                        </span>
                        <span className="font-medium text-slate-700">
                          {Number(addon.unit_price).toLocaleString('vi-VN')}đ
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Giỏ hàng slot */}
              {selected.length > 0 && (
                <div className="mt-4 animate-fade-in rounded-xl border border-brand-200 bg-brand-50 p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-brand-800">
                      Đã chọn {selected.length} khung giờ
                    </span>
                    <button
                      onClick={() => setSelected([])}
                      className="text-xs font-medium text-brand-600 hover:underline"
                    >
                      Xóa
                    </button>
                  </div>
                  <div className="mt-3 space-y-1.5 border-t border-brand-200 pt-3 text-sm">
                    {selected.slice(0, 4).map((s) => (
                      <div key={s.id} className="flex justify-between text-brand-800">
                        <span>
                          {s.start_time_str}-{s.end_time_str} · {s.court_name}
                        </span>
                        <span className="font-medium">
                          {Number(s.price).toLocaleString('vi-VN')}đ
                        </span>
                      </div>
                    ))}
                    {selected.length > 4 && (
                      <div className="text-xs text-brand-600">
                        +{selected.length - 4} khung giờ khác
                      </div>
                    )}
                  </div>
                  <div className="mt-3 flex items-center justify-between border-t border-brand-200 pt-3">
                    <span className="font-semibold text-brand-900">Tổng cộng</span>
                    <span className="text-lg font-bold text-brand-700">
                      {totalPrice.toLocaleString('vi-VN')}đ
                    </span>
                  </div>
                </div>
              )}

              <button
                onClick={handleBook}
                disabled={selected.length === 0}
                className="btn-primary mt-4 w-full"
              >
                {selected.length === 0
                  ? 'Chọn khung giờ để đặt'
                  : `Đặt sân (${selected.length} khung)`}
              </button>

              <p className="mt-2.5 text-center text-xs text-slate-400">
                Slot được giữ trong 10 phút sau khi đặt
              </p>
            </div>
          </aside>
        </div>
      </div>

      {/* ---------------- MODAL THANH TOÁN ---------------- */}
      <CheckoutModal
        open={showCheckout}
        booking={booking}
        onClose={() => setShowCheckout(false)}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Ô slot trong ma trận
// ---------------------------------------------------------------------------
function SlotCell({ slot, selected, onClick }) {
  const base =
    'flex h-10 w-full items-center justify-center rounded-lg border text-[11px] font-semibold transition-all'

  if (selected) {
    return (
      <button
        onClick={onClick}
        className={`${base} border-brand-600 bg-brand-600 text-white shadow-sm`}
        title={`${slot.start_time_str}-${slot.end_time_str} - ${Number(slot.price).toLocaleString('vi-VN')}đ`}
      >
        ✓
      </button>
    )
  }

  if (!slot.is_available) {
    // Phân biệt "đã qua" (khung giờ đã trôi qua) vs "đã đặt / đang giữ chỗ"
    const isPast = isSlotPast(slot)
    return (
      <div
        className={`${base} cursor-not-allowed ${
          isPast
            ? 'border-slate-100 bg-slate-100 text-slate-300'
            : 'border-slate-200 bg-slate-200 text-slate-400'
        }`}
        title={
          isPast
            ? 'Khung giờ đã qua'
            : 'Khung giờ đã được đặt hoặc đang giữ chỗ'
        }
      >
        {isPast ? '—' : '✕'}
      </div>
    )
  }

  return (
    <button
      onClick={onClick}
      className={`${base} border-slate-200 bg-white text-slate-600 hover:border-brand-400 hover:bg-brand-50 hover:text-brand-700`}
      title={`${slot.start_time_str}-${slot.end_time_str} - ${Number(slot.price).toLocaleString('vi-VN')}đ`}
    >
      {Number(slot.price).toLocaleString('vi-VN')}đ
    </button>
  )
}

/**
 * Kiểm tra khung giờ đã trôi qua chưa (so sánh ngày + giờ với thời điểm hiện tại).
 */
function isSlotPast(slot) {
  const slotDate = new Date(`${slot.date}T${slot.start_time}:00`)
  return slotDate.getTime() <= Date.now()
}

// ---------------------------------------------------------------------------
// Dòng thông tin
// ---------------------------------------------------------------------------
function InfoRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-slate-500">{label}</span>
      <span className="text-right font-medium text-slate-800">{value}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Modal thanh toán (VietQR)
// ---------------------------------------------------------------------------
function CheckoutModal({ open, booking, onClose }) {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    if (open) {
      setFile(null)
    }
  }, [open])

  const handleUpload = async () => {
    if (!file || !booking) return
    setUploading(true)
    try {
      await bookingApi.uploadProof(booking.booking_code, file)
      toast('Đã gửi ảnh thanh toán. Chủ sân sẽ kiểm tra và phản hồi.')
      onClose()
    } catch (e) {
      toast(getErrorMessage(e, 'Không tải lên được ảnh bill.'), 'error')
    } finally {
      setUploading(false)
    }
  }

  if (!booking) return null

  return (
    <Modal open={open} onClose={onClose} title="Thanh toán đặt sân" size="md">
      <div className="space-y-5">
        {/* Thông tin đơn */}
        <div className="rounded-xl bg-slate-50 p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">Mã đơn</span>
            <span className="font-mono font-bold text-slate-900">
              {booking.booking_code}
            </span>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <span className="text-sm text-slate-500">Tổng tiền</span>
            <span className="text-lg font-bold text-brand-700">
              {Number(booking.total_amount).toLocaleString('vi-VN')}đ
            </span>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <span className="text-sm text-slate-500">Cụm sân</span>
            <span className="text-sm font-medium text-slate-800">
              {booking.facility_name}
            </span>
          </div>
        </div>

        {/* QR VietQR */}
        {booking.vietqr_url && (
          <div className="text-center">
            <p className="mb-3 text-sm font-medium text-slate-700">
              Quét mã QR để chuyển khoản
            </p>
            <img
              src={booking.vietqr_url}
              alt="QR thanh toán VietQR"
              className="mx-auto h-56 w-56 rounded-xl border border-slate-200 bg-white p-2"
              onError={(e) => {
                e.currentTarget.style.display = 'none'
              }}
            />
            <p className="mt-2.5 text-xs text-slate-500">
              Số tiền và nội dung đã được điền sẵn trong QR
            </p>
          </div>
        )}

        {/* Upload bill */}
        <div className="border-t border-slate-100 pt-4">
          <label className="label">Tải lên ảnh chuyển khoản (bill)</label>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="input file:mr-3 file:rounded-lg file:border-0 file:bg-brand-600 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white"
          />
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="btn-primary mt-3 w-full"
          >
            {uploading ? 'Đang tải lên...' : 'Gửi bill cho chủ sân'}
          </button>
          <p className="mt-2 text-center text-xs text-slate-400">
            Chủ sân sẽ kiểm tra và phản hồi trong thời gian sớm nhất
          </p>
        </div>
      </div>
    </Modal>
  )
}
