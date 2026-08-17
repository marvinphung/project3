import { useParams } from 'react-router'

import { toArticle } from '../api/adapters'
import { usePublicArticles, usePublicEntity } from '../api/hooks'
import type { EntityKind } from '../api/models'
import StoryTimeline from '../components/StoryTimeline'
import { EmptyState, LoadingSkeleton, NewsRow, SectionHeading } from '../components/ui'

const labels: Record<EntityKind, { title: string; apiType: string }> = {
  player: { title: 'Cầu thủ', apiType: 'PLAYER' },
  club: { title: 'Câu lạc bộ', apiType: 'CLUB' },
  coach: { title: 'Huấn luyện viên', apiType: 'COACH' },
}

export default function EntityDetailPage({ kind }: { kind: EntityKind }) {
  const { id = '' } = useParams()
  const label = labels[kind]
  const remote = usePublicEntity(label.apiType, id)
  const articles = usePublicArticles(100, { entityType: label.apiType, entitySlug: id })
  const entity = remote.data
  const matching = articles.data ?? []

  if (remote.loading) return <div className="max-w-[1000px] mx-auto px-4 py-8"><LoadingSkeleton /></div>
  if (remote.error) return <div className="max-w-[1000px] mx-auto px-4 py-8"><EmptyState message="Không thể tải entity" sub={remote.error.message} /></div>
  if (!entity) return <div className="max-w-[1000px] mx-auto px-4 py-8"><EmptyState message={`${label.title} chưa có dữ liệu đã xuất bản`} /></div>

  return (
    <main className="max-w-[1000px] mx-auto px-4 sm:px-6 py-8">
      <header className="mb-8 rounded-xl border border-[#E5E7EB] bg-white p-6">
        <span className="text-xs font-semibold uppercase tracking-wider text-[#78A83D]">{label.title}</span>
        <h1 className="mt-1 text-3xl font-bold text-[#111827]">{entity.name}</h1>
        <p className="mt-2 text-sm text-[#6B7280]">{entity.article_count} bài đã xuất bản · {entity.story_count} Story</p>
      </header>
      <section className="mb-8 rounded-xl border border-[#E5E7EB] bg-white p-5">
        <SectionHeading>Timeline diễn biến</SectionHeading>
        <StoryTimeline storyId={null} entityType={label.apiType} entitySlug={id} />
      </section>
      <section>
        <SectionHeading>Tin liên quan</SectionHeading>
        {matching.map((article) => <NewsRow key={article.id} article={toArticle(article)} />)}
      </section>
    </main>
  )
}
