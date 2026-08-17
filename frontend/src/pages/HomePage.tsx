import { Link } from 'react-router'
import { usePublicArticles } from '../api/hooks'
import { toArticle } from '../api/adapters'
import { EmptyState, LargeNewsCard, LoadingSkeleton, MediumNewsCard, NewsRow, SectionHeading, EntityChip } from '../components/ui'

import { entitiesFromArticles } from '../api/adapters'

export default function HomePage() {
  const remote = usePublicArticles(8)
  const liveArticles = remote.data?.map(toArticle) ?? []
  const content = liveArticles
  const trendingEntities = entitiesFromArticles(remote.data ?? []).slice(0, 8)
  const hero = content[0]
  const secondary = content.slice(1, 4)
  const latest = content.slice(0, 8)

  return (
    <div className="max-w-[1280px] mx-auto px-4 sm:px-6 py-8">
      {/* Hero */}
      <section className="mb-12">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-8">
          {remote.loading ? <LoadingSkeleton /> : remote.error ? <EmptyState message="Chưa thể tải tin nổi bật" sub={remote.error.message} /> : hero ? <LargeNewsCard article={hero} /> : <EmptyState message="Chưa có bài viết được xuất bản" sub="Dữ liệu sẽ xuất hiện sau khi Story được duyệt và publish." />}
          <div className="flex flex-col gap-5">
            {secondary.map(a => <MediumNewsCard key={a.id} article={a} />)}
          </div>
        </div>
      </section>

      {/* Latest + Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_260px] gap-10">
        {/* Main */}
        <section>
          <SectionHeading>Tin mới nhất</SectionHeading>
          <div>
            {latest.length ? latest.map(a => <NewsRow key={a.id} article={a} />) : <EmptyState message="Chưa có tin mới" />}
          </div>
          <div className="mt-8 text-center">
            <Link
              to="/tin-moi"
              className="inline-flex items-center gap-2 px-6 py-2.5 border border-[#E5E7EB] rounded-lg text-sm font-medium text-[#374151] hover:border-[#78A83D] hover:text-[#78A83D] transition-colors"
            >
              Xem thêm tin
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
            </Link>
          </div>
        </section>

        {/* Sidebar */}
        <aside className="space-y-6">
          <div className="bg-white rounded-xl border border-[#E5E7EB] p-5">
            <SectionHeading>Đang được quan tâm</SectionHeading>
            <div className="flex flex-col gap-2">
              {trendingEntities.map(e => (
                <div key={e.id} className="flex items-center gap-2 py-1.5">
                  <EntityChip entity={e} />
                </div>
              ))}
              {!trendingEntities.length && <p className="text-sm text-[#6B7280]">Chưa có entity từ bài đã xuất bản.</p>}
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
