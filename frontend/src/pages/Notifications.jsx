/**
 * Trung tâm thông báo - Kiểu Gmail (đánh dấu đã xem / chưa xem).
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { notificationApi, getErrorMessage } from '@/lib/api'
import { EmptyState, ErrorAlert, LoadingScreen, toast } from '@/components/ui'

export default function Notifications() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('all')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await notificationApi.list()
      setItems(data)
    } catch (e) {
      setError(getErrorMessage(e, 'Khong tai duoc thong bao.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleMarkRead = async (id) => {
    // Cập nhật optimistic
    setItems((prev) =>
      prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
    )
    try {
      await notificationApi.markRead(id)
    } catch (e) {
      toast(getErrorMessage(e), 'error')
      load()
    }
  }

  const handleMarkAllRead = async () => {
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
    try {
      const res = await notificationApi.markRead()
      toast(`Da danh dau ${res.updated} thong bao da xem.`)
    } catch (e) {
      toast(getErrorMessage(e), 'error')
      load()
    }
  }

  const unread = items.filter((n) => !n.is_read)
  const filtered = tab === 'unread' ? unread : items

  const iconFor = (type) =>
    ({
      BOOKING_APPROVED: '✅',
      BOOKING_REJECTED: '❌',
      BOOKING_NEW: '📥',
      BOOKING_NEEDS_REUPLOAD: '🔄',
      BOOKING_CANCELLED: '🚫',
      SYSTEM: '🔔',
    })[type] || '🔔'

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 sm:text-3xl">
            Thông báo
          </h1>
          <p className="mt-1.5 text-sm text-slate-500">
            {unread.length > 0 ? `${unread.length} thông báo chưa đọc` : 'Đã đọc hết'}
          </p>
        </div>
        {unread.length > 0 && (
          <button onClick={handleMarkAllRead} className="btn-secondary !py-2 text-sm">
            ✓ Đánh dấu đã xem tất cả
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="mb-5 flex gap-2">
        {[
          { key: 'all', label: `Tất cả (${items.length})` },
          { key: 'unread', label: `Chưa đọc (${unread.length})` },
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

      {error && <ErrorAlert message={error} onRetry={load} />}

      {loading ? (
        <LoadingScreen label="Đang tải thông báo..." />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon="📭"
          title={tab === 'unread' ? 'Không có thông báo chưa đọc' : 'Chưa có thông báo nào'}
          description="Các thông báo về đơn đặt sân sẽ hiển thị ở đây."
        />
      ) : (
        <div className="card divide-y divide-slate-100 overflow-hidden">
          {filtered.map((n) => (
            <div
              key={n.id}
              className={`flex gap-3.5 p-4 transition-colors ${
                n.is_read ? 'bg-white' : 'bg-brand-50/50'
              }`}
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-lg">
                {iconFor(n.notification_type)}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-3">
                  <h3
                    className={`text-sm ${
                      n.is_read
                        ? 'font-medium text-slate-700'
                        : 'font-bold text-slate-900'
                    }`}
                  >
                    {n.title}
                    {!n.is_read && (
                      <span className="ml-2 inline-block h-2 w-2 rounded-full bg-brand-600 align-middle" />
                    )}
                  </h3>
                  <span className="shrink-0 text-xs text-slate-400">
                    {new Date(n.created_at).toLocaleString('vi-VN', {
                      day: '2-digit',
                      month: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>

                {n.message && (
                  <p className="mt-1 text-sm text-slate-600">{n.message}</p>
                )}

                <div className="mt-2 flex gap-3">
                  {!n.is_read && (
                    <button
                      onClick={() => handleMarkRead(n.id)}
                      className="text-xs font-medium text-brand-600 hover:underline"
                    >
                      Đánh dấu đã xem
                    </button>
                  )}
                  {n.link && (
                    <Link
                      to={n.link}
                      className="text-xs font-medium text-slate-500 hover:text-brand-600 hover:underline"
                    >
                      Xem chi tiết →
                    </Link>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
