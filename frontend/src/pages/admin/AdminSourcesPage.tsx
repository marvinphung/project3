import { useEffect, useState } from 'react'
import {
  ApiError,
  createSource,
  listSources,
  toggleSource,
  triggerSourceCrawl,
  updateSource,
  type Source,
  type SourceConfiguration,
} from '../../api/client'

type SourceForm = {
  name: string
  rssUrl: string
  domains: string
  sourceType: Source['source_type']
  reliabilityTier: number
  crawlIntervalMinutes: number
  maxConcurrency: number
}

const emptyForm: SourceForm = {
  name: '', rssUrl: '', domains: '', sourceType: 'RSS', reliabilityTier: 2, crawlIntervalMinutes: 60, maxConcurrency: 2,
}

function toForm(source: Source): SourceForm {
  return {
    name: source.name,
    rssUrl: source.rss_url,
    domains: source.allowed_domains.join(', '),
    sourceType: source.source_type,
    reliabilityTier: source.reliability_tier,
    crawlIntervalMinutes: source.crawl_interval_minutes,
    maxConcurrency: source.max_concurrency,
  }
}

function toConfiguration(form: SourceForm): SourceConfiguration {
  return {
    name: form.name.trim(),
    rss_url: form.rssUrl.trim(),
    allowed_domains: form.domains.split(',').map((domain) => domain.trim()).filter(Boolean),
    source_type: form.sourceType,
    reliability_tier: Number(form.reliabilityTier),
    crawl_interval_minutes: Number(form.crawlIntervalMinutes),
    max_concurrency: Number(form.maxConcurrency),
  }
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString('vi-VN') : 'Chưa crawl'
}

