/**
 * Trang sân yêu thích.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { favoriteApi, getErrorMessage } from '@/lib/api'
import { EmptyState, ErrorAlert, LoadingScreen } from '@/components/ui'
import { FacilityCard } from '@/pages/Home'

export default function Favorites() {
  const [facilities, setFacilities] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await favoriteApi.list()
      // API trả facility_id + facility_name; cần gọi thêm để lấy đầy đủ thông tin
      const full = await Promise.all(
        data.map(async (f) => {
          const res = await fetch(`/api/facilities/${f.facility}/`)
          return res.ok ? res.json() : null
        }),
      )
      setFacilities(full.filter(Boolean))
    } catch (e) {
      setError(getErrorMessage(e, 'Khong tai duoc san yeu thich.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 sm:text-3xl">
          Sân yêu thích
        </h1>
        <p className="mt-1.5 text-sm text-slate-500">
          {loading ? 'Đang tải...' : `${facilities.length} cụm sân đã lưu`}
        </p>
      </div>

      {error && <ErrorAlert message={error} onRetry={load} />}

      {loading ? (
        <LoadingScreen label="Đang tải sân yêu thích..." />
      ) : facilities.length === 0 ? (
        <EmptyState
          icon="♥"
          title="Chưa có sân yêu thích nào"
          description="Nhấn vào biểu tượng trái tim ở trang chi tiết cụm sân để lưu lại."
          action={
            <Link to="/facilities" className="btn-primary">
              Khám phá cụm sân
            </Link>
          }
        />
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {facilities.map((f) => (
            <FacilityCard key={f.id} facility={f} />
          ))}
        </div>
      )}
    </div>
  )
}
