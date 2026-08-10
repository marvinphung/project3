import { Link, useParams } from 'react-router'
import StoryTimeline from '../components/StoryTimeline'

export default function StoryPage() {
  const { id } = useParams()

  return (
    <div className="max-w-[900px] mx-auto px-4 sm:px-6 py-8">
      <div className="mb-6 flex items-center gap-2 text-xs text-[#6B7280]">
        <Link to="/" className="hover:text-[#78A83D]">Trang chủ</Link>
        <span>/</span>
        <span className="text-[#374151]">Story</span>
      </div>
      <div className="mb-8">
        <span className="text-xs font-semibold uppercase tracking-wider text-[#78A83D]">Story</span>
        <h1 className="mt-1 text-2xl sm:text-3xl font-bold text-[#111827]">Diễn biến sự kiện</h1>
        <p className="mt-2 text-sm text-[#6B7280]">Theo dõi các cập nhật theo thời gian và mức độ xác thực.</p>
      </div>
      <div className="rounded-xl border border-[#E5E7EB] bg-white p-5 sm:p-7">
        <StoryTimeline storyId={id ?? null} />
      </div>
    </div>
  )
}
