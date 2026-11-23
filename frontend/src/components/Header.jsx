/**
 * Header - Thanh điều hướng chính.
 */
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { useAuth } from '@/context/AuthContext'
import { notificationApi } from '@/lib/api'

export default function Header() {
  const { user, isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()
  const [unread, setUnread] = useState(0)
  const [menuOpen, setMenuOpen] = useState(false)

  // Dem thong bao chua doc
  useEffect(() => {
    if (!isAuthenticated) {
      setUnread(0)
      return
    }
    let active = true
    notificationApi
      .unreadCount()
      .then((count) => active && setUnread(count))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [isAuthenticated, user?.id])

  const handleLogout = async () => {
    await logout()
    setMenuOpen(false)
    navigate('/')
  }

  const navLinks = [
    { to: '/', label: 'Trang chu', end: true },
    { to: '/facilities', label: 'Tim san' },
    { to: '/map', label: 'Ban do' },
  ]

  if (isAuthenticated) {
    navLinks.push({ to: '/bookings', label: 'Don cua toi' })
    if (user?.role === 'OWNER' || user?.is_staff) {
      navLinks.push({ to: '/owner', label: 'Kenh chu san' })
    }
  }

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/90 backdrop-blur-lg">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2.5">
          <img
            src="/logo.png"
            alt="SportBook"
            className="h-9 w-auto object-contain"
          />
          <div className="hidden sm:block">
            <div className="text-base font-black leading-tight tracking-tight text-[#04331b]">
              SportBook
            </div>
            <div className="text-[11px] leading-tight text-slate-500">
              Đặt sân nhanh chóng
            </div>
          </div>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden items-center gap-1 md:flex">
          {navLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) =>
                `rounded-lg px-3.5 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-brand-50 text-brand-700'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {isAuthenticated ? (
            <>
              {/* Thong bao */}
              <Link
                to="/notifications"
                className="relative rounded-lg p-2 text-slate-600 transition-colors hover:bg-slate-100"
                title="Thong bao"
              >
                <svg
                  className="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M15 17h5l-1.4-1.4A2 2 0 0118 14.2V11a6 6 0 10-12 0v3.2c0 .5-.2 1-.6 1.4L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                  />
                </svg>
                {unread > 0 && (
                  <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                    {unread > 99 ? '99+' : unread}
                  </span>
                )}
              </Link>

              {/* User menu */}
              <div className="relative">
                <button
                  onClick={() => setMenuOpen((v) => !v)}
                  className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white py-1.5 pl-1.5 pr-3 transition-colors hover:border-brand-300 hover:bg-brand-50"
                >
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600 text-xs font-bold text-white">
                    {(user?.username?.[0] || 'U').toUpperCase()}
                  </div>
                  <span className="hidden max-w-24 truncate text-sm font-medium text-slate-700 sm:block">
                    {user?.username}
                  </span>
                  <svg className="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {menuOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-10"
                      onClick={() => setMenuOpen(false)}
                    />
                    <div className="absolute right-0 z-20 mt-2 w-56 animate-fade-in overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
                      <div className="border-b border-slate-100 px-4 py-3">
                        <div className="font-semibold text-slate-900">
                          {user?.full_name || user?.username}
                        </div>
                        <div className="mt-0.5 text-xs text-slate-500">
                          {user?.role_display}
                        </div>
                      </div>
                      <Link
                        to="/profile"
                        onClick={() => setMenuOpen(false)}
                        className="block px-4 py-2.5 text-sm text-slate-700 transition-colors hover:bg-slate-50"
                      >
                        Ho so ca nhan
                      </Link>
                      <Link
                        to="/favorites"
                        onClick={() => setMenuOpen(false)}
                        className="block px-4 py-2.5 text-sm text-slate-700 transition-colors hover:bg-slate-50"
                      >
                        San yeu thich
                      </Link>
                      <button
                        onClick={handleLogout}
                        className="block w-full border-t border-slate-100 px-4 py-2.5 text-left text-sm text-red-600 transition-colors hover:bg-red-50"
                      >
                        Dang xuat
                      </button>
                    </div>
                  </>
                )}
              </div>
            </>
          ) : (
            <div className="flex items-center gap-2">
              <Link to="/login" className="btn-ghost hidden sm:inline-flex">
                Dang nhap
              </Link>
              <Link to="/register" className="btn-primary !px-4 !py-2 text-sm">
                Dang ky
              </Link>
            </div>
          )}

          {/* Mobile menu toggle */}
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 md:hidden"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile nav */}
      {menuOpen && (
        <nav className="border-t border-slate-200 bg-white px-4 py-2 md:hidden">
          {navLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                `block rounded-lg px-3 py-2.5 text-sm font-medium ${
                  isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-700'
                }`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  )
}
