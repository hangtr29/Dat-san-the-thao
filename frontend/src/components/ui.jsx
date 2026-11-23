/**
 * Các component UI dùng chung: Loading, Empty, Error, Modal, Toast...
 */
import { useEffect, useState } from 'react'

// ---------------------------------------------------------------------------
// Loading spinner
// ---------------------------------------------------------------------------
export function Spinner({ className = 'h-6 w-6' }) {
  return (
    <svg
      className={`animate-spin ${className}`}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-20"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-90"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}

export function LoadingScreen({ label = 'Đang tải dữ liệu...' }) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3">
      <Spinner className="h-8 w-8 text-brand-600" />
      <p className="text-sm text-slate-500">{label}</p>
    </div>
  )
}

export function CardSkeleton({ count = 6 }) {
  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="card overflow-hidden">
          <div className="h-44 animate-pulse bg-slate-200" />
          <div className="space-y-3 p-5">
            <div className="h-5 w-3/4 animate-pulse rounded bg-slate-200" />
            <div className="h-4 w-full animate-pulse rounded bg-slate-100" />
            <div className="h-4 w-2/3 animate-pulse rounded bg-slate-100" />
            <div className="h-10 w-full animate-pulse rounded-xl bg-slate-100" />
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------
export function EmptyState({ icon = '🔍', title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
      <div className="mb-4 text-5xl">{icon}</div>
      <h3 className="text-lg font-semibold text-slate-800">{title}</h3>
      {description && (
        <p className="mt-1.5 max-w-md text-sm text-slate-500">{description}</p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Error alert
// ---------------------------------------------------------------------------
export function ErrorAlert({ message, onRetry, onDismiss }) {
  if (!message) return null
  return (
    <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
      <svg className="mt-0.5 h-5 w-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M5.07 19h13.86a2 2 0 001.74-3L13.74 4a2 2 0 00-3.48 0l-7 12a2 2 0 001.74 3z" />
      </svg>
      <div className="flex-1">
        <p className="font-medium">{message}</p>
      </div>
      <div className="flex shrink-0 gap-2">
        {onRetry && (
          <button
            onClick={onRetry}
            className="rounded-lg bg-red-100 px-3 py-1.5 font-medium text-red-700 transition-colors hover:bg-red-200"
          >
            Thử lại
          </button>
        )}
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="rounded-lg px-2 py-1.5 text-red-500 transition-colors hover:bg-red-100"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Toast notification
// ---------------------------------------------------------------------------
let toastId = 0
const listeners = new Set()

export function toast(message, type = 'success') {
  const id = ++toastId
  listeners.forEach((fn) => fn({ id, message, type }))
  setTimeout(() => {
    listeners.forEach((fn) => fn({ id, message: null, type }))
  }, 4000)
}

export function ToastContainer() {
  const [items, setItems] = useState([])

  useEffect(() => {
    const handler = ({ id, message, type }) => {
      setItems((prev) => {
        if (!message) return prev.filter((t) => t.id !== id)
        const exists = prev.find((t) => t.id === id)
        if (exists) return prev.map((t) => (t.id === id ? { ...t, message, type } : t))
        return [...prev, { id, message, type }]
      })
    }
    listeners.add(handler)
    return () => listeners.delete(handler)
  }, [])

  if (!items.length) return null

  const styles = {
    success: 'border-brand-200 bg-brand-50 text-brand-800',
    error: 'border-red-200 bg-red-50 text-red-800',
    info: 'border-blue-200 bg-blue-50 text-blue-800',
    warning: 'border-amber-200 bg-amber-50 text-amber-800',
  }
  const icons = { success: '✓', error: '✕', info: 'ℹ', warning: '!' }

  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-[100] flex w-full max-w-sm flex-col gap-2">
      {items.map((item) => (
        <div
          key={item.id}
          className={`pointer-events-auto animate-slide-up rounded-xl border px-4 py-3 text-sm font-medium shadow-lg ${styles[item.type]}`}
        >
          <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-white/70 text-xs">
            {icons[item.type]}
          </span>
          {item.message}
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------
export function Modal({ open, onClose, title, children, size = 'md' }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e) => e.key === 'Escape' && onClose?.()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!open) return null

  const sizes = {
    sm: 'max-w-sm',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
  }

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        className={`relative z-10 max-h-[90vh] w-full ${sizes[size]} animate-fade-in overflow-hidden rounded-2xl bg-white shadow-2xl`}
      >
        {title && (
          <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
            <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}
        <div className="max-h-[calc(90vh-4rem)] overflow-y-auto px-6 py-5">
          {children}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------
export function Pagination({ page, totalPages, onChange }) {
  if (!totalPages || totalPages <= 1) return null

  const pages = []
  const start = Math.max(1, page - 2)
  const end = Math.min(totalPages, start + 4)
  for (let i = start; i <= end; i++) pages.push(i)

  return (
    <nav className="flex items-center justify-center gap-1.5 pt-2">
      <button
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
        className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-40"
      >
        ‹
      </button>
      {start > 1 && (
        <>
          <button
            onClick={() => onChange(1)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          >
            1
          </button>
          <span className="px-1 text-slate-400">…</span>
        </>
      )}
      {pages.map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
            p === page
              ? 'border-brand-600 bg-brand-600 text-white'
              : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
          }`}
        >
          {p}
        </button>
      ))}
      {end < totalPages && (
        <>
          <span className="px-1 text-slate-400">…</span>
          <button
            onClick={() => onChange(totalPages)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          >
            {totalPages}
          </button>
        </>
      )}
      <button
        onClick={() => onChange(page + 1)}
        disabled={page >= totalPages}
        className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-40"
      >
        ›
      </button>
    </nav>
  )
}

// ---------------------------------------------------------------------------
// Status badge cho đơn đặt sân
// ---------------------------------------------------------------------------
const BOOKING_STATUS = {
  PENDING_BILL: { label: 'Chờ thanh toán', className: 'badge-amber' },
  WAITING_APPROVAL: { label: 'Chờ chủ sân duyệt', className: 'badge-blue' },
  CONFIRMED: { label: 'Đã xác nhận', className: 'badge-green' },
  REJECTED: { label: 'Bị từ chối', className: 'badge-red' },
  NEEDS_REUPLOAD: { label: 'Cần tải lại bill', className: 'badge-amber' },
  CANCELLED: { label: 'Đã hủy', className: 'badge-gray' },
}

export function BookingStatusBadge({ status }) {
  const config = BOOKING_STATUS[status] || { label: status, className: 'badge-gray' }
  return <span className={config.className}>{config.label}</span>
}

// ---------------------------------------------------------------------------
// Rating stars
// ---------------------------------------------------------------------------
export function RatingStars({ value = 0, count, size = 'sm' }) {
  const sizes = { sm: 'h-3.5 w-3.5', md: 'h-4 w-4', lg: 'h-5 w-5' }
  return (
    <div className="flex items-center gap-1">
      <div className="flex">
        {[1, 2, 3, 4, 5].map((i) => (
          <svg
            key={i}
            className={`${sizes[size]} ${
              i <= Math.round(value) ? 'text-amber-400' : 'text-slate-200'
            }`}
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path d="M9.05 2.93c.3-.92 1.6-.92 1.9 0l1.36 4.18a1 1 0 00.95.69h4.4c.97 0 1.37 1.24.59 1.81l-3.56 2.58a1 1 0 00-.36 1.12l1.36 4.18c.3.92-.76 1.69-1.54 1.12l-3.56-2.58a1 1 0 00-1.18 0l-3.56 2.58c-.78.57-1.84-.2-1.54-1.12l1.36-4.18a1 1 0 00-.36-1.12L1.74 9.61c-.78-.57-.38-1.81.59-1.81h4.4a1 1 0 00.95-.69L9.05 2.93z" />
          </svg>
        ))}
      </div>
      {count !== undefined && (
        <span className="text-xs text-slate-500">({count})</span>
      )}
    </div>
  )
}
