import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { ApiError, getOperationsSummary, type OperationsSummary } from '../../api/client'

const metrics = [
  { key: 'source_articles_today', label: 'Bài thu thập hôm nay', color: 'text-blue-600 bg-blue-50' },
  { key: 'enrichments_validated', label: 'Đã xác thực', color: 'text-purple-600 bg-purple-50' },
  { key: 'review', label: 'Bản nháp cần duyệt', color: 'text-amber-600 bg-amber-50' },
  { key: 'publications_total', label: 'Bài đã xuất bản', color: 'text-green-600 bg-green-50' },
  { key: 'enrichments_needs_content_review', label: 'Chờ kiểm tra nội dung', color: 'text-red-600 bg-red-50' },
] as const

function displayCount(value: number) {
  return new Intl.NumberFormat('vi-VN').format(value)
}

export default function AdminDashboard() {
  const [summary, setSummary] = useState<OperationsSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    getOperationsSummary()
      .then((response) => {
        if (!active) return
        setSummary(response)
        setError(null)
      })
      .catch((requestError: unknown) => {
        if (active) setError(requestError instanceof ApiError ? requestError.message : 'Không thể tải số liệu vận hành.')
      })
    return () => { active = false }
  }, [])

  const reviewCount = (summary?.revisions_by_state.DRAFT ?? 0) + (summary?.revisions_by_state.NEEDS_REVIEW ?? 0)
  const metricValues = {
    source_articles_today: summary?.source_articles_today ?? 0,
    enrichments_validated: summary?.enrichments_validated ?? 0,
    review: reviewCount,
    publications_total: summary?.publications_total ?? 0,
    enrichments_needs_content_review: summary?.enrichments_needs_content_review ?? 0,
  }
  const pipeline = summary ? [
    ['Bài nguồn', summary.source_articles_total],
    ['Đã xác thực', summary.enrichments_validated],
    ['Chờ kiểm tra', summary.enrichments_needs_content_review],
    ['Bản nháp', Object.values(summary.revisions_by_state).reduce((total, count) => total + count, 0)],
    ['Xuất bản', summary.publications_total],
  ] : []

  return (
    <div className="p-6 max-w-[1200px]">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#111827]">Tổng quan hệ thống</h1>
        <p className="text-sm text-[#6B7280] mt-1">Số liệu đọc trực tiếp từ pipeline hiện tại</p>
      </div>
      {error && <p role="alert" className="mb-4 text-sm text-red-600">{error}</p>}

      {/* Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
        {metrics.map(m => (
          <div key={m.label} className="bg-white border border-[#E5E7EB] rounded-xl p-4">
            <div aria-hidden="true" className={`w-8 h-8 rounded-lg flex items-center justify-center mb-3 ${m.color}`}>#</div>
            <p className="text-2xl font-bold text-[#111827]">{summary ? displayCount(metricValues[m.key]) : '—'}</p>
            <p className="text-xs text-[#6B7280] mt-0.5">{m.label}</p>
          </div>
        ))}
      </div>

      {/* Pipeline */}
      <div className="bg-white border border-[#E5E7EB] rounded-xl p-5 mb-6">
        <h2 className="text-sm font-bold text-[#111827] mb-4">Pipeline xử lý</h2>
        {summary ? <div className="flex items-center gap-0 overflow-x-auto">
          {pipeline.map(([stage, count], index) => <div key={stage} className="flex items-center flex-shrink-0">
            <div className="px-3 py-2 rounded-lg text-xs font-medium bg-[#78A83D]/10 text-[#4d7621]">{stage}<span className="ml-2 text-[10px] font-semibold">{displayCount(count)}</span></div>
            {index < pipeline.length - 1 && <span className="text-[#D1D5DB] mx-1 text-sm">→</span>}
          </div>)}
        </div> : <p className="text-sm text-[#6B7280]">Đang tải trạng thái pipeline…</p>}
      </div>

      {/* Recent activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white border border-[#E5E7EB] rounded-xl p-5">
          <h2 className="text-sm font-bold text-[#111827] mb-4">Hoạt động gần đây</h2>
          <p className="text-sm text-[#6B7280]">Activity feed chưa có endpoint thật nên không hiển thị dữ liệu giả.</p>
        </div>

        <div className="bg-white border border-[#E5E7EB] rounded-xl p-5">
          <h2 className="text-sm font-bold text-[#111827] mb-4">Thao tác nhanh</h2>
          <div className="space-y-2">
            <Link to="/admin/ban-nhap" className="flex items-center justify-between p-3 bg-[#F9FAFB] rounded-lg hover:bg-[#F3F4F6] transition-colors group">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 bg-amber-100 text-amber-700 rounded text-[10px] font-bold flex items-center justify-center">{summary ? displayCount(reviewCount) : '—'}</span>
                <span className="text-sm text-[#374151]">Bản nháp cần duyệt</span>
              </div>
              <svg className="w-4 h-4 text-[#9CA3AF] group-hover:text-[#78A83D]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
