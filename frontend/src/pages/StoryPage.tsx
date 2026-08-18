import { Link, useParams } from 'react-router'
import StoryTimeline from '../components/StoryTimeline'
import { usePublicStory } from '../api/hooks'
import { EmptyState, LoadingSkeleton } from '../components/ui'

export default function StoryPage() {
  const { id } = useParams()
  const story = usePublicStory(id ?? '')

  if (story.loading) return <div className="max-w-[900px] mx-auto px-4 py-8"><LoadingSkeleton /></div>
  if (story.error || !story.data) return <div className="max-w-[900px] mx-auto px-4 py-8"><EmptyState message="Không thể tải Story" sub={story.error?.message} /></div>

  return (
    <div className="max-w-[900px] mx-auto px-4 sm:px-6 py-8">
      <div className="mb-6 flex items-center gap-2 text-xs text-[#6B7280]">
        <Link to="/" className="hover:text-[#78A83D]">Trang chủ</Link>
        <span>/</span>
        <span className="text-[#374151]">Story</span>
      </div>
      <div className="mb-8">
        <span className="text-xs font-semibold uppercase tracking-wider text-[#78A83D]">Story</span>
        <h1 className="mt-1 text-2xl sm:text-3xl font-bold text-[#111827]">{story.data.title_vi || story.data.event_type}</h1>
        <p className="mt-2 text-sm text-[#6B7280]">{story.data.status} · {story.data.confirmation} · {story.data.entity_ids.length} entity</p>
        {story.data.summary_vi && (
          <p className="mt-3 text-sm leading-relaxed text-[#4B5563]">{story.data.summary_vi}</p>
        )}
      </div>
      <div className="rounded-xl border border-[#E5E7EB] bg-white p-5 sm:p-7">
        <StoryTimeline storyId={id ?? null} />
      </div>
    </div>
  )
}
