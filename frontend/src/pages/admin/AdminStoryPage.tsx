import { useEffect, useState } from 'react'
import { ApiError, listAdminStories, type AdminStory } from '../../api/client'

export default function AdminStoryPage() {
  const [items, setItems] = useState<AdminStory[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { let active = true; listAdminStories().then((response) => { if (active) setItems(response.items) }).catch((cause: unknown) => { if (active) setError(cause instanceof ApiError ? cause.message : 'Không thể tải Story.') }).finally(() => { if (active) setLoading(false) }); return () => { active = false } }, [])
  return <div className="p-6"><h1 className="text-2xl font-bold text-[#111827] mb-6">Story</h1>{error && <p role="alert" className="mb-4 text-sm text-red-600">{error}</p>}<div className="bg-white border border-[#E5E7EB] rounded-xl overflow-hidden">{loading ? <p className="p-6 text-sm text-[#6B7280]">Đang tải Story…</p> : items.length === 0 ? <p className="p-6 text-sm text-[#6B7280]">Chưa có Story thật nào.</p> : <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b bg-[#F9FAFB]"><th className="text-left px-4 py-3">Loại sự kiện</th><th className="text-left px-4 py-3">Trạng thái</th><th className="text-left px-4 py-3">Nguồn</th><th className="text-left px-4 py-3">Cập nhật</th></tr></thead><tbody className="divide-y">{items.map((story) => <tr key={story.id}><td className="px-4 py-3 font-medium">{story.event_type}</td><td className="px-4 py-3">{story.status}</td><td className="px-4 py-3">{story.source_count}</td><td className="px-4 py-3 text-[#6B7280]">{new Date(story.last_seen_at).toLocaleString('vi-VN')}</td></tr>)}</tbody></table></div>}</div></div>
}
