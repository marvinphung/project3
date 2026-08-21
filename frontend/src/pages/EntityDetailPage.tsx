import { useParams, Link } from 'react-router'
import { useEntityTimeline } from '../api/hooks'
import type { EntityKind } from '../api/models'
import { EmptyState, LoadingSkeleton, SectionHeading } from '../components/ui'

const labels: Record<string, { title: string }> = {
  PLAYER: { title: 'Cầu thủ' },
  CLUB: { title: 'Câu lạc bộ' },
  COACH: { title: 'Huấn luyện viên' },
  COMPETITION: { title: 'Giải đấu' },
}

export default function EntityDetailPage({ kind }: { kind?: EntityKind }) {
  const { id = '' } = useParams()
  const remote = useEntityTimeline(id)

  if (remote.loading) {
    return (
      <div className="max-w-[1000px] mx-auto px-4 py-8">
        <LoadingSkeleton />
      </div>
    )
  }

  if (remote.error) {
    return (
      <div className="max-w-[1000px] mx-auto px-4 py-8">
        <EmptyState message="Không thể tải timeline entity" sub={remote.error.message} />
      </div>
    )
  }

  const timelineData = remote.data
  const entity = timelineData?.entity
  const items = timelineData?.items ?? []
  const entityType = entity?.entity_type?.toUpperCase() ?? 'CLUB'
  const typeLabel = labels[entityType]?.title ?? entityType

  function formatTimeWindow(start: string, end: string) {
    try {
      const s = new Date(start)
      const e = new Date(end)
      const date = s.toLocaleDateString('vi-VN', { timeZone: 'UTC' })
      const startTime = `${String(s.getUTCHours()).padStart(2, '0')}:00`
      const endTime = `${String(e.getUTCHours()).padStart(2, '0')}:00`
      return `${date} ${startTime} - ${endTime} (UTC)`
    } catch {
      return `${start} - ${end}`
    }
  }

  return (
    <main className="max-w-[1000px] mx-auto px-4 sm:px-6 py-8">
      {/* Entity Header */}
      <header className="mb-8 rounded-2xl border border-[#E5E7EB] bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <span className="inline-block rounded-md bg-[#78A83D]/15 px-2.5 py-1 text-xs font-bold uppercase tracking-wider text-[#78A83D]">
              {typeLabel}
            </span>
            <h1 className="mt-2 text-3xl font-extrabold text-[#111827]">
              {entity?.canonical_name || 'Chi tiết Entity'}
            </h1>
            {entity?.aliases && entity.aliases.length > 0 && (
              <p className="mt-2 text-sm text-[#6B7280]">
                <span className="font-medium text-gray-700">Biệt danh / Tên gọi khác:</span>{' '}
                {entity.aliases.join(', ')}
              </p>
            )}
          </div>
          {entity && (
            <div className="rounded-xl bg-gray-50 border border-gray-200 px-5 py-3 text-right">
              <span className="block text-2xl font-black text-[#78A83D]">
                {entity.mention_count_24h}
              </span>
              <span className="text-xs text-gray-500 font-medium">bài viết trong 24h</span>
            </div>
          )}
        </div>
      </header>

      {/* Timeline Section */}
      <section className="space-y-6">
        <SectionHeading>Timeline Diễn Biến (3 Giờ / Bucket)</SectionHeading>

        {!items.length ? (
          <EmptyState
            message="Chưa có timeline được tổng hợp"
            sub="Timeline 3 giờ sẽ xuất hiện khi có bài viết liên quan được AI xử lý."
          />
        ) : (
          <div className="relative border-l-2 border-[#78A83D]/30 ml-4 pl-6 space-y-8">
            {items.map((item) => (
              <div key={item.id} className="relative group">
                {/* Timeline dot */}
                <div className="absolute -left-[31px] top-1.5 h-4 w-4 rounded-full border-2 border-[#78A83D] bg-white group-hover:bg-[#78A83D] transition-colors" />

                <article className="rounded-xl border border-[#E5E7EB] bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
                  {/* Time Window & Article Count */}
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-3 mb-4">
                    <span className="text-xs font-semibold text-[#78A83D] tracking-wide">
                      {formatTimeWindow(item.window_start, item.window_end)}
                    </span>
                    <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                      {item.article_count} nguồn tin tổng hợp
                    </span>
                  </div>

                  {/* Short Description / Headline */}
                  <h2 className="text-xl font-bold text-gray-900 leading-snug">
                    {item.title}
                  </h2>

                  {/* Aggregated Summary */}
                  <div className="mt-3 text-sm text-gray-700 leading-relaxed whitespace-pre-line bg-gray-50/70 p-4 rounded-lg border border-gray-100">
                    {item.summary}
                  </div>

                  {/* Key Entities Badges */}
                  {item.key_entities_50?.length > 0 && (
                    <div className="mt-4 flex flex-wrap items-center gap-1.5">
                      <span className="text-xs text-gray-400 font-medium mr-1">Entities liên quan:</span>
                      {item.key_entities_50.map((kEntity, kIdx) => (
                        <span
                          key={kIdx}
                          className="rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800 border border-emerald-200"
                        >
                          {kEntity}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Source Articles Provenance */}
                  {item.source_articles?.length > 0 && (
                    <div className="mt-5 border-t border-gray-100 pt-4">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">
                        Nguồn bài viết gốc ({item.source_articles.length})
                      </h4>
                      <ul className="space-y-2">
                        {item.source_articles.map((src) => (
                          <li
                            key={src.id}
                            className="flex items-center justify-between text-xs text-gray-600 bg-white p-2 rounded border border-gray-100 hover:border-gray-300 transition"
                          >
                            <a
                              href={src.url || src.canonical_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="truncate font-medium text-blue-600 hover:underline max-w-[80%]"
                            >
                              {src.title}
                            </a>
                            <span className="shrink-0 text-gray-400 font-mono pl-2">
                              {src.source_name || src.domain_name}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </article>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}
