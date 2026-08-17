import { Link, useParams } from 'react-router'

import { toArticle } from '../api/adapters'
import { useArticleSources, usePublicArticle, usePublicArticles } from '../api/hooks'
import StoryTimeline from '../components/StoryTimeline'
import { EmptyState, EntityChips, LoadingSkeleton, NewsRow, SectionHeading } from '../components/ui'

export default function ArticleDetailPage() {
  const { id = '' } = useParams()
  const remote = usePublicArticle(id)
  const sources = useArticleSources(id)
  const related = usePublicArticles(4, { storyId: remote.data?.story_id })

  if (remote.loading) return <div className="max-w-[800px] mx-auto px-4 py-8"><LoadingSkeleton /></div>
  if (remote.error || !remote.data) return <div className="max-w-[800px] mx-auto px-4 py-8"><EmptyState message="Không thể tải bài viết" sub={remote.error?.message} /></div>

  const article = remote.data
  const entities = toArticle(article).entities
  const relatedArticles = (related.data ?? []).filter((item) => item.slug !== article.slug)
  return (
    <main className="max-w-[900px] mx-auto px-4 sm:px-6 py-8">
      <nav className="mb-6 text-xs text-[#6B7280]"><Link to="/">Trang chủ</Link> / <Link to="/tin-moi">Tin mới</Link></nav>
      <article>
        <h1 className="text-3xl sm:text-4xl font-bold leading-tight text-[#111827]">{article.title_vi}</h1>
        <p className="mt-4 text-sm text-[#6B7280]">Xuất bản {new Date(article.published_at).toLocaleString('vi-VN')} · Story phiên bản {article.story_version}</p>
        <div className="mt-4"><EntityChips entities={entities} /></div>
        <div className="mt-8 space-y-5">
          {article.body_vi.split(/\n\s*\n/).filter(Boolean).map((paragraph, index) => <p key={index} className="text-[17px] leading-[1.75] text-[#1F2937]">{paragraph}</p>)}
        </div>
      </article>
      <section className="mt-10 rounded-xl border border-[#E5E7EB] bg-white p-5">
        <SectionHeading>Timeline diễn biến</SectionHeading>
        <StoryTimeline storyId={article.story_id} />
      </section>
      <section className="mt-10">
        <SectionHeading>Nguồn tham khảo</SectionHeading>
        {sources.loading && <LoadingSkeleton />}
        {!sources.loading && !sources.data?.length && <EmptyState message="Chưa có nguồn công khai" />}
        <div className="space-y-3">
          {sources.data?.map((source) => <a key={source.source_id} href={source.source_url} target="_blank" rel="noreferrer" className="block rounded-lg border border-[#E5E7EB] bg-white p-3 hover:border-[#78A83D]/50"><strong className="text-sm text-[#111827]">{source.source_name}</strong><p className="mt-1 text-xs text-[#6B7280]">Độ tin cậy tier {source.reliability_tier} · {new Date(source.published_at).toLocaleString('vi-VN')}</p></a>)}
        </div>
      </section>
      {relatedArticles.length > 0 && <section className="mt-10"><SectionHeading>Tin cùng Story</SectionHeading>{relatedArticles.map((item) => <NewsRow key={item.id} article={toArticle(item)} />)}</section>}
    </main>
  )
}
