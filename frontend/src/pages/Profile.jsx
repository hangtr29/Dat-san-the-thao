/**
 * Trang Hồ sơ cá nhân - đồng bộ với bản Django gốc (templates/users/profile.html).
 *
 * Bao gồm:
 * - Header gradient: avatar, tên, vai trò, nhanh tới thông báo / đơn của tôi
 * - Thống kê: tổng đơn, đã xác nhận, tổng chi tiêu, sân yêu thích
 * - Sửa thông tin cá nhân (họ tên, email, số điện thoại, ảnh đại diện)
 * - Đổi mật khẩu
 * - Trợ giúp tài khoản + đơn đặt gần đây
 * - Thông tin hệ thống (username, UUID, ngày tham gia)
 */
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi, getErrorMessage } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { ErrorAlert, LoadingScreen, toast } from '@/components/ui'

const BOOKING_STATUS_CLASS = {
  CONFIRMED: 'bg-emerald-100 text-emerald-700',
  WAITING_APPROVAL: 'bg-blue-100 text-blue-700',
  PENDING_BILL: 'bg-amber-100 text-amber-700',
  NEEDS_REUPLOAD: 'bg-orange-100 text-orange-700',
  REJECTED: 'bg-rose-100 text-rose-700',
  CANCELLED: 'bg-slate-100 text-slate-600',
}

