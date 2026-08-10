import { useEntityStoryTimeline, useStoryTimeline } from '../api/timeline'
import { EmptyState, LoadingSkeleton } from './ui'

function formatTime(value: string) {
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

export default function StoryTimeline({
  storyId,
  entityType,
  entitySlug,
}: {
  storyId: string | null
  entityType?: string
  entitySlug?: string
}) {
  const directTimeline = useStoryTimeline(storyId)
  const entityTimeline = useEntityStoryTimeline(entityType ?? '', entitySlug ?? '')
  const resolvedStoryId = storyId ?? (entityType && entitySlug ? 'entity' : null)
  const timeline = storyId ? directTimeline : entityTimeline

  if (!resolvedStoryId) {
    return (
      <EmptyState
        message="Story timeline chưa được liên kết"
        sub="Timeline sẽ xuất hiện khi thực thể được gắn với một Story."
      />
    )
  }
  if (timeline.loading) return <LoadingSkeleton />
  if (timeline.error) {
    return <EmptyState message="Không thể tải timeline" sub={timeline.error.message} />
  }
  if (!timeline.data?.length) return <EmptyState message="Story chưa có diễn biến" />

  const entries = timeline.data ?? []
  return (
    <ol className="relative ml-3 border-l border-[#DCE7CF] pl-6">
      {entries.map((entry, index) => (
        <li key={`${entry.story_id}-${entry.window_start}`} className="relative pb-6 last:pb-0">
          <span className="absolute -left-[31px] top-1 h-3 w-3 rounded-full border-2 border-white bg-[#78A83D] shadow-sm" />
          <time className="text-xs font-semibold text-[#78A83D]">{formatTime(entry.window_start)}</time>
          <p className="mt-1 text-sm leading-relaxed text-[#374151]">{entry.summary_vi}</p>
          <span className="mt-2 inline-flex rounded-full bg-[#F3F7EE] px-2 py-0.5 text-[11px] font-medium text-[#5E8430]">
            {entry.confirmation}
          </span>
          {index === entries.length - 1 && (
            <span className="ml-2 text-[11px] text-[#9CA3AF]">Mới nhất</span>
          )}
        </li>
      ))}
    </ol>
  )
}
