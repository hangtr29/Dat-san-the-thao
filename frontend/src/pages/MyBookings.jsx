/**
 * Trang danh sách đơn đặt sân của khách hàng.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { bookingApi, getErrorMessage } from '@/lib/api'
import {
  BookingStatusBadge,
  EmptyState,
  ErrorAlert,
  LoadingScreen,
  Modal,
  toast,
} from '@/components/ui'

export default function MyBookings() {
  const [bookings, setBookings] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('ALL')
  const [detail, setDetail] = useState(null)
  const [cancelTarget, setCancelTarget] = useState(null)
  const [cancelReason, setCancelReason] = useState('')
  const [cancelling, setCancelling] = useState(false)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await bookingApi.list()
      setBookings(data)
    } catch (e) {
      setError(getErrorMessage(e, 'Không tải được danh sách đơn.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered =
    filter === 'ALL'
      ? bookings
      : bookings.filter((b) => b.status === filter)

  const handleCancel = async () => {
    if (!cancelTarget) return
    setCancelling(true)
    try {
      await bookingApi.cancel(cancelTarget.booking_code, cancelReason)
      toast('Đã hủy đơn đặt sân.')
      setCancelTarget(null)
      setCancelReason('')
      load()
    } catch (e) {
      toast(getErrorMessage(e, 'Không hủy được đơn.'), 'error')
    } finally {
      setCancelling(false)
    }
  }

  const FILTERS = [
    { key: 'ALL', label: 'Tất cả' },
    { key: 'PENDING_BILL', label: 'Chờ thanh toán' },
    { key: 'WAITING_APPROVAL', label: 'Chờ duyệt' },
    { key: 'CONFIRMED', label: 'Đã xác nhận' },
    { key: 'CANCELLED', label: 'Đã hủy' },
  ]

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 sm:text-3xl">
          Đơn đặt sân của tôi
        </h1>
        <p className="mt-1.5 text-sm text-slate-500">
          {loading ? 'Đang tải...' : `${bookings.length} đơn`}
        </p>
      </div>

      {/* Filters */}
      <div className="mb-5 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`rounded-xl px-3.5 py-2 text-sm font-medium transition-colors ${
              filter === f.key
                ? 'bg-brand-600 text-white shadow-sm'
                : 'bg-white text-slate-600 hover:bg-slate-100'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <ErrorAlert message={error} onRetry={load} />}

      {loading ? (
        <LoadingScreen label="Đang tải đơn đặt sân..." />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon="📋"
          title="Chưa có đơn đặt sân nào"
          description="Hãy tìm một cụm sân và đặt lịch để xem đơn tại đây."
          action={
            <Link to="/facilities" className="btn-primary">
              Tìm cụm sân
            </Link>
          }
        />
      ) : (
        <div className="space-y-3">
          {filtered.map((booking) => (
            <div key={booking.id} className="card-hover p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span className="font-mono text-sm font-bold text-slate-900">
                      {booking.booking_code}
                    </span>
                    <BookingStatusBadge status={booking.status} />
                  </div>

                  <div className="mt-2.5 space-y-1 text-sm text-slate-600">
                    <div className="flex items-center gap-1.5">
                      <span>🏟</span>
                      <span className="font-medium">{booking.facility_name}</span>
                      {booking.court_name && (
                        <span className="text-slate-400">· {booking.court_name}</span>
                      )}
                    </div>
                    {booking.slot_summary && (
                      <div className="flex items-center gap-1.5 text-slate-500">
                        <span>🕐</span>
                        <span>{booking.slot_summary}</span>
                      </div>
                    )}
                    <div className="flex items-center gap-1.5 text-slate-500">
                      <span>📅</span>
                      <span>{new Date(booking.created_at).toLocaleString('vi-VN')}</span>
                    </div>
                  </div>
                </div>

                <div className="flex shrink-0 flex-col items-end gap-2">
                  <div className="text-right">
                    <div className="text-xs text-slate-500">Tổng tiền</div>
                    <div className="text-lg font-bold text-brand-700">
                      {Number(booking.total_amount).toLocaleString('vi-VN')}đ
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setDetail(booking)}
                      className="btn-secondary !px-3 !py-1.5 text-xs"
                    >
                      Chi tiết
                    </button>
                    {['PENDING_BILL', 'WAITING_APPROVAL', 'NEEDS_REUPLOAD'].includes(
                      booking.status,
                    ) && (
                      <button
                        onClick={() => setCancelTarget(booking)}
                        className="rounded-lg px-3 py-1.5 text-xs font-semibold text-red-600 transition-colors hover:bg-red-50"
                      >
                        Hủy
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal chi tiết */}
      <Modal
        open={!!detail}
        onClose={() => setDetail(null)}
        title="Chi tiết đơn đặt sân"
      >
        {detail && (
          <div className="space-y-4">
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-500">Mã đơn</span>
                <span className="font-mono font-bold">{detail.booking_code}</span>
              </div>
              <div className="mt-2 flex items-center justify-between">
                <span className="text-sm text-slate-500">Trạng thái</span>
                <BookingStatusBadge status={detail.status} />
              </div>
              <div className="mt-2 flex items-center justify-between">
                <span className="text-sm text-slate-500">Cụm sân</span>
                <span className="text-sm font-medium">{detail.facility_name}</span>
              </div>
              <div className="mt-2 flex items-center justify-between">
                <span className="text-sm text-slate-500">Tổng tiền</span>
                <span className="font-bold text-brand-700">
                  {Number(detail.total_amount).toLocaleString('vi-VN')}đ
                </span>
              </div>
            </div>

            {/* Slots */}
            {detail.slots?.length > 0 && (
              <div>
                <h4 className="mb-2 text-sm font-bold text-slate-700">Khung giờ</h4>
                <div className="space-y-1.5">
                  {detail.slots.map((slot) => (
                    <div
                      key={slot.id}
                      className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm"
                    >
                      <span className="text-slate-700">
                        {slot.court_name} · {slot.start_time_str}-{slot.end_time_str}
                      </span>
                      <span className="font-medium">
                        {Number(slot.price).toLocaleString('vi-VN')}đ
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Addons */}
            {detail.addons?.length > 0 && (
              <div>
                <h4 className="mb-2 text-sm font-bold text-slate-700">Dịch vụ phụ</h4>
                <div className="space-y-1.5">
                  {detail.addons.map((addon) => (
                    <div
                      key={addon.id}
                      className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm"
                    >
                      <span className="text-slate-700">
                        {addon.name} x{addon.quantity}
                      </span>
                      <span className="font-medium">
                        {Number(addon.subtotal).toLocaleString('vi-VN')}đ
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {detail.reject_reason && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-sm">
                <div className="mb-1 font-bold text-amber-800">Lý do từ chối</div>
                <p className="text-amber-700">{detail.reject_reason}</p>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* Modal hủy */}
      <Modal
        open={!!cancelTarget}
        onClose={() => setCancelTarget(null)}
        title="Hủy đơn đặt sân"
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            Bạn có chắc muốn hủy đơn{' '}
            <span className="font-mono font-bold">{cancelTarget?.booking_code}</span>?
            Khung giờ sẽ được giải phóng ngay.
          </p>
          <div>
            <label className="label">Lý do hủy (không bắt buộc)</label>
            <textarea
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              rows={3}
              placeholder="VD: Đổi lịch, không thể đến..."
              className="input resize-none"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setCancelTarget(null)}
              className="btn-secondary flex-1"
            >
              Không
            </button>
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="btn-primary flex-1 !bg-red-600 hover:!bg-red-700"
            >
              {cancelling ? 'Đang hủy...' : 'Xác nhận hủy'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
