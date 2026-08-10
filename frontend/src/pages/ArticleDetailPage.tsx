import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { articles, sources } from '../data/mock'
import { usePublicArticle } from '../api/hooks'
import StoryTimeline from '../components/StoryTimeline'
import { EmptyState, EntityChips, LoadingSkeleton, MediumNewsCard } from '../components/ui'

export default function ArticleDetailPage() {
  const { id } = useParams()
  const remote = usePublicArticle(id)
  const [timelineOpen, setTimelineOpen] = useState(true)
  if (remote.loading) {
    return <div className="max-w-[760px] mx-auto px-4 sm:px-6 py-8"><LoadingSkeleton /></div>
  }
  if (remote.error || !remote.data) {
    return <div className="max-w-[760px] mx-auto px-4 sm:px-6 py-8"><EmptyState message="Không thể tải bài viết" sub={remote.error?.message} /></div>
  }
  const apiArticle = remote.data
  const article = articles.find(a => a.id === id) ?? articles[0]
  const related = articles.filter(a => a.id !== article.id).slice(0, 3)

  return (
    <div className="max-w-[1280px] mx-auto px-4 sm:px-6 py-8">
      <div className="max-w-[760px] mx-auto">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-[#6B7280] mb-6">
          <Link to="/" className="hover:text-[#78A83D]">Trang chủ</Link>
          <span>/</span>
          <Link to="/tin-moi" className="hover:text-[#78A83D]">Tin mới</Link>
          <span>/</span>
          <span className="text-[#374151] truncate">Bài viết</span>
        </div>

        {/* Category + status */}
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-semibold text-[#78A83D] uppercase tracking-wider">Chuyển nhượng</span>
        </div>

        {/* Headline */}
        <h1 className="text-3xl sm:text-4xl font-bold text-[#111827] leading-tight mb-4">
          {apiArticle.title_vi}
        </h1>

        {/* Summary */}
        <p className="text-lg text-[#374151] leading-relaxed mb-4">{apiArticle.body_vi.slice(0, 280)}{apiArticle.body_vi.length > 280 ? '…' : ''}</p>

        {/* Meta */}
        <div className="flex items-center gap-3 flex-wrap mb-2">
          <p className="text-sm text-[#6B7280]">Cập nhật {new Date(apiArticle.published_at).toLocaleString('vi-VN')} · Story phiên bản {apiArticle.story_version}</p>
        </div>
        <div className="mb-6">
          <EntityChips entities={article.entities} />
        </div>

        {/* Cover image */}
        <div className="relative aspect-[16/9] rounded-xl overflow-hidden bg-[#E5E7EB] mb-8">
          <div className="w-full h-full bg-gradient-to-br from-[#EAF2E1] to-[#DCE7CF]" aria-label="Ảnh bài viết" />
        </div>

        {/* Body */}
        <div className="prose-like space-y-5 mb-10">
          {apiArticle.body_vi.split(/\n\s*\n/).filter(Boolean).map((p, i) => (
            <p key={i} className="text-base sm:text-[17px] text-[#1F2937] leading-[1.75]">{p}</p>
          ))}

          <h2 className="text-xl font-bold text-[#111827] mt-8 mb-3">Diễn biến tiếp theo</h2>
        </div>

        <hr className="border-[#E5E7EB] my-8" />

        {/* Related entities */}
        <section className="mb-8">
          <h3 className="text-base font-bold text-[#111827] mb-4">Liên quan</h3>
          <div className="flex flex-wrap gap-3">
            {article.entities.map(e => (
              <Link
                key={e.id}
                to={e.type === 'club' ? `/clb/${e.id}` : e.type === 'player' ? `/cau-thu/${e.id}` : `/hlv/${e.id}`}
                className="flex items-center gap-2.5 bg-white border border-[#E5E7EB] rounded-lg px-3 py-2 hover:border-[#78A83D]/40 transition-colors"
              >
                <span className="w-8 h-8 rounded-full bg-[#F3F4F6] flex items-center justify-center text-xs font-bold text-[#6B7280]">
                  {e.name.charAt(0)}
                </span>
                <div>
                  <p className="text-sm font-medium text-[#111827]">{e.name}</p>
                  <p className="text-xs text-[#6B7280]">{e.type === 'club' ? 'CLB' : e.type === 'player' ? 'Cầu thủ' : 'HLV'}</p>
                </div>
              </Link>
            ))}
          </div>
        </section>

        {/* Timeline */}
        <section className="mb-8">
          <button
            onClick={() => setTimelineOpen(!timelineOpen)}
            className="flex items-center justify-between w-full mb-4 group"
          >
            <h3 className="text-base font-bold text-[#111827]">Diễn biến câu chuyện</h3>
            <svg className={`w-5 h-5 text-[#6B7280] transition-transform ${timelineOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
          </button>
          {timelineOpen && (
            <div className="relative pl-6">
              <div className="absolute left-2 top-2 bottom-2 w-px bg-[#E5E7EB]" />
              <StoryTimeline storyId={apiArticle.story_id} />
            </div>
          )}
        </section>

        {/* Sources */}
        <section className="mb-8">
          <h3 className="text-base font-bold text-[#111827] mb-4">Nguồn tham khảo</h3>
          <div className="space-y-3">
            {sources.map(s => (
              <a key={s.id} href={s.url} className="flex items-center justify-between p-3 bg-white border border-[#E5E7EB] rounded-lg hover:border-[#78A83D]/40 transition-colors group">
                <div>
                  <p className="text-xs font-semibold text-[#78A83D] mb-0.5">{s.name}</p>
                  <p className="text-sm text-[#374151] group-hover:text-[#111827]">{s.title}</p>
                  <p className="text-xs text-[#9CA3AF] mt-0.5">{s.time}</p>
                </div>
                <svg className="w-4 h-4 text-[#9CA3AF] flex-shrink-0 ml-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
              </a>
            ))}
          </div>
        </section>

        {/* Related news */}
        <section>
          <h3 className="text-base font-bold text-[#111827] mb-4">Tin liên quan</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {related.map(a => (
              <div key={a.id}>
                <MediumNewsCard article={a} />
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
