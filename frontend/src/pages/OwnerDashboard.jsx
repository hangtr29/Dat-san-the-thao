/**
 * Kênh chủ sân - Dashboard quản lý đơn đặt sân, cụm sân và doanh thu.
 */
import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { ownerApi, getErrorMessage } from '@/lib/api'
import {
  BookingStatusBadge,
  EmptyState,
  ErrorAlert,
  LoadingScreen,
  Modal,
  toast,
} from '@/components/ui'

export default function OwnerDashboard() {
  const [tab, setTab] = useState('pending')
  const [bookings, setBookings] = useState([])
  const [facilities, setFacilities] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [rejectTarget, setRejectTarget] = useState(null)
  const [rejectReason, setRejectReason] = useState('')
  const [processing, setProcessing] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [b, f, s] = await Promise.all([
        ownerApi.bookings(),
        ownerApi.facilities(),
        ownerApi.stats(),
      ])
      setBookings(b)
      setFacilities(f)
      setStats(s)
    } catch (e) {
      setError(getErrorMessage(e, 'Không tải được dữ liệu chủ sân.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleApprove = async (booking) => {
    setProcessing(true)
    try {
      await ownerApi.approve(booking.booking_code)
      toast(`Đã duyệt đơn ${booking.booking_code}.`)
      load()
    } catch (e) {
      toast(getErrorMessage(e, 'Không duyệt được đơn.'), 'error')
    } finally {
      setProcessing(false)
    }
  }

  const handleReject = async () => {
    if (!rejectTarget) return
    setProcessing(true)
    try {
      await ownerApi.reject(rejectTarget.booking_code, rejectReason)
      toast(`Đã từ chối đơn ${rejectTarget.booking_code}.`)
      setRejectTarget(null)
      setRejectReason('')
      load()
    } catch (e) {
      toast(getErrorMessage(e, 'Không từ chối được đơn.'), 'error')
    } finally {
      setProcessing(false)
    }
  }

  const pending = bookings.filter((b) => b.status === 'WAITING_APPROVAL')
  const confirmed = bookings.filter((b) => b.status === 'CONFIRMED')
  const rejected = bookings.filter((b) =>
    ['REJECTED', 'NEEDS_REUPLOAD'].includes(b.status),
  )

  const tabData = {
    pending: { list: pending, empty: 'Không có đơn nào chờ duyệt.', icon: '📥' },
    confirmed: { list: confirmed, empty: 'Chưa có đơn nào được xác nhận.', icon: '✅' },
    rejected: { list: rejected, empty: 'Không có đơn nào bị từ chối.', icon: '❌' },
    all: { list: bookings, empty: 'Chưa có đơn nào.', icon: '📋' },
  }

  if (loading) return <LoadingScreen label="Đang tải dữ liệu chủ sân..." />

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 sm:text-3xl">
          Kênh chủ sân
        </h1>
        <p className="mt-1.5 text-sm text-slate-500">
          Quản lý đơn đặt sân, cụm sân và theo dõi doanh thu
        </p>
      </div>

      {error && <ErrorAlert message={error} onRetry={load} />}

      {/* Stats */}
      {stats && (
        <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Tổng đơn"
            value={stats.total_bookings}
            icon="📋"
            color="from-blue-500 to-blue-600"
          />
          <StatCard
            label="Tổng doanh thu"
            value={`${Number(stats.total_revenue || 0).toLocaleString('vi-VN')}đ`}
            icon="💰"
            color="from-brand-500 to-brand-600"
          />
          <StatCard
            label="Chờ duyệt"
            value={pending.length}
            icon="⏳"
            color="from-amber-500 to-amber-600"
          />
          <StatCard
            label="Cụm sân"
            value={facilities.length}
            icon="🏟"
            color="from-purple-500 to-purple-600"
          />
        </div>
      )}

      {/* Tabs */}
      <div className="mb-5 flex flex-wrap gap-2">
        {[
          { key: 'pending', label: `Chờ duyệt (${pending.length})` },
          { key: 'confirmed', label: `Đã xác nhận (${confirmed.length})` },
          { key: 'rejected', label: `Từ chối (${rejected.length})` },
          { key: 'all', label: `Tất cả (${bookings.length})` },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-xl px-3.5 py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? 'bg-brand-600 text-white shadow-sm'
                : 'bg-white text-slate-600 hover:bg-slate-100'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Bookings */}
      <div className="space-y-3">
        {tabData[tab].list.length === 0 ? (
          <EmptyState
            icon={tabData[tab].icon}
            title={tabData[tab].empty}
            description="Các đơn mới sẽ hiển thị ở đây."
          />
        ) : (
          tabData[tab].list.map((booking) => (
            <div key={booking.id} className="card p-5">
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
                  </div>
                </div>

                <div className="flex shrink-0 flex-col items-end gap-2">
                  <div className="text-lg font-bold text-brand-700">
                    {Number(booking.total_amount).toLocaleString('vi-VN')}đ
                  </div>
                  {booking.status === 'WAITING_APPROVAL' && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleApprove(booking)}
                        disabled={processing}
                        className="rounded-lg bg-brand-600 px-3.5 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
                      >
                        ✓ Duyệt
                      </button>
                      <button
                        onClick={() => setRejectTarget(booking)}
                        disabled={processing}
                        className="rounded-lg bg-red-50 px-3.5 py-1.5 text-xs font-semibold text-red-600 transition-colors hover:bg-red-100 disabled:opacity-50"
                      >
                        ✕ Từ chối
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Facilities */}
      <div className="mt-8">
        <h2 className="mb-4 text-lg font-bold text-slate-900">
          Cụm sân của tôi ({facilities.length})
        </h2>
        {facilities.length === 0 ? (
          <EmptyState
            icon="🏟"
            title="Bạn chưa đăng ký cụm sân nào"
            description="Đăng ký cụm sân để nhận đơn đặt từ người chơi."
            action={
              <Link to="/owner/register" className="btn-primary">
                Đăng ký cụm sân
              </Link>
            }
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {facilities.map((f) => (
              <div key={f.id} className="card p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate font-bold text-slate-900">{f.name}</h3>
                    <p className="mt-1 line-clamp-2 text-xs text-slate-500">
                      {f.address}
                    </p>
                  </div>
                  <span
                    className={
                      f.status === 'ACTIVE'
                        ? 'badge-green shrink-0'
                        : f.status === 'PENDING_REVIEW'
                          ? 'badge-amber shrink-0'
                          : 'badge-gray shrink-0'
                    }
                  >
                    {f.status === 'ACTIVE'
                      ? 'Hoạt động'
                      : f.status === 'PENDING_REVIEW'
                        ? 'Chờ duyệt'
                        : f.status}
                  </span>
                </div>
                <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-xs text-slate-500">
                  <span>🏸 {f.total_courts} sân</span>
                  <span className="font-medium text-slate-700">
                    từ {f.min_price?.toLocaleString('vi-VN')}đ
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal từ chối */}
      <Modal
        open={!!rejectTarget}
        onClose={() => setRejectTarget(null)}
        title="Từ chối đơn đặt sân"
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            Từ chối đơn{' '}
            <span className="font-mono font-bold">{rejectTarget?.booking_code}</span>.
            Khách sẽ được yêu cầu tải lại bill.
          </p>
          <div>
            <label className="label">Lý do từ chối</label>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              rows={3}
              placeholder="VD: Ảnh bill không rõ, sai số tiền..."
              className="input resize-none"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setRejectTarget(null)}
              className="btn-secondary flex-1"
            >
              Hủy
            </button>
            <button
              onClick={handleReject}
              disabled={processing}
              className="btn-primary flex-1 !bg-red-600 hover:!bg-red-700"
            >
              Xác nhận từ chối
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

function StatCard({ label, value, icon, color }) {
  return (
    <div className="card overflow-hidden">
      <div className={`bg-gradient-to-br ${color} p-5 text-white`}>
        <div className="flex items-center justify-between">
          <span className="text-3xl">{icon}</span>
        </div>
        <div className="mt-3 text-2xl font-extrabold">{value}</div>
        <div className="mt-0.5 text-xs text-white/80">{label}</div>
      </div>
    </div>
  )
}
