import { useState } from 'react'
import { Link } from 'react-router'
import { articles } from '../data/mock'
import { NewsRow, SectionHeading, StatusBadge, EntityChip } from '../components/ui'

const filters = ['Tất cả', 'Mới nhất', 'Nhiều nguồn', 'Chính thức']

const trendingEntities = [
  { type: 'club' as const, id: 'arsenal', name: 'Arsenal' },
  { type: 'player' as const, id: 'mbappe', name: 'Kylian Mbappé' },
  { type: 'club' as const, id: 'real-madrid', name: 'Real Madrid' },
  { type: 'coach' as const, id: 'arteta', name: 'Mikel Arteta' },
]

export default function LatestNewsPage() {
  const [active, setActive] = useState('Tất cả')

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
            {articles.map(a => <NewsRow key={a.id} article={a} />)}
          </div>
          <div className="mt-8 text-center">
            <button className="inline-flex items-center gap-2 px-6 py-2.5 border border-[#E5E7EB] rounded-lg text-sm font-medium text-[#374151] hover:border-[#78A83D] hover:text-[#78A83D] transition-colors">
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
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
