/**
 * Trang đăng nhập & đăng ký - dùng chung component.
 */
import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { getErrorMessage } from '@/lib/api'
import { toast } from '@/components/ui'

export function LoginPage() {
  return <AuthForm mode="login" />
}

export function RegisterPage() {
  return <AuthForm mode="register" />
}

function AuthForm({ mode }) {
  const isLogin = mode === 'login'
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [form, setForm] = useState({
    username: '',
    email: '',
    phone: '',
    password: '',
    password_confirm: '',
    role: 'CUSTOMER',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!isLogin && form.password !== form.password_confirm) {
      setError('Xác nhận mật khẩu không khớp.')
      return
    }

    setLoading(true)
    try {
      if (isLogin) {
        const data = await login({
          username: form.username,
          password: form.password,
        })
        toast(data.message || 'Đăng nhập thành công!')
      } else {
        const data = await register({
          username: form.username,
          email: form.email || undefined,
          phone: form.phone || undefined,
          password: form.password,
          password_confirm: form.password_confirm,
          role: form.role,
        })
        toast(data.message || 'Đăng ký thành công!')
      }
      navigate(location.state?.from || '/', { replace: true })
    } catch (err) {
      setError(getErrorMessage(err, 'Không thể thực hiện. Vui lòng thử lại.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-gradient-to-br from-brand-50 via-slate-50 to-emerald-50 px-4 py-10">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="mb-6 text-center">
          <img
            src="/logo.png"
            alt="SportBook"
            className="mx-auto h-16 w-auto object-contain"
          />
          <h1 className="mt-4 text-2xl font-bold text-slate-900">
            {isLogin ? 'Đăng nhập' : 'Tạo tài khoản'}
          </h1>
          <p className="mt-1.5 text-sm text-slate-500">
            {isLogin
              ? 'Chào mừng trở lại với SportBook'
              : 'Đăng ký để bắt đầu đặt sân thể thao'}
          </p>
        </div>

        {/* Form */}
        <div className="card p-6 sm:p-7">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Username */}
            <div>
              <label className="label">
                {isLogin ? 'Tên đăng nhập hoặc email' : 'Tên đăng nhập'}
              </label>
              <input
                type="text"
                name="username"
                value={form.username}
                onChange={handleChange}
                required
                autoComplete="username"
                placeholder="vidu: khachhang1"
                className="input"
              />
            </div>

            {/* Email (chỉ khi đăng ký) */}
            {!isLogin && (
              <div>
                <label className="label">Email (không bắt buộc)</label>
                <input
                  type="email"
                  name="email"
                  value={form.email}
                  onChange={handleChange}
                  autoComplete="email"
                  placeholder="email@example.com"
                  className="input"
                />
              </div>
            )}

            {/* Phone (chỉ khi đăng ký) */}
            {!isLogin && (
              <div>
                <label className="label">Số điện thoại (không bắt buộc)</label>
                <input
                  type="tel"
                  name="phone"
                  value={form.phone}
                  onChange={handleChange}
                  autoComplete="tel"
                  placeholder="0912345678"
                  className="input"
                />
              </div>
            )}

            {/* Role (chỉ khi đăng ký) */}
            {!isLogin && (
              <div>
                <label className="label">Bạn là</label>
                <div className="grid grid-cols-2 gap-2">
                  <RoleOption
                    active={form.role === 'CUSTOMER'}
                    onClick={() => setForm((p) => ({ ...p, role: 'CUSTOMER' }))}
                    icon="🏃"
                    title="Người chơi"
                    desc="Tìm & đặt sân"
                  />
                  <RoleOption
                    active={form.role === 'OWNER'}
                    onClick={() => setForm((p) => ({ ...p, role: 'OWNER' }))}
                    icon="🏟"
                    title="Chủ sân"
                    desc="Đăng ký cụm sân"
                  />
                </div>
              </div>
            )}

            {/* Password */}
            <div>
              <label className="label">Mật khẩu</label>
              <input
                type="password"
                name="password"
                value={form.password}
                onChange={handleChange}
                required
                minLength={6}
                autoComplete={isLogin ? 'current-password' : 'new-password'}
                placeholder="Tối thiểu 6 ký tự"
                className="input"
              />
            </div>

            {/* Confirm password */}
            {!isLogin && (
              <div>
                <label className="label">Xác nhận mật khẩu</label>
                <input
                  type="password"
                  name="password_confirm"
                  value={form.password_confirm}
                  onChange={handleChange}
                  required
                  minLength={6}
                  autoComplete="new-password"
                  placeholder="Nhập lại mật khẩu"
                  className="input"
                />
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            {/* Submit */}
            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading
                ? 'Đang xử lý...'
                : isLogin
                  ? 'Đăng nhập'
                  : 'Tạo tài khoản'}
            </button>
          </form>

          {/* Switch */}
          <div className="mt-5 border-t border-slate-100 pt-5 text-center text-sm text-slate-500">
            {isLogin ? (
              <>
                Chưa có tài khoản?{' '}
                <Link to="/register" className="font-semibold text-brand-600 hover:underline">
                  Đăng ký ngay
                </Link>
              </>
            ) : (
              <>
                Đã có tài khoản?{' '}
                <Link to="/login" className="font-semibold text-brand-600 hover:underline">
                  Đăng nhập
                </Link>
              </>
            )}
          </div>
        </div>

        {/* Demo accounts */}
        {isLogin && (
          <div className="mt-4 rounded-xl border border-dashed border-slate-300 bg-white/60 p-4">
            <p className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">
              Tài khoản demo
            </p>
            <div className="space-y-1.5 text-xs text-slate-600">
              <DemoAccount
                role="Khách hàng"
                username="khachhang1"
                password="customer123"
                onClick={(u, p) => {
                  setForm((prev) => ({ ...prev, username: u, password: p }))
                }}
              />
              <DemoAccount
                role="Chủ sân"
                username="chusan"
                password="chusan123"
                onClick={(u, p) => {
                  setForm((prev) => ({ ...prev, username: u, password: p }))
                }}
              />            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function RoleOption({ active, onClick, icon, title, desc }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl border-2 p-3 text-left transition-all ${
        active
          ? 'border-brand-500 bg-brand-50'
          : 'border-slate-200 hover:border-slate-300'
      }`}
    >
      <div className="text-xl">{icon}</div>
      <div className="mt-1 text-sm font-semibold text-slate-800">{title}</div>
      <div className="text-xs text-slate-500">{desc}</div>
    </button>
  )
}

function DemoAccount({ role, username, password, onClick }) {
  return (
    <button
      type="button"
      onClick={() => onClick(username, password)}
      className="flex w-full items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-left transition-colors hover:bg-slate-100"
    >
      <span className="font-medium">{role}</span>
      <span className="font-mono text-slate-500">
        {username} / {password}
      </span>
    </button>
  )
}
