import { useEffect, useState } from 'react'
import {
  ApiError,
  EditorialRevisionDetail,
  approveArticle,
  listEditorialRevisions,
  publishArticle,
  rejectArticle,
  submitArticle,
  updateEditorialRevision,
} from '../../api/client'

const stateLabel: Record<string, string> = {
  DRAFT: 'Bản nháp',
  NEEDS_REVIEW: 'Chờ duyệt',
  APPROVED: 'Đã duyệt',
  REJECTED: 'Từ chối',
  STALE: 'Cũ',
}

export default function AdminDraftPage() {
  const [items, setItems] = useState<EditorialRevisionDetail[]>([])
  const [selected, setSelected] = useState<EditorialRevisionDetail | null>(null)
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const response = await listEditorialRevisions()
      const revisions = response.items
      setItems(revisions)
      if (selected) {
        const fresh = revisions.find(item => item.generated_article_id === selected.generated_article_id)
        if (fresh) { setSelected(fresh); setTitle(fresh.title_vi); setBody(fresh.body_vi) }
      }
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : 'Không thể tải bản nháp.')
    } finally { setLoading(false) }
  }

  useEffect(() => { void load() }, [])

  const open = (item: EditorialRevisionDetail) => {
    setSelected(item); setTitle(item.title_vi); setBody(item.body_vi); setMessage('')
  }

  const save = async () => {
    if (!selected) return
    setBusy(true); setMessage('')
    try {
      const updated = await updateEditorialRevision(selected.generated_article_id, { title_vi: title, body_vi: body }, selected.revision_number)
      setSelected(updated); setItems(current => current.map(item => item.generated_article_id === updated.generated_article_id ? updated : item))
      setMessage('Đã lưu nội dung tiếng Việt.')
    } catch (error) { setMessage(error instanceof ApiError ? error.message : 'Không thể lưu bản nháp.') }
    finally { setBusy(false) }
  }

  const transition = async (action: 'submit' | 'approve' | 'reject' | 'publish') => {
    if (!selected) return
    setBusy(true); setMessage('')
    try {
      if (action === 'submit') await submitArticle(selected.generated_article_id, selected.revision_number)
      if (action === 'approve') await approveArticle(selected.generated_article_id, selected.revision_number)
      if (action === 'reject') await rejectArticle(selected.generated_article_id, selected.revision_number)
      if (action === 'publish') await publishArticle(selected.generated_article_id, title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') || `story-${selected.story_id}`, crypto.randomUUID())
      setMessage(action === 'publish' ? 'Đã xuất bản bài viết.' : 'Đã cập nhật trạng thái.')
      await load()
    } catch (error) { setMessage(error instanceof ApiError ? error.message : 'Không thể cập nhật trạng thái.') }
    finally { setBusy(false) }
  }

  if (loading) return <div className="p-6 text-sm text-[#6B7280]">Đang tải bản nháp thật từ PostgreSQL...</div>

  if (selected) return (
    <div className="p-6 max-w-5xl">
      <button onClick={() => setSelected(null)} className="text-sm text-[#78A83D] mb-5">← Quay lại danh sách</button>
      <div className="bg-white border border-[#E5E7EB] rounded-xl p-6">
        <div className="flex justify-between gap-4 mb-5">
          <div><h1 className="text-2xl font-bold text-[#111827]">Biên tập bản nháp</h1><p className="text-xs text-[#6B7280] mt-1">Article ID: {selected.generated_article_id}</p></div>
          <span className="h-fit px-3 py-1 rounded-full text-xs font-semibold bg-[#F3F4F6]">{stateLabel[selected.state] ?? selected.state}</span>
        </div>
        <label className="block text-xs font-semibold text-[#6B7280] mb-1">TIÊU ĐỀ TIẾNG VIỆT</label>
        <textarea value={title} onChange={event => setTitle(event.target.value)} rows={2} className="w-full border rounded-lg p-3 mb-4 text-lg font-semibold" />
        <label className="block text-xs font-semibold text-[#6B7280] mb-1">NỘI DUNG TIẾNG VIỆT</label>
        <textarea value={body} onChange={event => setBody(event.target.value)} rows={14} className="w-full border rounded-lg p-3 mb-5 text-sm leading-relaxed" />
        <div className="flex flex-wrap gap-2">
          {(selected.state === 'DRAFT' || selected.state === 'REJECTED') && <><button disabled={busy} onClick={() => void save()} className="px-4 py-2 rounded-lg bg-[#78A83D] text-white text-sm font-semibold">Lưu bản nháp</button><button disabled={busy} onClick={() => void transition('submit')} className="px-4 py-2 rounded-lg border text-sm">Gửi duyệt</button></>}
          {selected.state === 'NEEDS_REVIEW' && <><button disabled={busy} onClick={() => void transition('approve')} className="px-4 py-2 rounded-lg bg-[#2E7D32] text-white text-sm font-semibold">Phê duyệt</button><button disabled={busy} onClick={() => void transition('reject')} className="px-4 py-2 rounded-lg border border-red-200 text-red-600 text-sm">Từ chối</button></>}
          {selected.state === 'APPROVED' && <button disabled={busy} onClick={() => void transition('publish')} className="px-4 py-2 rounded-lg bg-[#78A83D] text-white text-sm font-semibold">Xuất bản</button>}
        </div>
        {message && <p className="mt-4 text-sm text-[#374151]">{message}</p>}
      </div>
    </div>
  )

  return <div className="p-6"><div className="flex items-center justify-between mb-6"><h1 className="text-2xl font-bold text-[#111827]">Bản nháp</h1><button onClick={() => void load()} className="text-sm text-[#78A83D]">Làm mới</button></div>{message && <p className="mb-4 text-sm text-red-600">{message}</p>}<div className="bg-white border border-[#E5E7EB] rounded-xl overflow-hidden">{items.length === 0 ? <p className="p-6 text-sm text-[#6B7280]">Chưa có bản nháp cần biên tập.</p> : <table className="w-full text-sm"><thead><tr className="border-b bg-[#F9FAFB]"><th className="text-left px-4 py-3">Tiêu đề</th><th className="text-left px-4 py-3">Trạng thái</th><th className="text-left px-4 py-3">Cập nhật</th><th /></tr></thead><tbody className="divide-y">{items.map(item => <tr key={item.generated_article_id}><td className="px-4 py-3 font-medium">{item.title_vi}</td><td className="px-4 py-3">{stateLabel[item.state] ?? item.state}</td><td className="px-4 py-3 text-[#6B7280]">{new Date(item.updated_at).toLocaleString('vi-VN')}</td><td className="px-4 py-3 text-right"><button onClick={() => open(item)} className="text-[#78A83D]">Xem & duyệt</button></td></tr>)}</tbody></table>}</div></div>
}