export default function ProfilePage() {
  const { user, setUser } = useAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Form thông tin cá nhân
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
  })
  const [avatarFile, setAvatarFile] = useState(null)
  const [avatarPreview, setAvatarPreview] = useState(null)
  const [savingProfile, setSavingProfile] = useState(false)
  const [profileError, setProfileError] = useState('')
  const fileInputRef = useRef(null)

  // Form đổi mật khẩu
  const [pwd, setPwd] = useState({
    old_password: '',
    new_password1: '',
    new_password2: '',
  })
  const [savingPwd, setSavingPwd] = useState(false)
  const [pwdError, setPwdError] = useState('')

  // ---- Tải hồ sơ ----
  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await authApi.profile()
      setData(res)
      setForm({
        first_name: res.user.first_name || '',
        last_name: res.user.last_name || '',
        email: res.user.email || '',
        phone: res.user.phone || '',
      })
      setAvatarPreview(res.user.avatar_url || null)
    } catch (e) {
      setError(getErrorMessage(e, 'Không tải được hồ sơ.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  // ---- Lưu thông tin cá nhân ----
  const handleSaveProfile = async (e) => {
    e.preventDefault()
    setSavingProfile(true)
    setProfileError('')
    try {
      const payload = { ...form }
      if (avatarFile) {
        payload.avatar = avatarFile
      }
      const res = await authApi.updateProfile(payload)
      setUser(res.user)
      toast(res.message || 'Cập nhật hồ sơ thành công.')
      setAvatarFile(null)
      await load()
    } catch (err) {
      setProfileError(getErrorMessage(err, 'Không cập nhật được hồ sơ.'))
    } finally {
      setSavingProfile(false)
    }
  }

  // ---- Chọn ảnh đại diện ----
  const handleAvatarChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 5 * 1024 * 1024) {
      toast('Ảnh quá lớn (tối đa 5MB).', 'error')
      return
    }
    setAvatarFile(file)
    setAvatarPreview(URL.createObjectURL(file))
  }

  // ---- Xóa ảnh đại diện ----
  const handleDeleteAvatar = async () => {
    if (!window.confirm('Xóa ảnh đại diện?')) return
    try {
      await authApi.deleteAvatar()
      setAvatarFile(null)
      setAvatarPreview(null)
      toast('Đã xóa ảnh đại diện.')
      await load()
    } catch (err) {
      toast(getErrorMessage(err, 'Không xóa được ảnh đại diện.'), 'error')
    }
  }

  // ---- Đổi mật khẩu ----
  const handleChangePassword = async (e) => {
    e.preventDefault()
    setSavingPwd(true)
    setPwdError('')
    try {
      const res = await authApi.changePassword(pwd)
      toast(res.message || 'Đổi mật khẩu thành công.')
      setPwd({ old_password: '', new_password1: '', new_password2: '' })
    } catch (err) {
      setPwdError(getErrorMessage(err, 'Không đổi được mật khẩu.'))
    } finally {
      setSavingPwd(false)
    }
  }

  if (loading) return <LoadingScreen label="Đang tải hồ sơ..." />

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-10">
        <ErrorAlert message={error} onRetry={load} />
      </div>
    )
  }

  const profile = data?.user || user || {}
  const stats = data?.stats || {}
  const recent = data?.recent_bookings || []
  const displayName = profile.full_name || profile.username || 'Người dùng'

  return (
    <div className="mx-auto my-8 max-w-5xl px-4 sm:px-6">
      {/* ---- Header ---- */}
      <div className="mb-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4 bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-6 text-white sm:px-8">
          <div className="flex items-center gap-4">
            {avatarPreview ? (
              <img
                src={avatarPreview}
                alt="Ảnh đại diện"
                className="h-16 w-16 rounded-2xl border-2 border-white/30 object-cover"
              />
            ) : (
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl border-2 border-white/30 bg-white/15 text-2xl font-black">
                {(profile.username || 'U').charAt(0).toUpperCase()}
              </div>
            )}
            <div>
              <h2 className="text-xl font-black">{displayName}</h2>
              <div className="mt-1.5 flex items-center gap-2">
                <span className="inline-block rounded-full border border-white/25 bg-white/20 px-3 py-0.5 text-[11px] font-black text-white">
                  {profile.role_display || 'Khách hàng'}
                </span>
                <span className="text-[11px] font-bold text-emerald-100">
                  @{profile.username}
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to="/notifications"
              className="rounded-xl bg-white/15 px-4 py-2.5 text-xs font-bold text-white transition hover:bg-white/25"
            >
              <i className="fa-solid fa-bell mr-1" />
              Thông báo
            </Link>
            <Link
              to="/bookings"
              className="rounded-xl bg-white/15 px-4 py-2.5 text-xs font-bold text-white transition hover:bg-white/25"
            >
              <i className="fa-solid fa-calendar-check mr-1" />
              Đơn của tôi
            </Link>
          </div>
        </div>

        {/* Thống kê */}
        <div className="grid grid-cols-2 divide-x divide-slate-100 sm:grid-cols-4">
          <div className="p-4 text-center">
            <div className="text-2xl font-black text-slate-800">
              {stats.total ?? 0}
            </div>
            <div className="mt-0.5 text-[10px] font-black uppercase tracking-wider text-slate-400">
              Tổng đơn
            </div>
          </div>
          <div className="p-4 text-center">
            <div className="text-2xl font-black text-emerald-600">
              {stats.confirmed ?? 0}
            </div>
            <div className="mt-0.5 text-[10px] font-black uppercase tracking-wider text-slate-400">
              Đã xác nhận
            </div>
          </div>
          <div className="p-4 text-center">
            <div className="text-2xl font-black text-amber-600">
              {Number(stats.spent ?? 0).toLocaleString('vi-VN')} đ
            </div>
            <div className="mt-0.5 text-[10px] font-black uppercase tracking-wider text-slate-400">
              Tổng chi tiêu
            </div>
          </div>
          <div className="p-4 text-center">
            <div className="text-2xl font-black text-rose-500">
              {stats.favorites ?? 0}
            </div>
            <div className="mt-0.5 text-[10px] font-black uppercase tracking-wider text-slate-400">
              Sân yêu thích
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* ---- SỬA THÔNG TIN CÁ NHÂN ---- */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="mb-1 flex items-center gap-2 text-sm font-black text-slate-800">
            <i className="fa-solid fa-user-pen text-emerald-600" />
            Sửa thông tin cá nhân
          </h3>
          <p className="mb-5 text-[11px] text-slate-500">
            Cập nhật tên, email, số điện thoại và ảnh đại diện của bạn.
          </p>

          {profileError && (
            <div className="mb-4">
              <ErrorAlert message={profileError} onDismiss={() => setProfileError('')} />
            </div>
          )}

          <form onSubmit={handleSaveProfile} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label
                  htmlFor="first_name"
                  className="mb-1.5 block text-[11px] font-black uppercase tracking-wider text-slate-500"
                >
                  Họ / Tên đệm
                </label>
                <input
                  id="first_name"
                  type="text"
                  value={form.first_name}
                  onChange={(e) =>
                    setForm({ ...form, first_name: e.target.value })
                  }
                  className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-700 transition focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                />
              </div>
              <div>
                <label
                  htmlFor="last_name"
                  className="mb-1.5 block text-[11px] font-black uppercase tracking-wider text-slate-500"
                >
                  Tên
                </label>
                <input
                  id="last_name"
                  type="text"
                  value={form.last_name}
                  onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-700 transition focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="phone"
                className="mb-1.5 block text-[11px] font-black uppercase tracking-wider text-slate-500"
              >
                Số điện thoại / Zalo
              </label>
              <input
                id="phone"
                type="tel"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-700 transition focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
              />
            </div>

            <div>
              <label
                htmlFor="email"
                className="mb-1.5 block text-[11px] font-black uppercase tracking-wider text-slate-500"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-700 transition focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
              />
            </div>

            <div>
              <label
                htmlFor="avatar"
                className="mb-1.5 block text-[11px] font-black uppercase tracking-wider text-slate-500"
              >
                Ảnh đại diện
              </label>
              <input
                id="avatar"
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleAvatarChange}
                className="block w-full cursor-pointer rounded-xl border border-slate-300 text-xs text-slate-500 transition file:mr-3 file:cursor-pointer file:rounded-l-xl file:border-0 file:bg-emerald-50 file:px-4 file:py-2.5 file:text-xs file:font-black file:text-emerald-700 hover:border-emerald-400"
              />
              {avatarPreview && !avatarFile && (
                <button
                  type="button"
                  onClick={handleDeleteAvatar}
                  className="mt-2 text-[11px] font-bold text-rose-500 hover:underline"
                >
                  <i className="fa-solid fa-trash mr-1" />
                  Xóa ảnh hiện tại
                </button>
              )}
            </div>

            <button
              type="submit"
              disabled={savingProfile}
              className="w-full rounded-xl bg-emerald-600 py-3 text-xs font-black uppercase tracking-wide text-white shadow-md transition hover:bg-emerald-700 disabled:opacity-60"
            >
              {savingProfile ? (
                <>
                  <i className="fa-solid fa-spinner fa-spin mr-1" />
                  Đang lưu...
                </>
              ) : (
                <>
                  <i className="fa-solid fa-floppy-disk mr-1" />
                  Lưu thay đổi
                </>
              )}
            </button>
          </form>
        </div>

        {/* ---- ĐỔI MẬT KHẨU + TRỢ GIÚP ---- */}
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="mb-1 flex items-center gap-2 text-sm font-black text-slate-800">
              <i className="fa-solid fa-key text-emerald-600" />
              Đổi mật khẩu
            </h3>
            <p className="mb-5 text-[11px] text-slate-500">
              Mật khẩu mới cần có ít nhất 8 ký tự và không quá thông dụng.
            </p>

            {pwdError && (
              <div className="mb-4">
                <ErrorAlert message={pwdError} onDismiss={() => setPwdError('')} />
              </div>
            )}

            <form onSubmit={handleChangePassword} className="space-y-4">
              <div>
                <label
                  htmlFor="old_password"
                  className="mb-1.5 block text-[11px] font-black uppercase tracking-wider text-slate-500"
                >
                  Mật khẩu hiện tại
                </label>
                <input
                  id="old_password"
                  type="password"
                  required
                  value={pwd.old_password}
                  onChange={(e) => setPwd({ ...pwd, old_password: e.target.value })}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-700 transition focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                />
              </div>
              <div>
                <label
                  htmlFor="new_password1"
                  className="mb-1.5 block text-[11px] font-black uppercase tracking-wider text-slate-500"
                >
                  Mật khẩu mới
                </label>
                <input
                  id="new_password1"
                  type="password"
                  required
                  minLength={8}
                  value={pwd.new_password1}
                  onChange={(e) => setPwd({ ...pwd, new_password1: e.target.value })}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-700 transition focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                />
              </div>
              <div>
                <label
                  htmlFor="new_password2"
                  className="mb-1.5 block text-[11px] font-black uppercase tracking-wider text-slate-500"
                >
                  Xác nhận mật khẩu mới
                </label>
                <input
                  id="new_password2"
                  type="password"
                  required
                  minLength={8}
                  value={pwd.new_password2}
                  onChange={(e) => setPwd({ ...pwd, new_password2: e.target.value })}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-700 transition focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                />
              </div>
              <button
                type="submit"
                disabled={savingPwd}
                className="w-full rounded-xl bg-emerald-600 py-3 text-xs font-black uppercase tracking-wide text-white shadow-md transition hover:bg-emerald-700 disabled:opacity-60"
              >
                {savingPwd ? (
                  <>
                    <i className="fa-solid fa-spinner fa-spin mr-1" />
                    Đang đổi...
                  </>
                ) : (
                  <>
                    <i className="fa-solid fa-lock mr-1" />
                    Đổi mật khẩu
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Trợ giúp tài khoản */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="mb-4 flex items-center gap-2 text-sm font-black text-slate-800">
              <i className="fa-solid fa-circle-question text-emerald-600" />
              Trợ giúp tài khoản
            </h3>
            <Link
              to="/bookings"
              className="mb-4 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 transition hover:bg-slate-100"
            >
              <span className="text-xs font-bold text-slate-700">
                <i className="fa-solid fa-calendar-check mr-1 text-emerald-600" />
                Quản lý đơn đặt sân
              </span>
              <i className="fa-solid fa-chevron-right text-xs text-slate-400" />
            </Link>

            <div className="mb-2 text-[11px] font-black uppercase tracking-wider text-slate-400">
              Đơn đặt gần đây
            </div>
            <div className="space-y-1.5">
              {recent.map((b) => (
                <Link
                  key={b.id}
                  to="/bookings"
                  className="flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 transition hover:bg-slate-50"
                >
                  <div className="min-w-0">
                    <div className="text-xs font-black text-slate-700">
                      {b.booking_code}
                    </div>
                    <div className="text-[10px] font-bold text-slate-400">
                      {b.facility_name}
                    </div>
                  </div>
                  <span
                    className={`whitespace-nowrap rounded-lg px-2 py-0.5 text-[10px] font-black ${
                      BOOKING_STATUS_CLASS[b.status] || 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {b.status_display}
                  </span>
                </Link>
              ))}
              {recent.length === 0 && (
                <div className="py-2 text-xs text-slate-400">
                  Chưa có đơn đặt sân nào.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ---- Thông tin hệ thống ---- */}
      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-black text-slate-800">
          <i className="fa-solid fa-circle-info text-emerald-600" />
          Thông tin hệ thống
        </h3>
        <div className="grid grid-cols-1 gap-3 text-xs sm:grid-cols-3">
          <div className="rounded-xl bg-slate-50 p-4">
            <span className="mb-1 block text-[10px] font-bold uppercase text-slate-400">
              Tên đăng nhập
            </span>
            <span className="font-semibold text-slate-700">{profile.username}</span>
          </div>
          <div className="rounded-xl bg-slate-50 p-4">
            <span className="mb-1 block text-[10px] font-bold uppercase text-slate-400">
              Mã định danh (UUID)
            </span>
            <span className="block truncate font-mono text-slate-600">
              {profile.id}
            </span>
          </div>
          <div className="rounded-xl bg-slate-50 p-4">
            <span className="mb-1 block text-[10px] font-bold uppercase text-slate-400">
              Ngày tham gia
            </span>
            <span className="font-semibold text-slate-700">
              {profile.date_joined
                ? new Date(profile.date_joined).toLocaleDateString('vi-VN')
                : '—'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
