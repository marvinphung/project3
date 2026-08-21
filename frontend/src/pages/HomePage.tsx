import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { useTopEntities } from '../api/hooks'
import { EmptyState, LoadingSkeleton, SectionHeading } from '../components/ui'

export default function HomePage() {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const topEntities = useTopEntities(100, '24h')

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (searchQuery.trim()) {
      navigate(`/tim-kiem?q=${encodeURIComponent(searchQuery.trim())}`)
    }
  }

  const entityTypeLabels: Record<string, string> = {
    CLUB: 'CLB',
    PLAYER: 'Cầu thủ',
    COACH: 'HLV',
    COMPETITION: 'Giải đấu',
  }

  function entityPath(entity: { id: string; entity_type: string; slug: string }) {
    if (entity.entity_type === 'CLUB') return `/clb/${entity.slug}`
    if (entity.entity_type === 'PLAYER') return `/cau-thu/${entity.slug}`
    if (entity.entity_type === 'COACH') return `/hlv/${entity.slug}`
    if (entity.entity_type === 'COMPETITION') return `/competition/${entity.slug}`
    return `/entity/${entity.id}`
  }

  return (
    <div className="max-w-[1280px] mx-auto px-4 sm:px-6 py-8">
      {/* Hero & Search Banner */}
      <section className="mb-10 rounded-2xl bg-gradient-to-r from-[#1E293B] to-[#0F172A] p-8 text-white shadow-xl">
        <div className="max-w-3xl">
          <span className="inline-block rounded-full bg-[#78A83D]/20 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#78A83D]">
            Football Intelligence Timeline
          </span>
          <h1 className="mt-3 text-3xl font-extrabold sm:text-4xl text-white">
            Theo dõi diễn biến bóng đá theo từng Entity
          </h1>
          <p className="mt-2 text-sm text-gray-300 sm:text-base">
            Tổng hợp tin tức 3 giờ tự động qua AI cho từng câu lạc bộ, cầu thủ và giải đấu.
          </p>

          <form onSubmit={handleSearch} className="mt-6 flex max-w-xl gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Tìm kiếm CLB, cầu thủ, biệt danh (vd: MU, Real, Arsenal)..."
              className="min-w-0 flex-1 rounded-xl bg-white px-4 py-3 text-sm text-gray-900 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-[#78A83D]"
            />
            <button
              type="submit"
              className="rounded-xl bg-[#78A83D] px-6 py-3 text-sm font-semibold text-white transition hover:bg-[#689332]"
            >
              Tìm kiếm
            </button>
          </form>
        </div>
      </section>

      {/* Top 100 Entities in 24h */}
      <section className="mb-12">
        <div className="flex items-center justify-between mb-6">
          <SectionHeading>Top 100 Entities nổi bật (24h qua)</SectionHeading>
          <span className="text-xs text-gray-500 font-medium">Xếp hạng theo số bài viết 24h</span>
        </div>

        {topEntities.loading ? (
          <LoadingSkeleton />
        ) : topEntities.error ? (
          <EmptyState message="Không thể tải danh sách top entities" sub={topEntities.error.message} />
        ) : !topEntities.data?.length ? (
          <EmptyState
            message="Chưa có dữ liệu entity 24h"
            sub="Dữ liệu timeline sẽ hiển thị sau khi pipeline tổng hợp và xuất bản."
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {topEntities.data.map((entity, idx) => (
              <Link
                key={entity.id}
                to={entityPath(entity)}
                className="group flex items-center justify-between rounded-xl border border-[#E5E7EB] bg-white p-5 shadow-sm transition hover:border-[#78A83D] hover:shadow-md"
              >
                <div className="flex items-center gap-4 min-w-0">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gray-100 font-bold text-gray-700 group-hover:bg-[#78A83D]/10 group-hover:text-[#78A83D]">
                    #{idx + 1}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-bold text-gray-900 group-hover:text-[#78A83D]">
                        {entity.canonical_name}
                      </span>
                      <span className="shrink-0 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600">
                        {entityTypeLabels[entity.entity_type] || entity.entity_type}
                      </span>
                    </div>
                    {entity.aliases?.length > 0 && (
                      <p className="truncate text-xs text-gray-500 mt-0.5">
                        {entity.aliases.slice(0, 3).join(', ')}
                      </p>
                    )}
                  </div>
                </div>
                <div className="text-right shrink-0 pl-3">
                  <span className="block text-lg font-extrabold text-[#78A83D]">
                    {entity.mention_count_24h}
                  </span>
                  <span className="text-[11px] text-gray-400">bài viết / 24h</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
