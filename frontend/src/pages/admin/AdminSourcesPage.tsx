import { useState } from 'react'
import { useEffect } from 'react'
import { ApiError, listSources, toggleSource, triggerSourceCrawl, type Source } from '../../api/client'

const sourcesData = [
  { id: 1, name: 'BBC Sport', type: 'RSS', status: 'active', lastCrawl: '5 phút trước', articles: 12, errors: 0 },
  { id: 2, name: 'Sky Sports', type: 'RSS', status: 'active', lastCrawl: '8 phút trước', articles: 9, errors: 0 },
  { id: 3, name: 'The Athletic', type: 'HTML', status: 'active', lastCrawl: '15 phút trước', articles: 7, errors: 1 },
  { id: 4, name: 'marca.com', type: 'HTML', status: 'error', lastCrawl: '2 giờ trước', articles: 0, errors: 3 },
  { id: 5, name: 'L\'Équipe', type: 'RSS', status: 'active', lastCrawl: '30 phút trước', articles: 5, errors: 0 },
  { id: 6, name: 'Kicker', type: 'RSS', status: 'disabled', lastCrawl: '1 ngày trước', articles: 0, errors: 0 },
]

type Source = typeof sourcesData[0]

const StatusChip = ({ status }: { status: string }) => {
  const map: Record<string, string> = {
    active: 'bg-green-50 text-green-700',
    error: 'bg-red-50 text-red-600',
    disabled: 'bg-[#F3F4F6] text-[#9CA3AF]',
  }
  const labels: Record<string, string> = {
    active: 'Hoạt động',
    error: 'Lỗi',
    disabled: 'Đã tắt',
  }
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[status]}`}>{labels[status]}</span>
}

export default function AdminSourcesPage() {
  const [showModal, setShowModal] = useState(false)
  const [remote, setRemote] = useState<{ items: Source[]; loading: boolean; error: string | null }>({ items: [], loading: true, error: null })
  const [toggling, setToggling] = useState<string | null>(null)
  const [crawling, setCrawling] = useState<string | null>(null)
  useEffect(() => {
    listSources()
      .then((response) => setRemote({ items: response.items, loading: false, error: null }))
      .catch((error: unknown) => setRemote({ items: [], loading: false, error: error instanceof ApiError ? error.message : 'Không thể tải nguồn tin' }))
  }, [])
  const displaySources = remote.items.length > 0 ? remote.items.map((source) => ({
    id: source.id,
    name: source.name,
    type: source.source_type,
    status: source.enabled ? 'active' : 'disabled',
    lastCrawl: source.last_discovered_at ? new Date(source.last_discovered_at).toLocaleString('vi-VN') : 'Chưa crawl',
    articles: 0,
    errors: 0,
  })) : sourcesData
  const handleToggle = async (source: (typeof displaySources)[number]) => {
    if (!/^[0-9a-f-]{36}$/i.test(String(source.id))) {
      setRemote((current) => ({ ...current, error: 'Nguồn fixture chưa có UUID từ backend.' }))
      return
    }
    const current = remote.items.find((item) => item.id === source.id)
    if (!current) return
    setToggling(current.id)
    try {
      const updated = await toggleSource(current.id, !current.enabled, current.version)
      setRemote((state) => ({ ...state, items: state.items.map((item) => item.id === updated.id ? updated : item), error: null }))
    } catch (error) {
      setRemote((state) => ({ ...state, error: error instanceof ApiError ? error.message : 'Không thể cập nhật nguồn tin' }))
    } finally {
      setToggling(null)
    }
  }
  const handleCrawl = async (source: (typeof displaySources)[number]) => {
    if (!/^[0-9a-f-]{36}$/i.test(String(source.id))) {
      setRemote((current) => ({ ...current, error: 'Nguồn fixture chưa có UUID từ backend.' }))
      return
    }
    setCrawling(String(source.id))
    try {
      await triggerSourceCrawl(String(source.id), `manual:${source.id}:${Date.now()}`)
      setRemote((state) => ({ ...state, error: null }))
    } catch (error) {
      setRemote((state) => ({ ...state, error: error instanceof ApiError ? error.message : 'Không thể bắt đầu crawl' }))
    } finally {
      setCrawling(null)
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-[#111827]">Nguồn tin</h1>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-[#78A83D] text-white rounded-lg text-sm font-medium hover:bg-[#6a9435] transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
          Thêm nguồn
        </button>
      </div>

      {remote.loading && <p className="mb-4 text-sm text-[#6B7280]">Đang tải nguồn tin...</p>}
      {remote.error && <p className="mb-4 text-sm text-red-600">{remote.error}</p>}
      <div className="bg-white border border-[#E5E7EB] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E5E7EB] bg-[#F9FAFB]">
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Tên nguồn</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Loại</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Trạng thái</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Lần crawl gần nhất</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Bài gần nhất</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Lỗi</th>
                <th className="text-right px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5E7EB]">
              {displaySources.map(s => (
                <tr key={s.id} className="hover:bg-[#F9FAFB] transition-colors">
                  <td className="px-4 py-3 font-medium text-[#111827]">{s.name}</td>
                  <td className="px-4 py-3"><span className="text-xs font-mono bg-[#F3F4F6] px-2 py-0.5 rounded text-[#6B7280]">{s.type}</span></td>
                  <td className="px-4 py-3"><StatusChip status={s.status} /></td>
                  <td className="px-4 py-3 text-[#6B7280]">{s.lastCrawl}</td>
                  <td className="px-4 py-3 text-[#374151]">{s.articles}</td>
                  <td className="px-4 py-3">
                    {s.errors > 0 ? <span className="text-red-600 font-medium">{s.errors}</span> : <span className="text-[#9CA3AF]">—</span>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => void handleToggle(s)} disabled={toggling === s.id} className="px-2 py-1 text-xs text-[#6B7280] hover:text-[#111827] hover:bg-[#F3F4F6] rounded transition-colors disabled:opacity-50">
                        {s.status === 'disabled' ? 'Bật' : 'Tắt'}
                      </button>
                      <button onClick={() => void handleCrawl(s)} disabled={crawling === String(s.id)} className="px-2 py-1 text-xs text-[#6B7280] hover:text-[#78A83D] hover:bg-[#F3F4F6] rounded transition-colors disabled:opacity-50">Crawl</button>
                      <button className="px-2 py-1 text-xs text-[#6B7280] hover:text-[#111827] hover:bg-[#F3F4F6] rounded transition-colors">Sửa</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowModal(false)} />
          <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-bold text-[#111827]">Thêm nguồn tin</h2>
              <button onClick={() => setShowModal(false)} className="p-1 text-[#6B7280] hover:text-[#111827]">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[#374151] mb-1.5">Tên nguồn</label>
                <input type="text" placeholder="BBC Sport" className="w-full px-3 py-2 border border-[#E5E7EB] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30 focus:border-[#78A83D]" />
              </div>
              <div>
                <label className="block text-sm font-medium text-[#374151] mb-1.5">URL nguồn</label>
                <input type="url" placeholder="https://..." className="w-full px-3 py-2 border border-[#E5E7EB] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30 focus:border-[#78A83D]" />
              </div>
              <div>
                <label className="block text-sm font-medium text-[#374151] mb-1.5">Loại</label>
                <select className="w-full px-3 py-2 border border-[#E5E7EB] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30 focus:border-[#78A83D]">
                  <option>RSS</option>
                  <option>HTML</option>
                </select>
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowModal(false)} className="flex-1 py-2 border border-[#E5E7EB] text-[#374151] rounded-lg text-sm font-medium hover:bg-[#F3F4F6] transition-colors">Hủy</button>
              <button className="flex-1 py-2 bg-[#78A83D] text-white rounded-lg text-sm font-semibold hover:bg-[#6a9435] transition-colors">Thêm nguồn</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
