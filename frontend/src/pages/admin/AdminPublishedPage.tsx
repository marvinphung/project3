import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { ApiError, listAdminPublications, type AdminPublication } from '../../api/client'

export default function AdminPublishedPage() {
  const [items, setItems] = useState<AdminPublication[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null)
  useEffect(() => { let active = true; listAdminPublications().then((response) => { if (active) setItems(response.items) }).catch((cause: unknown) => { if (active) setError(cause instanceof ApiError ? cause.message : 'Không thể tải bài đã xuất bản.') }).finally(() => { if (active) setLoading(false) }); return () => { active = false } }, [])
  return <div className="p-6"><h1 className="text-2xl font-bold text-[#111827] mb-6">Bài đã xuất bản</h1>{error && <p role="alert" className="mb-4 text-sm text-red-600">{error}</p>}<div className="bg-white border border-[#E5E7EB] rounded-xl overflow-hidden">{loading ? <p className="p-6 text-sm text-[#6B7280]">Đang tải bài đã xuất bản…</p> : items.length === 0 ? <p className="p-6 text-sm text-[#6B7280]">Chưa có bài viết được xuất bản.</p> : <table className="w-full text-sm"><thead><tr className="border-b bg-[#F9FAFB]"><th className="text-left px-4 py-3">Tiêu đề</th><th className="text-left px-4 py-3">Xuất bản</th><th /></tr></thead><tbody className="divide-y">{items.map((item) => <tr key={item.id}><td className="px-4 py-3 font-medium">{item.title_vi}</td><td className="px-4 py-3 text-[#6B7280]">{new Date(item.published_at).toLocaleString('vi-VN')}</td><td className="px-4 py-3 text-right"><Link to={`/bai-viet/${item.slug}`} className="text-[#78A83D] text-xs">Xem bài</Link></td></tr>)}</tbody></table>}</div></div>
}
