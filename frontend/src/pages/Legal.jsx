/**
 * Các trang tĩnh: Điều khoản đặt sân, Chính sách hoàn tiền & huỷ lịch,
 * Tra cứu mã đơn đặt sân.
 *
 * Nội dung đồng bộ với bản Django gốc:
 * - templates/bookings/booking_terms.html
 * - templates/bookings/booking_refund_policy.html
 * - templates/bookings/booking_lookup.html
 */
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { bookingApi, getErrorMessage } from '@/lib/api'

// ---------------------------------------------------------------------------
// ĐIỀU KHOẢN ĐẶT SÂN
// ---------------------------------------------------------------------------
export function BookingTermsPage() {
  const sections = [
    {
      title: 'Phạm vi áp dụng',
      body: (
        <>
          Điều khoản này áp dụng cho mọi giao dịch đặt khung giờ thi đấu tại các cụm sân thể
          thao (Cầu lông, Pickleball, Bóng bàn) đang hoạt động trên nền tảng SportBook. Khi bạn
          bấm <strong>“Xác nhận &amp; Thanh toán”</strong>, đồng thời chọn khung giờ và chuyển
          khoản, bạn được xem là đã đọc, hiểu và đồng ý với toàn bộ nội dung dưới đây.
        </>
      ),
    },
    {
      title: 'Cơ chế giữ chỗ tạm thời (10 phút)',
      list: [
        <>
          Khi bạn chọn khung giờ, hệ thống <strong>giữ chỗ (lock)</strong> khung giờ đó trong{' '}
          <strong>10 phút</strong> để bạn hoàn tất thanh toán.
        </>,
        <>
          Trong 10 phút đó, khung giờ không thể được người khác đặt — đảm bảo công bằng cho mọi
          khách hàng.
        </>,
        <>
          Nếu hết 10 phút mà bạn chưa nộp ảnh bill, đơn sẽ tự động hủy và khung giờ được giải
          phóng về trạng thái khả dụng.
        </>,
        <>
          Hệ thống sẽ <strong>không tự động chuyển hướng</strong> bạn ra khỏi trang thanh toán
          nếu bạn đang tải ảnh bill lên.
        </>,
      ],
    },
    {
      title: 'Thanh toán trực tiếp — Không giữ tiền trung gian',
      body: (
        <>
          SportBook là <strong>nền tảng trung gian kết nối</strong>, không giữ tiền trung gian.
          Tiền được chuyển <strong>trực tiếp</strong> từ tài khoản ngân hàng của bạn đến tài
          khoản của chủ sân thông qua mã VietQR (chuẩn Napas 247).
        </>
      ),
      list: [
        <>
          Mã QR hiển thị luôn kèm <strong>số tiền</strong> và{' '}
          <strong>nội dung chuyển khoản</strong> (mã đơn đặt) — bạn không cần tự nhập tay.
        </>,
        <>
          Mỗi đơn đặt chỉ được thuộc về <strong>một cụm sân</strong>. Hệ thống sẽ từ chối đơn
          có khung giờ từ nhiều cụm sân khác nhau nhằm tránh việc tiền về nhầm chủ sân.
        </>,
        <>
          Chủ sân có trách nhiệm kiểm tra ảnh bill và xác nhận đơn. Thời gian xử lý phụ thuộc vào
          chủ sân (khuyến nghị trong vòng 24 giờ).
        </>,
      ],
    },
    {
      title: 'Quyền & Trách nhiệm của Khách Hàng',
      list: [
        <>
          Cung cấp thông tin <strong>chính xác</strong>: họ tên và số điện thoại liên hệ để chủ
          sân gọi xác nhận khi cần.
        </>,
        <>
          Ảnh bill phải là ảnh chụp màn hình biên lai <strong>thật</strong>, hiển thị rõ số
          tiền, số tài khoản và nội dung chuyển khoản.
        </>,
        <>
          Không sử dụng ảnh bill đã sửa, sao chép từ đơn khác, hoặc ảnh không liên quan — đơn sẽ
          bị từ chối và khung giờ được giải phóng.
        </>,
        <>Tuân thủ quy định của cụm sân về giờ chơi, trang phục, thiết bị và luật chơi nội bộ.</>,
        <>Chịu trách nhiệm về thiệt hại do hành vi của mình gây ra tại cơ sở.</>,
      ],
    },
    {
      title: 'Đánh giá & Xác thực Chủ Sân',
      body: (
        <>
          Mỗi cụm sân trên nền tảng đều được đánh dấu <strong>“Tích xanh”</strong> sau khi chủ
          sân hoàn tất hồ sơ xác minh (KYC). Bạn nên ưu tiên những cụm sân đã tích xanh. Chỉ
          khách hàng có đơn đặt được chủ sân <strong>xác nhận thành công</strong> mới được đánh
          giá (mỗi đơn 1 lần — chống spam).
        </>
      ),
    },
    {
      title: 'Giải quyết Tranh Chấp',
      body: (
        <>
          Mỗi phiếu đặt sân đều hiển thị rõ <strong>Hotline/Zalo</strong> của chủ sân để hai
          bên liên hệ trực tiếp giải quyết các vấn đề phát sinh tại chỗ. Nếu cần hỗ trợ từ nền
          tảng, vui lòng liên hệ Ban quản trị qua Hotline 1900-xxxx.
        </>
      ),
    },
  ]

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-8 rounded-3xl bg-gradient-to-r from-[#032614] via-[#0b6b3a] to-[#04331b] p-7 text-white shadow-xl sm:p-9">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-2xl bg-white/15 text-2xl">
            <i className="fa-solid fa-file-contract" />
          </div>
          <div>
            <h1 className="text-xl font-black tracking-wide sm:text-2xl">
              ĐIỀU KHOẢN ĐẶT SÂN
            </h1>
            <p className="mt-1 text-xs font-semibold text-emerald-300">
              Nền tảng SportBook — Cập nhật lần cuối: 19/11/2026
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-7 rounded-3xl border border-slate-200 bg-white p-6 text-sm leading-relaxed text-slate-700 shadow-sm sm:p-9">
        {sections.map((s, i) => (
          <section key={s.title}>
            <h2 className="mb-3 flex items-center gap-2.5 text-base font-black uppercase tracking-wide text-[#04331b]">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100 text-xs font-black text-[#0b6b3a]">
                {i + 1}
              </span>
              {s.title}
            </h2>
            {s.body && <p>{s.body}</p>}
            {s.list && (
              <ul className="list-inside list-disc space-y-2 marker:text-emerald-500">
                {s.list.map((li, j) => (
                  <li key={j}>{li}</li>
                ))}
              </ul>
            )}
          </section>
        ))}

        <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
          <h2 className="mb-2 text-sm font-black uppercase tracking-wide text-emerald-900">
            Liên kết liên quan
          </h2>
          <p className="text-xs text-emerald-800">
            Xem thêm{' '}
            <Link to="/refund-policy" className="font-black underline">
              Chính sách hoàn tiền &amp; huỷ lịch
            </Link>{' '}
            hoặc quay lại{' '}
            <Link to="/facilities" className="font-black underline">
              trang đặt sân
            </Link>
            .
          </p>
        </section>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// CHÍNH SÁCH HOÀN TIỀN & HUỶ LỊCH
// ---------------------------------------------------------------------------
const REFUND_ROWS = [
  {
    situation: 'Huỷ trước khi thanh toán',
    result: 'Hoàn 100%',
    resultClass: 'bg-emerald-100 text-emerald-800',
    time: 'Trong 10 phút giữ chỗ',
    zebra: false,
  },
  {
    situation: 'Chủ sân từ chối đơn (bill sai)',
    result: 'Hoàn 100%',
    resultClass: 'bg-emerald-100 text-emerald-800',
    time: 'Ngay khi chủ sân từ chối',
    zebra: true,
  },
  {
    situation: 'Khách vãng lai (không có tài khoản)',
    result: 'Hoàn 100%',
    resultClass: 'bg-emerald-100 text-emerald-800',
    time: 'Cần tra mã đơn hoặc liên hệ chủ sân',
    zebra: false,
  },
  {
    situation: 'Huỷ sau khi chủ sân xác nhận',
    result: 'Theo thỏa thuận',
    resultClass: 'bg-amber-100 text-amber-800',
    time: 'Liên hệ trực tiếp chủ sân',
    zebra: true,
  },
  {
    situation: 'Khách vắng mặt / không thể chơi',
    result: 'Không hoàn',
    resultClass: 'bg-rose-100 text-rose-800',
    time: 'Sau mốc xác nhận của chủ sân',
    zebra: false,
  },
]

export function RefundPolicyPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-8 rounded-3xl bg-gradient-to-r from-[#7a2e0e] via-[#c2410c] to-[#7a2e0e] p-7 text-white shadow-xl sm:p-9">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-2xl bg-white/15 text-2xl">
            <i className="fa-solid fa-rotate-left" />
          </div>
          <div>
            <h1 className="text-xl font-black tracking-wide sm:text-2xl">
              CHÍNH SÁCH HOÀN TIỀN &amp; HUỶ LỊCH
            </h1>
            <p className="mt-1 text-xs font-semibold text-orange-200">
              Nền tảng SportBook — Cập nhật lần cuối: 19/11/2026
            </p>
          </div>
        </div>
      </div>

      {/* Bảng tóm tắt nhanh */}
      <div className="mb-8 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 bg-slate-50 px-5 py-3">
          <h2 className="text-xs font-black uppercase tracking-wider text-slate-700">
            Tóm tắt nhanh
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs sm:text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-5 py-3 text-left font-black uppercase tracking-wide">
                  Tình huống
                </th>
                <th className="px-5 py-3 text-left font-black uppercase tracking-wide">
                  Kết quả
                </th>
                <th className="px-5 py-3 text-left font-black uppercase tracking-wide">
                  Thời điểm áp dụng
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {REFUND_ROWS.map((row) => (
                <tr key={row.situation} className={row.zebra ? 'bg-orange-50/40' : ''}>
                  <td className="px-5 py-3.5 font-bold text-slate-800">{row.situation}</td>
                  <td className="px-5 py-3.5">
                    <span
                      className={`rounded-full px-2.5 py-1 font-bold ${row.resultClass}`}
                    >
                      {row.result}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-slate-600">{row.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="space-y-7 rounded-3xl border border-slate-200 bg-white p-6 text-sm leading-relaxed text-slate-700 shadow-sm sm:p-9">
        <section>
          <h2 className="mb-3 flex items-center gap-2.5 text-base font-black uppercase tracking-wide text-[#7a2e0e]">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-100 text-xs font-black text-[#c2410c]">
              1
            </span>
            Nguyên tắc chung
          </h2>
          <p>
            Vì SportBook <strong>không giữ tiền trung gian</strong>, tiền của bạn được chuyển
            thẳng từ ngân hàng của bạn đến ngân hàng của chủ sân. Vì vậy việc hoàn tiền phụ thuộc
            vào <strong>quyết định của chủ sân</strong> và thời điểm bạn yêu cầu.
          </p>
          <p className="mt-2">
            Chính sách này ưu tiên bảo vệ quyền lợi khách hàng trong các trường hợp do{' '}
            <strong>lỗi của hệ thống hoặc của chủ sân</strong>, đồng thời giữ sân ổn định cho
            cả hai bên.
          </p>
        </section>

        <section>
          <h2 className="mb-3 flex items-center gap-2.5 text-base font-black uppercase tracking-wide text-[#7a2e0e]">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-100 text-xs font-black text-[#c2410c]">
              2
            </span>
            Hoàn tiền 100% (không điều kiện)
          </h2>
          <ul className="list-inside list-disc space-y-2.5 marker:text-orange-400">
            <li>
              <strong>Huỷ trong 10 phút giữ chỗ:</strong> bạn huỷ trước khi chuyển khoản
              hoặc trước khi nộp bill. Khung giờ được giải phóng ngay lập tức.
            </li>
            <li>
              <strong>Chủ sân từ chối đơn:</strong> khi chủ sân không nhận được tiền, ảnh bill
              không hợp lệ hoặc không thể phục vụ. Khung giờ được giải phóng và bạn được hoàn
              lại toàn bộ số tiền.
            </li>
            <li>
              <strong>Hệ thống tự hủy đơn quá hạn:</strong> đơn không được nộp bill trong 10
              phút sẽ bị hủy và khung giờ trở lại trạng thái khả dụng.
            </li>
            <li>
              <strong>Sự cố kỹ thuật:</strong> nếu bạn đã chuyển khoản thành công nhưng hệ
              thống ghi nhận lỗi, liên hệ Ban quản trị — chúng tôi hỗ trợ trực tiếp với chủ
              sân.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="mb-3 flex items-center gap-2.5 text-base font-black uppercase tracking-wide text-[#7a2e0e]">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-100 text-xs font-black text-[#c2410c]">
              3
            </span>
            Huỷ lịch sau khi chủ sân đã xác nhận
          </h2>
          <p>
            Khi chủ sân đã xác nhận đơn (<strong>CONFIRMED</strong>), khung giờ được cam kết và
            không thể bán lại cho khách khác. Do đó:
          </p>
          <ul className="mt-3 list-inside list-disc space-y-2.5 marker:text-orange-400">
            <li>
              Việc hoàn tiền sẽ do <strong>chủ sân và khách hàng thỏa thuận</strong> dựa trên
              tình hình thực tế.
            </li>
            <li>
              SportBook khuyến nghị liên hệ Hotline/Zalo của chủ sân (hiển thị ngay trên phiếu
              đặt) để thống nhất trước.
            </li>
            <li>
              Trường hợp chủ sân <strong>không liên lạc được</strong> hoặc từ chối thỏa thuận,
              bạn có quyền gửi khiếu nại lên Ban quản trị để được hỗ trợ.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="mb-3 flex items-center gap-2.5 text-base font-black uppercase tracking-wide text-[#7a2e0e]">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-100 text-xs font-black text-[#c2410c]">
              4
            </span>
            Không hoàn tiền
          </h2>
          <ul className="list-inside list-disc space-y-2.5 marker:text-rose-400">
            <li>
              Khách đã chuyển khoản và nộp bill nhưng <strong>không xuất hiện</strong> tại sân
              đúng giờ (không thông báo trước).
            </li>
            <li>Khách vắng mặt quá 15 phút kể từ giờ bắt đầu mà không có thông báo cho chủ sân.</li>
            <li>
              Khách hủy lịch liên tục nhiều lần mà không có lý do chính đáng, gây ảnh hưởng doanh
              thu của cụm sân.
            </li>
            <li>
              Trường hợp gian lận: ảnh bill giả, bill của đơn khác, chuyển khoản không đúng số
              tiền.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="mb-3 flex items-center gap-2.5 text-base font-black uppercase tracking-wide text-[#7a2e0e]">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-100 text-xs font-black text-[#c2410c]">
              5
            </span>
            Quy trình yêu cầu hoàn tiền
          </h2>
          <ol className="list-inside list-decimal space-y-3 marker:font-black marker:text-[#c2410c]">
            <li>
              <strong>Bước 1:</strong> Liên hệ chủ sân qua Hotline/Zalo hiển thị trên phiếu đặt
              sân.
            </li>
            <li>
              <strong>Bước 2:</strong> Cung cấp <strong>mã đơn (mã bắt đầu bằng BK)</strong> và
              ảnh bill đã chuyển khoản.
            </li>
            <li>
              <strong>Bước 3:</strong> Chủ sân kiểm tra và chuyển khoản hoàn lại trực tiếp vào
              tài khoản của bạn.
            </li>
            <li>
              <strong>Bước 4:</strong> Nếu không thỏa thuận được, gửi khiếu nại lên Ban quản trị
              SportBook kèm mã đơn và ảnh bill để được xử lý.
            </li>
          </ol>
        </section>

        <section>
          <h2 className="mb-3 flex items-center gap-2.5 text-base font-black uppercase tracking-wide text-[#7a2e0e]">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-100 text-xs font-black text-[#c2410c]">
              6
            </span>
            Quyền riêng tư &amp; Bảo mật thông tin
          </h2>
          <ul className="list-inside list-disc space-y-2.5 marker:text-orange-400">
            <li>
              Thông tin tra cứu đơn bằng <strong>số điện thoại</strong> chỉ dành cho{' '}
              <strong>chính chủ tài khoản</strong> đã đăng nhập.
            </li>
            <li>
              Khách vãng lai tra cứu bằng <strong>mã đơn (BK...)</strong> — mã ngẫu nhiên 8 ký
              tự, không thể dò tuần tự.
            </li>
            <li>
              Ảnh bill chuyển khoản được lưu trong hệ thống để chủ sân đối soát, không chia sẻ
              cho bên thứ ba.
            </li>
          </ul>
        </section>

        <section className="rounded-2xl border border-orange-200 bg-orange-50 p-5">
          <h2 className="mb-2 text-sm font-black uppercase tracking-wide text-orange-900">
            Liên kết liên quan
          </h2>
          <p className="text-xs text-orange-800">
            Xem thêm{' '}
            <Link to="/terms" className="font-black underline">
              Điều khoản đặt sân
            </Link>{' '}
            hoặc quay lại{' '}
            <Link to="/facilities" className="font-black underline">
              trang đặt sân
            </Link>
            .
          </p>
        </section>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// TRA CỨU MÃ ĐƠN ĐẶT SÂN
// ---------------------------------------------------------------------------
export function BookingLookupPage() {
  const [code, setCode] = useState('')
  const [booking, setBooking] = useState(null)
  const [error, setError] = useState('')
  const [searched, setSearched] = useState(false)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    const value = code.trim()
    if (!value) return
    setLoading(true)
    setError('')
    setBooking(null)
    try {
      const data = await bookingApi.lookup(value.toUpperCase())
      setBooking(data)
      setSearched(true)
    } catch (err) {
      setError(getErrorMessage(err, 'Không tìm thấy đơn đặt nào.'))
      setSearched(true)
    } finally {
      setLoading(false)
    }
  }

  const statusClass = {
    CONFIRMED: 'bg-emerald-100 text-emerald-800',
    WAITING_APPROVAL: 'bg-blue-100 text-blue-800',
  }

  return (
    <div className="mx-auto max-w-xl px-4 py-12 sm:px-6 lg:px-8">
      <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-2xl text-emerald-600 shadow-inner">
          <i className="fa-solid fa-magnifying-glass" />
        </div>
        <h1 className="text-2xl font-black text-slate-800">Tra Cứu Đơn Đặt Sân</h1>
        <p className="mx-auto mt-1 max-w-sm text-xs text-slate-500">
          Nhập mã đơn đặt (Ví dụ:{' '}
          <code className="rounded bg-slate-100 px-1 py-0.5 font-bold text-slate-700">BK...</code>)
          để kiểm tra trạng thái duyệt bill và thông tin sân.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 flex gap-2">
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Nhập mã đơn"
            required
            className="flex-1 rounded-xl border border-slate-300 px-4 py-3 font-mono text-sm font-bold uppercase text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded-xl bg-emerald-600 px-6 py-3 text-sm font-bold text-white shadow-md shadow-emerald-200 transition hover:bg-emerald-700 disabled:opacity-60"
          >
            {loading ? 'Đang tra...' : 'Tra Cứu'}
          </button>
        </form>

        {searched && (
          <div className="mt-8 space-y-3 border-t border-slate-100 pt-8 text-left">
            {error && (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center">
                <i className="fa-solid fa-circle-exclamation mb-2 text-2xl text-rose-500" />
                <h4 className="text-sm font-bold text-rose-800">
                  Không tìm thấy đơn đặt nào với "{code}"
                </h4>
                <p className="mt-1 text-xs text-rose-600">
                  Vui lòng kiểm tra lại chính xác mã đơn bạn đã đặt sân.
                </p>
              </div>
            )}

            {booking && (
              <div className="space-y-3 rounded-2xl border border-emerald-200 bg-emerald-50/50 p-5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase text-slate-500">
                    Mã:{' '}
                    <strong className="font-mono text-slate-800">
                      {booking.booking_code}
                    </strong>
                  </span>
                  <span
                    className={`rounded-full px-2.5 py-1 text-xs font-bold ${
                      statusClass[booking.status] || 'bg-slate-100 text-slate-700'
                    }`}
                  >
                    {booking.status_display}
                  </span>
                </div>
                <div className="text-xs text-slate-600">
                  Cụm sân: <strong>{booking.facility_name || 'Không xác định'}</strong>
                </div>
                {booking.facility_hotline && (
                  <div className="text-xs text-slate-600">
                    Hotline/Zalo: <strong>{booking.facility_hotline}</strong>
                  </div>
                )}
                <div className="text-xs text-slate-600">
                  Tổng thanh toán:{' '}
                  <strong className="text-sm text-emerald-700">
                    {Number(booking.total_amount).toLocaleString('vi-VN')} đ
                  </strong>
                </div>
                <button
                  type="button"
                  onClick={() => navigate('/bookings')}
                  className="block w-full rounded-xl bg-emerald-600 py-2.5 text-center text-xs font-bold text-white shadow-sm transition hover:bg-emerald-700"
                >
                  Xem Phiếu Đặt Sân Chi Tiết
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
