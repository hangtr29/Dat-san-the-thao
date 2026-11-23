/**
 * Trang 404 - Không tìm thấy.
 */
import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center px-4 py-20 text-center">
      <div className="text-8xl font-black text-brand-600">404</div>
      <h1 className="mt-4 text-2xl font-bold text-slate-900">
        Không tìm thấy trang bạn yêu cầu
      </h1>
      <p className="mt-2.5 text-sm text-slate-500">
        Trang bạn truy cập không tồn tại, đã bị xóa hoặc đã chuyển sang địa chỉ khác.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Link to="/" className="btn-primary">
          Về trang chủ
        </Link>
        <Link to="/facilities" className="btn-secondary">
          Tìm cụm sân
        </Link>
      </div>
    </div>
  )
}
