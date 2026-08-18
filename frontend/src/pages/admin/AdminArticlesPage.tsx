import { FormEvent, useEffect, useState } from 'react'
import { ApiError, listSourceArticles, type SourceArticle } from '../../api/client'

const PAGE_SIZE = 50

const statusLabels: Record<string, { label: string; className: string }> = {
  SUCCESS: { label: 'Đã xử lý', className: 'bg-emerald-50 text-emerald-700' },
  FAILED: { label: 'Lỗi', className: 'bg-red-50 text-red-700' },
  PENDING: { label: 'Chờ xử lý', className: 'bg-amber-50 text-amber-700' },
}

function sourceName(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return 'Không xác định'
  }
}

function StatusChip({ status }: { status: string }) {
  const display = statusLabels[status] ?? { label: status, className: 'bg-slate-100 text-slate-700' }
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${display.className}`}>{display.label}</span>
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export default function AdminArticlesPage() {
  const [articles, setArticles] = useState<SourceArticle[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [searchInput, setSearchInput] = useState('')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    listSourceArticles({ limit: PAGE_SIZE, offset, query: query || undefined })
      .then((response) => {
        if (!active) return
        setArticles(response.items)
        setTotal(response.total ?? 0)
      })
      .catch((reason: unknown) => {
        if (!active) return
        setArticles([])
        setTotal(0)
        setError(reason instanceof ApiError ? reason.message : 'Không thể tải bài nguồn')
      })
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [offset, query])

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setOffset(0)
    setQuery(searchInput.trim())
  }

  const pageStart = total === 0 ? 0 : offset + 1
  const pageEnd = Math.min(offset + articles.length, total)

  return (
    <div className="mx-auto max-w-[1440px] p-4 sm:p-6">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-medium text-[#78A83D]">Kho dữ liệu thu thập</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-[#111827]">Bài viết nguồn</h1>
          <p className="mt-1 text-sm text-[#6B7280]">
            {loading ? 'Đang tải số lượng bài…' : `${total.toLocaleString('vi-VN')} bài trong kho`}
          </p>
        </div>
        <form onSubmit={submitSearch} className="flex w-full gap-2 sm:w-auto">
          <label className="sr-only" htmlFor="source-article-search">Tìm bài nguồn</label>
          <input
            id="source-article-search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Tìm theo tiêu đề hoặc URL"
            className="min-w-0 flex-1 rounded-lg border border-[#D9DEE5] bg-white px-3 py-2 text-sm text-[#111827] outline-none transition focus:border-[#78A83D] focus:ring-2 focus:ring-[#78A83D]/20 sm:w-72"
          />
          <button type="submit" className="rounded-lg bg-[#78A83D] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#668f34] active:translate-y-px">
            Tìm
          </button>
        </form>
      </div>

      {error && <p role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}

      <div className="overflow-hidden rounded-xl border border-[#E3E7EC] bg-white">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="border-b border-[#E3E7EC] bg-[#F8FAFC] text-left text-xs font-semibold uppercase tracking-wider text-[#667085]">
              <tr>
                <th className="px-5 py-3">Tiêu đề gốc</th>
                <th className="px-4 py-3">Nguồn</th>
                <th className="px-4 py-3">Thu thập lúc</th>
                <th className="px-4 py-3">Trạng thái</th>
                <th className="px-4 py-3">Trùng lặp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EEF1F4]">
              {loading && Array.from({ length: 8 }, (_, index) => (
                <tr key={index} aria-busy="true">
                  <td className="px-5 py-4"><div className="skeleton h-4 w-4/5" /></td>
                  <td className="px-4 py-4"><div className="skeleton h-4 w-24" /></td>
                  <td className="px-4 py-4"><div className="skeleton h-4 w-28" /></td>
                  <td className="px-4 py-4"><div className="skeleton h-5 w-20" /></td>
                  <td className="px-4 py-4"><div className="skeleton h-4 w-12" /></td>
                </tr>
              ))}
              {!loading && articles.map((article) => (
                <tr key={article.id} className="transition-colors hover:bg-[#FAFCF8]">
                  <td className="max-w-[520px] px-5 py-3.5">
                    <a href={article.source_url} target="_blank" rel="noreferrer" className="line-clamp-2 font-medium leading-snug text-[#172033] hover:text-[#5F8C2F] hover:underline">
                      {article.title}
                    </a>
                  </td>
                  <td className="px-4 py-3.5 text-[#475467]">{sourceName(article.source_url)}</td>
                  <td className="whitespace-nowrap px-4 py-3.5 text-[#667085]">{formatDate(article.collected_at)}</td>
                  <td className="px-4 py-3.5"><StatusChip status={article.extraction_status} /></td>
                  <td className="px-4 py-3.5 text-xs font-medium text-[#667085]">{article.duplicate_type === 'NONE' ? 'Không' : 'Có'}</td>
                </tr>
              ))}
              {!loading && !error && articles.length === 0 && (
                <tr><td colSpan={5} className="px-5 py-16 text-center text-[#667085]">Không tìm thấy bài nguồn phù hợp.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="flex flex-col gap-3 border-t border-[#E3E7EC] px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-[#667085]">Hiển thị {pageStart.toLocaleString('vi-VN')}–{pageEnd.toLocaleString('vi-VN')} trong {total.toLocaleString('vi-VN')} bài</p>
          <div className="flex gap-2">
            <button type="button" onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} disabled={offset === 0 || loading} className="rounded-md border border-[#D9DEE5] px-3 py-1.5 text-sm font-medium text-[#475467] transition hover:bg-[#F8FAFC] disabled:cursor-not-allowed disabled:opacity-40">Trước</button>
            <button type="button" onClick={() => setOffset(offset + PAGE_SIZE)} disabled={loading || offset + articles.length >= total} className="rounded-md border border-[#D9DEE5] px-3 py-1.5 text-sm font-medium text-[#475467] transition hover:bg-[#F8FAFC] disabled:cursor-not-allowed disabled:opacity-40">Sau</button>
          </div>
        </div>
      </div>
    </div>
  )
}
