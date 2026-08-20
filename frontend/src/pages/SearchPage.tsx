import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useEntitySearch } from '../api/hooks'
import { EmptyState, LoadingSkeleton } from '../components/ui'

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const currentQuery = searchParams.get('q')?.trim() ?? ''
  const [query, setQuery] = useState(currentQuery)
  const remote = useEntitySearch(currentQuery)

  function handleSearch(event: React.FormEvent) {
    event.preventDefault()
    const normalized = query.trim()
    setSearchParams(normalized ? { q: normalized } : {})
  }

  const entityTypeLabels: Record<string, string> = {
    CLUB: 'CLB',
    PLAYER: 'Cầu thủ',
    COACH: 'HLV',
    COMPETITION: 'Giải đấu',
  }

  return (
    <main className="max-w-[1000px] mx-auto px-4 sm:px-6 py-8">
      <h1 className="mb-6 text-2xl font-bold text-[#111827]">
        {currentQuery ? `Kết quả tìm kiếm cho “${currentQuery}”` : 'Tìm kiếm Entity'}
      </h1>

      <form onSubmit={handleSearch} className="mb-8">
        <label htmlFor="public-search" className="sr-only">
          Từ khóa tìm kiếm
        </label>
        <div className="flex max-w-2xl gap-2">
          <input
            id="public-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Tìm theo tên CLB, cầu thủ, biệt danh (vd: MU, Los Blancos)..."
            className="min-w-0 flex-1 rounded-xl border border-[#E5E7EB] bg-white px-4 py-3 text-sm text-gray-900 focus:border-[#78A83D] focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30"
          />
          <button
            type="submit"
            className="rounded-xl bg-[#78A83D] px-6 py-3 text-sm font-semibold text-white hover:bg-[#6a9435]"
          >
            Tìm kiếm
          </button>
        </div>
      </form>

      {!currentQuery && (
        <EmptyState
          message="Nhập từ khóa để tìm kiếm"
          sub="Tìm kiếm theo tên chính thức hoặc biệt danh của câu lạc bộ, cầu thủ."
        />
      )}

      {currentQuery && remote.loading && <LoadingSkeleton />}

      {currentQuery && remote.error && (
        <EmptyState message="Không thể tìm kiếm" sub={remote.error.message} />
      )}

      {currentQuery && !remote.loading && !remote.error && !remote.data?.length && (
        <EmptyState
          message="Không tìm thấy kết quả phù hợp"
          sub={`Không tìm thấy entity nào với từ khóa "${currentQuery}".`}
        />
      )}

      {currentQuery && !remote.loading && !remote.error && Boolean(remote.data?.length) && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {remote.data?.map((entity) => (
            <Link
              key={entity.id}
              to={`/entity/${entity.id}`}
              className="group flex items-center justify-between rounded-xl border border-[#E5E7EB] bg-white p-5 shadow-sm transition hover:border-[#78A83D] hover:shadow-md"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate font-bold text-gray-900 group-hover:text-[#78A83D]">
                    {entity.canonical_name}
                  </span>
                  <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600">
                    {entityTypeLabels[entity.entity_type] || entity.entity_type}
                  </span>
                </div>
                {entity.aliases?.length > 0 && (
                  <p className="mt-1 truncate text-xs text-gray-500">
                    Biệt danh: {entity.aliases.join(', ')}
                  </p>
                )}
              </div>
              <div className="text-right shrink-0 pl-3">
                <span className="block text-base font-extrabold text-[#78A83D]">
                  {entity.mention_count_24h}
                </span>
                <span className="text-[11px] text-gray-400">bài / 24h</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </main>
  )
}

