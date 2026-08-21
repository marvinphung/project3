import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import { usePublicEntities } from '../api/hooks'
import type { EntityKind } from '../api/models'
import { EmptyState, LoadingSkeleton } from '../components/ui'

const labels: Record<EntityKind, { title: string; singular: string; route: string; limit: number }> = {
  player: { title: 'Cầu thủ', singular: 'Cầu thủ', route: 'cau-thu', limit: 50 },
  club: { title: 'Câu lạc bộ', singular: 'CLB', route: 'clb', limit: 30 },
  coach: { title: 'Huấn luyện viên', singular: 'HLV', route: 'hlv', limit: 30 },
}

export default function EntityDirectoryPage({ kind }: { kind: EntityKind }) {
  const [search, setSearch] = useState('')
  const label = labels[kind]
  const remote = usePublicEntities(kind.toUpperCase(), search.trim(), label.limit)
  const entities = useMemo(() => remote.data ?? [], [remote.data])

  return (
    <main className="max-w-[1280px] mx-auto px-4 sm:px-6 py-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-[#111827]">{label.title}</h1>
          <p className="mt-1 text-sm text-[#6B7280]">Dữ liệu entity từ các bài đã xuất bản.</p>
        </div>
        <input
          aria-label={`Tìm ${label.singular}`}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={`Tìm ${label.singular.toLocaleLowerCase('vi')}...`}
          className="w-full sm:w-72 rounded-lg border border-[#E5E7EB] bg-white px-4 py-2 text-sm focus:border-[#78A83D] focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30"
        />
      </div>
      {remote.loading && <LoadingSkeleton />}
      {!remote.loading && remote.error && <EmptyState message="Không thể tải dữ liệu" sub={remote.error.message} />}
      {!remote.loading && !remote.error && !entities.length && (
        <EmptyState message={`Chưa có ${label.title.toLocaleLowerCase('vi')}`} sub="Entity sẽ xuất hiện sau khi có bài được publish." />
      )}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {entities.map((entity) => {
          const displayName = entity.canonical_name || entity.name || 'Entity'
          const initial = displayName.charAt(0).toUpperCase() || '?'
          const count = entity.mention_count_24h ?? entity.article_count ?? 0
          return (
            <Link key={entity.id} to={`/${label.route}/${entity.slug}`} className="rounded-xl border border-[#E5E7EB] bg-white p-4 transition-colors hover:border-[#78A83D]/50">
              <div className="flex items-center gap-3">
                <span className="flex h-11 w-11 items-center justify-center rounded-full bg-[#F3F7EE] font-bold text-[#5E8430]">{initial}</span>
                <div>
                  <h2 className="font-semibold text-[#111827]">{displayName}</h2>
                  <p className="text-xs text-[#6B7280]">{count} lượt nhắc 24h</p>
                </div>
              </div>
            </Link>
          )
        })}
      </div>
    </main>
  )
}
