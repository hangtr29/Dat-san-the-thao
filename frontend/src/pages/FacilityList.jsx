/**
 * Trang danh sách cụm sân - Tìm kiếm & lọc theo môn, giá, khoảng cách.
 */
import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { facilityApi } from '@/lib/api'
import {
  CardSkeleton,
  EmptyState,
  ErrorAlert,
  Pagination,
} from '@/components/ui'
import { FacilityCard } from '@/pages/Home'

export default function FacilityList() {
  const [searchParams, setSearchParams] = useSearchParams()

  const [data, setData] = useState({ results: [], count: 0 })
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Filter state (đồng bộ với URL)
  const keyword = searchParams.get('q') || ''
  const sport = searchParams.get('sport') || ''
  const minPrice = searchParams.get('min_price') || ''
  const maxPrice = searchParams.get('max_price') || ''
  const page = parseInt(searchParams.get('page') || '1', 10)

  const [draftKeyword, setDraftKeyword] = useState(keyword)

  const setParam = useCallback(
    (updates) => {
      const next = new URLSearchParams(searchParams)
      Object.entries(updates).forEach(([key, value]) => {
        if (value) next.set(key, value)
        else next.delete(key)
      })
      if (!('page' in updates)) next.delete('page')
      setSearchParams(next)
    },
    [searchParams, setSearchParams],
  )

  // Load categories một lần
  useEffect(() => {
    facilityApi.categories().then(setCategories).catch(() => {})
  }, [])

  // Load facilities
  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = { page }
      if (keyword) params.q = keyword
      if (sport) params.sport = sport
      if (minPrice) params.min_price = minPrice
      if (maxPrice) params.max_price = maxPrice

      const res = await facilityApi.list(params)
      setData(res)
    } catch (e) {
      setError(e.response?.data?.detail || 'Không tải được danh sách cụm sân.')
    } finally {
      setLoading(false)
    }
  }, [keyword, sport, minPrice, maxPrice, page])

  useEffect(() => {
    load()
  }, [load])

  const handleSubmitSearch = (e) => {
    e.preventDefault()
    setParam({ q: draftKeyword })
  }

  const totalPages = Math.ceil((data.count || 0) / 20)

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 sm:text-3xl">
          Tìm kiếm cụm sân
        </h1>
        <p className="mt-1.5 text-sm text-slate-500">
          {loading ? 'Đang tải...' : `Tìm thấy ${data.count} cụm sân`}
        </p>
      </div>

      {/* Filters */}
      <div className="card mb-6 p-5">
        <form
          onSubmit={handleSubmitSearch}
          className="grid gap-4 md:grid-cols-[2fr_1fr_1fr_1fr_auto]"
        >
          {/* Keyword */}
          <div>
            <label className="label">Từ khoá</label>
            <div className="relative">
              <input
                type="text"
                value={draftKeyword}
                onChange={(e) => setDraftKeyword(e.target.value)}
                placeholder="Tên cụm sân, địa chỉ..."
                className="input pl-10"
              />
              <svg
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z" />
              </svg>
            </div>
          </div>

          {/* Sport */}
          <div>
            <label className="label">Môn thể thao</label>
            <select
              value={sport}
              onChange={(e) => setParam({ sport: e.target.value })}
              className="input"
            >
              <option value="">Tất cả</option>
              {categories.map((c) => (
                <option key={c.id} value={c.slug}>
                  {c.icon_url} {c.name} ({c.court_count})
                </option>
              ))}
            </select>
          </div>

          {/* Min price */}
          <div>
            <label className="label">Giá thấp nhất</label>
            <select
              value={minPrice}
              onChange={(e) => setParam({ min_price: e.target.value })}
              className="input"
            >
              <option value="">Tất cả</option>
              <option value="50000">Từ 50.000đ</option>
              <option value="100000">Từ 100.000đ</option>
              <option value="150000">Từ 150.000đ</option>
              <option value="200000">Từ 200.000đ</option>
            </select>
          </div>

          {/* Max price */}
          <div>
            <label className="label">Giá cao nhất</label>
            <select
              value={maxPrice}
              onChange={(e) => setParam({ max_price: e.target.value })}
              className="input"
            >
              <option value="">Tất cả</option>
              <option value="100000">Dưới 100.000đ</option>
              <option value="150000">Dưới 150.000đ</option>
              <option value="200000">Dưới 200.000đ</option>
              <option value="300000">Dưới 300.000đ</option>
            </select>
          </div>

          {/* Submit */}
          <div className="flex items-end">
            <button type="submit" className="btn-primary w-full md:w-auto">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z" />
              </svg>
              Lọc
            </button>
          </div>
        </form>

        {/* Active filter chips */}
        {(keyword || sport || minPrice || maxPrice) && (
          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
            <span className="text-xs font-medium text-slate-500">Đang lọc:</span>
            {keyword && (
              <FilterChip label={`"${keyword}"`} onRemove={() => { setDraftKeyword(''); setParam({ q: '' }) }} />
            )}
            {sport && (
              <FilterChip
                label={
                  categories.find((c) => c.slug === sport)?.name || sport
                }
                onRemove={() => setParam({ sport: '' })}
              />
            )}
            {minPrice && (
              <FilterChip label={`≥ ${Number(minPrice).toLocaleString('vi-VN')}đ`} onRemove={() => setParam({ min_price: '' })} />
            )}
            {maxPrice && (
              <FilterChip label={`≤ ${Number(maxPrice).toLocaleString('vi-VN')}đ`} onRemove={() => setParam({ max_price: '' })} />
            )}
            <button
              onClick={() => { setDraftKeyword(''); setSearchParams({}) }}
              className="text-xs font-semibold text-red-600 hover:underline"
            >
              Xóa tất cả
            </button>
          </div>
        )}
      </div>

      {/* Error */}
      {error && <ErrorAlert message={error} onRetry={load} />}

      {/* Results */}
      <div className="mt-6">
        {loading ? (
          <CardSkeleton count={6} />
        ) : data.results.length === 0 ? (
          <EmptyState
            icon="🏟"
            title="Không tìm thấy cụm sân nào"
            description="Thử thay đổi từ khoá hoặc bỏ bớt bộ lọc để xem thêm kết quả."
            action={
              <button onClick={() => { setDraftKeyword(''); setSearchParams({}) }} className="btn-primary">
                Xóa bộ lọc
              </button>
            }
          />
        ) : (
          <>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {data.results.map((f) => (
                <FacilityCard key={f.id} facility={f} />
              ))}
            </div>
            <div className="mt-8">
              <Pagination
                page={page}
                totalPages={totalPages}
                onChange={(p) => {
                  setParam({ page: p === 1 ? '' : String(p) })
                  window.scrollTo({ top: 0, behavior: 'smooth' })
                }}
              />
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function FilterChip({ label, onRemove }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">
      {label}
      <button onClick={onRemove} className="hover:text-brand-900">
        ✕
      </button>
    </span>
  )
}
