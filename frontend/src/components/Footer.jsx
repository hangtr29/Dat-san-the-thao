/**
 * Footer - đồng bộ với bản Django gốc (templates/base.html).
 *
 * 4 cột: Logo + mô tả | Danh mục môn thể thao | Chính sách & hỗ trợ | Đề cương OOP
 */
import { Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

const SPORT_LINKS = [
  { to: '/facilities?sport=cau-long', icon: '🏸', label: 'Sân Cầu Lông' },
  { to: '/facilities?sport=pickleball', icon: '🏓', label: 'Sân Pickleball' },
  { to: '/facilities?sport=bong-ban', icon: '🏓', label: 'Sân Bóng Bàn' },
]

const POLICY_LINKS = [
  { to: '/terms', label: 'Điều khoản đặt sân' },
  { to: '/refund-policy', label: 'Chính sách hoàn tiền & huỷ lịch' },
  { to: '/lookup', label: 'Tra cứu mã đơn đặt' },
  { to: '/favorites', label: 'Sân yêu thích' },
]

export default function Footer() {
  const { isAuthenticated } = useAuth()

  return (
    <>
      <footer className="mt-auto w-full border-t border-slate-800 bg-slate-900 py-10 text-slate-400 sm:py-12">
        <div className="mx-auto w-full max-w-7xl px-4 sm:px-8 lg:px-12">
          <div className="grid grid-cols-1 items-start gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {/* Logo + mô tả */}
            <div className="min-w-0">
              <div className="mb-3 flex items-center space-x-2">
                <img
                  src="/logo.png"
                  alt="SportBook"
                  className="logo-glow-effect h-12 w-auto max-w-full object-contain sm:h-14"
                />
              </div>
              <p className="max-w-xs text-xs leading-relaxed text-slate-400 sm:max-w-md">
                SportBook - Đặt Sân Nhanh Chóng. Nền tảng kết nối trực tiếp Khách hàng &amp;
                Chủ sân Cầu lông, Pickleball, Bóng bàn. Chuyển khoản VietQR không giữ tiền
                trung gian.
              </p>
            </div>

            {/* Danh mục môn thể thao */}
            <div className="min-w-0">
              <h4 className="mb-3 text-xs font-black uppercase tracking-wider text-white">
                Danh Mục Môn Thể Thao
              </h4>
              <ul className="space-y-2 text-xs font-semibold">
                {SPORT_LINKS.map((link) => (
                  <li key={link.to}>
                    <Link to={link.to} className="hover:text-emerald-400">
                      {link.icon} {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Chính sách & hỗ trợ */}
            <div className="min-w-0">
              <h4 className="mb-3 text-xs font-black uppercase tracking-wider text-white">
                Chính sách &amp; Hỗ trợ
              </h4>
              <ul className="space-y-2 text-xs font-semibold">
                {POLICY_LINKS.map((link) => (
                  <li key={link.to}>
                    <Link to={link.to} className="hover:text-emerald-400">
                      {link.label}
                    </Link>
                  </li>
                ))}
                {!isAuthenticated && (
                  <li>
                    <Link to="/login" className="hover:text-emerald-400">
                      Đăng nhập / Đăng ký
                    </Link>
                  </li>
                )}
              </ul>
            </div>

            {/* Đề cương kiến trúc OOP */}
            <div className="min-w-0">
              <h4 className="mb-3 text-xs font-black uppercase tracking-wider text-white">
                Đề Cương Kiến Trúc OOP
              </h4>
              <p className="text-xs font-bold text-slate-300">
                Phát triển ứng dụng Hướng Đối Tượng (HTTT14)
              </p>
              <p className="mt-1 text-xs text-slate-400">
                Tech Stack: Python / Django / ReactJS / Tailwind CSS
              </p>
            </div>
          </div>

          <div className="mt-8 border-t border-slate-800 pt-6 text-center text-xs text-slate-500">
            &copy; 2026 SportBook - Đặt Sân Nhanh Chóng. All rights reserved.
          </div>
        </div>
      </footer>

      {/* Mobile Bottom Navigation Bar */}
      <nav className="fixed inset-x-0 bottom-0 z-50 flex items-center justify-around border-t border-slate-200 bg-white px-4 py-2 text-center text-[10px] font-bold shadow-2xl md:hidden">
        <Link to="/facilities" className="flex flex-col items-center text-[#0b6b3a]">
          <i className="fa-solid fa-house mb-0.5 text-base" />
          <span>Trang chủ</span>
        </Link>
        <Link to="/map" className="flex flex-col items-center text-slate-400 hover:text-slate-700">
          <i className="fa-solid fa-map-location-dot mb-0.5 text-base" />
          <span>Bản đồ</span>
        </Link>
        {/* Central Floating Button */}
        <Link
          to="/"
          className="-mt-6 flex h-12 w-12 items-center justify-center overflow-hidden rounded-full border-4 border-white bg-slate-900 p-1 shadow-xl"
        >
          <img
            src="/logo-icon.png"
            alt="SportBook"
            className="h-full w-full object-contain"
          />
        </Link>
        <Link to="/bookings" className="flex flex-col items-center text-slate-400 hover:text-slate-700">
          <i className="fa-solid fa-fire mb-0.5 text-base" />
          <span>Nổi bật</span>
        </Link>
        <Link
          to={isAuthenticated ? '/profile' : '/login'}
          className="flex flex-col items-center text-slate-400 hover:text-slate-700"
        >
          <i className="fa-solid fa-user mb-0.5 text-base" />
          <span>Tài khoản</span>
        </Link>
      </nav>
    </>
  )
}