function StatusChip({ enabled }: { enabled: boolean }) {
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${enabled ? 'bg-green-50 text-green-700' : 'bg-[#F3F4F6] text-[#6B7280]'}`}>{enabled ? 'Hoạt động' : 'Đã tắt'}</span>
}

export default function AdminSourcesPage() {
  const [items, setItems] = useState<Source[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [editing, setEditing] = useState<Source | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<SourceForm>(emptyForm)

  const load = async () => {
    setLoading(true)
    try {
      const response = await listSources()
      setItems(response.items)
      setError(null)
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Không thể tải nguồn tin.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const replace = (source: Source) => setItems((current) => current.map((item) => item.id === source.id ? source : item))
  const openCreate = () => { setEditing(null); setForm(emptyForm); setShowForm(true); setError(null) }
  const openEdit = (source: Source) => { setEditing(source); setForm(toForm(source)); setShowForm(true); setError(null) }

  const save = async () => {
    setBusyId(editing?.id ?? 'new')
    try {
      const saved = editing
        ? await updateSource(editing.id, toConfiguration(form), editing.version)
        : await createSource(toConfiguration(form))
      setItems((current) => editing ? current.map((item) => item.id === saved.id ? saved : item) : [saved, ...current])
      setShowForm(false)
      setError(null)
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Không thể lưu nguồn tin.')
    } finally {
      setBusyId(null)
    }
  }

  const toggle = async (source: Source) => {
    setBusyId(source.id)
    try { replace(await toggleSource(source.id, !source.enabled, source.version)); setError(null) }
    catch (requestError) { setError(requestError instanceof ApiError ? requestError.message : 'Không thể cập nhật nguồn tin.') }
    finally { setBusyId(null) }
  }

  const crawl = async (source: Source) => {
    setBusyId(source.id)
    try { await triggerSourceCrawl(source.id, `manual:${source.id}:${Date.now()}`); setError(null) }
    catch (requestError) { setError(requestError instanceof ApiError ? requestError.message : 'Không thể bắt đầu crawl.') }
    finally { setBusyId(null) }
  }

  return <div className="p-6">
    <div className="flex items-center justify-between mb-6">
      <h1 className="text-2xl font-bold text-[#111827]">Nguồn tin</h1>
      <button onClick={openCreate} className="px-4 py-2 bg-[#78A83D] text-white rounded-lg text-sm font-medium hover:bg-[#6a9435]">Thêm nguồn</button>
    </div>
    {error && <p role="alert" className="mb-4 text-sm text-red-600">{error}</p>}
    <div className="bg-white border border-[#E5E7EB] rounded-xl overflow-hidden">
      {loading ? <p className="p-6 text-sm text-[#6B7280]">Đang tải nguồn tin…</p> : items.length === 0 ? <p className="p-6 text-sm text-[#6B7280]">Chưa có nguồn tin thật nào được cấu hình.</p> : <div className="overflow-x-auto"><table className="w-full text-sm">
        <thead><tr className="border-b border-[#E5E7EB] bg-[#F9FAFB]">
          <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase">Tên nguồn</th><th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase">Loại</th><th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase">Trạng thái</th><th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase">Lần crawl gần nhất</th><th className="text-right px-4 py-3 font-semibold text-[#374151] text-xs uppercase">Thao tác</th>
        </tr></thead>
        <tbody className="divide-y divide-[#E5E7EB]">{items.map((source) => <tr key={source.id} className="hover:bg-[#F9FAFB]">
          <td className="px-4 py-3"><p className="font-medium text-[#111827]">{source.name}</p><p className="text-xs text-[#6B7280] truncate max-w-80">{source.rss_url}</p></td>
          <td className="px-4 py-3"><span className="text-xs font-mono bg-[#F3F4F6] px-2 py-0.5 rounded text-[#6B7280]">{source.source_type}</span></td>
          <td className="px-4 py-3"><StatusChip enabled={source.enabled} /></td>
          <td className="px-4 py-3 text-[#6B7280]">{formatDate(source.last_discovered_at)}</td>
          <td className="px-4 py-3"><div className="flex justify-end gap-1"><button disabled={busyId === source.id} onClick={() => void toggle(source)} className="px-2 py-1 text-xs text-[#6B7280] hover:bg-[#F3F4F6] rounded disabled:opacity-50">{source.enabled ? 'Tắt' : 'Bật'}</button><button disabled={busyId === source.id || !source.enabled} onClick={() => void crawl(source)} className="px-2 py-1 text-xs text-[#78A83D] hover:bg-[#78A83D]/5 rounded disabled:opacity-50">Crawl</button><button onClick={() => openEdit(source)} className="px-2 py-1 text-xs text-[#6B7280] hover:bg-[#F3F4F6] rounded">Sửa</button></div></td>
        </tr>)}</tbody>
      </table></div>}
    </div>
    {showForm && <SourceDialog form={form} editing={editing} busy={busyId !== null} onChange={setForm} onClose={() => setShowForm(false)} onSave={() => void save()} />}
  </div>
}

function SourceDialog({ form, editing, busy, onChange, onClose, onSave }: { form: SourceForm; editing: Source | null; busy: boolean; onChange: (value: SourceForm) => void; onClose: () => void; onSave: () => void }) {
  const update = <K extends keyof SourceForm>(key: K, value: SourceForm[K]) => onChange({ ...form, [key]: value })
  return <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="source-dialog-title">
    <button aria-label="Đóng" className="absolute inset-0 bg-black/40" onClick={onClose} />
    <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md p-6"><h2 id="source-dialog-title" className="font-bold text-[#111827] mb-5">{editing ? 'Sửa nguồn tin' : 'Thêm nguồn tin'}</h2>
      <div className="space-y-4"><label className="block text-sm font-medium text-[#374151]">Tên nguồn<input value={form.name} onChange={(event) => update('name', event.target.value)} className="mt-1.5 w-full px-3 py-2 border rounded-lg" /></label><label className="block text-sm font-medium text-[#374151]">URL nguồn<input type="url" value={form.rssUrl} onChange={(event) => update('rssUrl', event.target.value)} className="mt-1.5 w-full px-3 py-2 border rounded-lg" /></label><label className="block text-sm font-medium text-[#374151]">Allowed domains, ngăn cách bởi dấu phẩy<input value={form.domains} onChange={(event) => update('domains', event.target.value)} className="mt-1.5 w-full px-3 py-2 border rounded-lg" /></label><label className="block text-sm font-medium text-[#374151]">Loại<select value={form.sourceType} onChange={(event) => update('sourceType', event.target.value as Source['source_type'])} className="mt-1.5 w-full px-3 py-2 border rounded-lg"><option value="RSS">RSS</option><option value="HTML">HTML</option></select></label></div>
      <div className="flex gap-3 mt-6"><button onClick={onClose} className="flex-1 py-2 border rounded-lg text-sm">Hủy</button><button disabled={busy || !form.name.trim() || !form.rssUrl.trim() || !form.domains.trim()} onClick={onSave} className="flex-1 py-2 bg-[#78A83D] text-white rounded-lg text-sm font-semibold disabled:opacity-50">{busy ? 'Đang lưu…' : 'Lưu nguồn'}</button></div>
    </div>
  </div>
}
