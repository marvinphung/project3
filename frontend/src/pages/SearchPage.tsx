import { useState } from 'react'
import { useSearchParams } from 'react-router'

import { toArticle } from '../api/adapters'
import { usePublicArticles } from '../api/hooks'
import { EmptyState, LoadingSkeleton, NewsRow } from '../components/ui'

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const currentQuery = searchParams.get('q')?.trim() ?? ''
  const [query, setQuery] = useState(currentQuery)
  const remote = usePublicArticles(50, { query: currentQuery || undefined })

  function handleSearch(event: React.FormEvent) {
    event.preventDefault()
    const normalized = query.trim()
    setSearchParams(normalized ? { q: normalized } : {})
  }

  return (
    <main className="max-w-[1000px] mx-auto px-4 sm:px-6 py-8">
      <h1 className="mb-6 text-2xl font-bold text-[#111827]">
        {currentQuery ? `Kết quả tìm kiếm cho “${currentQuery}”` : 'Tìm kiếm'}
      </h1>
      <form onSubmit={handleSearch} className="mb-8">
        <label htmlFor="public-search" className="sr-only">Từ khóa tìm kiếm</label>
        <div className="flex max-w-2xl gap-2">
          <input id="public-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm trong bài đã xuất bản..." className="min-w-0 flex-1 rounded-xl border border-[#E5E7EB] bg-white px-4 py-3 focus:border-[#78A83D] focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30" />
          <button type="submit" className="rounded-xl bg-[#78A83D] px-5 py-3 text-sm font-semibold text-white hover:bg-[#6a9435]">Tìm</button>
        </div>
      </form>
      {!currentQuery && <EmptyState message="Nhập từ khóa để tìm bài đã xuất bản" />}
      {currentQuery && remote.loading && <LoadingSkeleton />}
      {currentQuery && remote.error && <EmptyState message="Không thể tìm kiếm" sub={remote.error.message} />}
      {currentQuery && !remote.loading && !remote.error && !remote.data?.length && <EmptyState message="Không tìm thấy kết quả phù hợp" />}
      {currentQuery && !remote.loading && !remote.error && remote.data?.map((article) => <NewsRow key={article.id} article={toArticle(article)} />)}
    </main>
  )
}
