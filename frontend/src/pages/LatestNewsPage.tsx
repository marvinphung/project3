import { useState } from 'react'
import { Link } from 'react-router'
import { usePublicArticles } from '../api/hooks'
import { toArticle } from '../api/adapters'
import { EmptyState, LoadingSkeleton, NewsRow, SectionHeading, EntityChip } from '../components/ui'
import type { Article } from '../api/models'
import { entitiesFromArticles } from '../api/adapters'

const filters = ['Tất cả', 'Mới nhất', 'Nhiều nguồn', 'Chính thức']

export default function LatestNewsPage() {
  const [active, setActive] = useState('Tất cả')
  const [limit, setLimit] = useState(20)
  const remote = usePublicArticles(limit, { sort: active === 'Mới nhất' ? 'newest' : undefined })
  const displayArticles: Article[] = remote.data?.map(toArticle) ?? []
  const trendingEntities = entitiesFromArticles(remote.data ?? []).slice(0, 6)

  return (
    <div className="max-w-[1280px] mx-auto px-4 sm:px-6 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-[#111827] mb-2">Tin mới</h1>
        <p className="text-[#6B7280]">Tổng hợp tin bóng đá mới nhất từ nhiều nguồn uy tín.</p>
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-8 overflow-x-auto pb-1">
        {filters.map(f => (
          <button
            key={f}
            onClick={() => setActive(f)}
            className={`flex-shrink-0 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${active === f ? 'bg-[#78A83D] text-white' : 'bg-white border border-[#E5E7EB] text-[#374151] hover:border-[#78A83D] hover:text-[#78A83D]'}`}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_260px] gap-10">
        <section>
          <div>
            {remote.loading && <LoadingSkeleton />}
            {!remote.loading && remote.error && (
              <EmptyState
                message="Chưa thể tải tin mới"
                sub="API đang không khả dụng. Vui lòng thử lại sau."
              />
            )}
            {!remote.loading && !remote.error && displayArticles.length === 0 && (
              <EmptyState message="Chưa có bài viết được xuất bản" />
            )}
            {!remote.loading && !remote.error && displayArticles.map(a => <NewsRow key={a.id} article={a} />)}
          </div>
          <div className="mt-8 text-center">
            <button onClick={() => setLimit((current) => current + 20)} disabled={remote.loading || displayArticles.length < limit} className="inline-flex items-center gap-2 px-6 py-2.5 border border-[#E5E7EB] rounded-lg text-sm font-medium text-[#374151] hover:border-[#78A83D] hover:text-[#78A83D] transition-colors disabled:cursor-not-allowed disabled:opacity-50">
              Xem thêm tin
            </button>
          </div>
        </section>

        <aside>
          <div className="bg-white rounded-xl border border-[#E5E7EB] p-5">
            <SectionHeading>Đang được quan tâm</SectionHeading>
            <div className="flex flex-col gap-2">
              {trendingEntities.map(e => (
                <div key={e.id} className="py-1.5">
                  <EntityChip entity={e} />
                </div>
              ))}
              {!trendingEntities.length && <p className="text-sm text-[#6B7280]">Chưa có dữ liệu.</p>}
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
