const sourceArticles = [
  { id: 1, title: 'Arsenal in advanced talks for striker transfer', source: 'BBC Sport', time: '18 phút trước', status: 'processed', duplicate: false, entities: ['Arsenal', 'Mikel Arteta'], story: 'Arsenal Transfer' },
  { id: 2, title: 'Gunners accelerate move for top target this summer', source: 'Sky Sports', time: '45 phút trước', status: 'processed', duplicate: true, entities: ['Arsenal'], story: 'Arsenal Transfer' },
  { id: 3, title: 'Real Madrid confirm contract extension talks', source: 'Marca', time: '1 giờ trước', status: 'error', duplicate: false, entities: ['Real Madrid', 'Jude Bellingham'], story: 'Real Madrid News' },
  { id: 4, title: 'Guardiola press conference transcript', source: 'The Athletic', time: '2 giờ trước', status: 'processing', duplicate: false, entities: ['Pep Guardiola', 'Man City'], story: 'Man City Planning' },
]

const StatusChip = ({ status }: { status: string }) => {
  const m: Record<string, { cls: string; label: string }> = {
    processed: { cls: 'bg-green-50 text-green-700', label: 'Đã xử lý' },
    processing: { cls: 'bg-blue-50 text-blue-700', label: 'Đang xử lý' },
    error: { cls: 'bg-red-50 text-red-600', label: 'Lỗi' },
    pending: { cls: 'bg-amber-50 text-amber-700', label: 'Chờ' },
  }
  const { cls, label } = m[status] ?? m.pending
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>{label}</span>
}

export default function AdminArticlesPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-[#111827] mb-6">Bài viết nguồn</h1>

      <div className="flex flex-wrap gap-3 mb-6">
        {['Nguồn', 'Trạng thái', 'Trùng lặp', 'Ngày'].map(f => (
          <select key={f} className="px-3 py-2 border border-[#E5E7EB] rounded-lg text-sm text-[#374151] bg-white focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30 focus:border-[#78A83D]">
            <option>{f}: Tất cả</option>
          </select>
        ))}
      </div>

      <div className="bg-white border border-[#E5E7EB] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E5E7EB] bg-[#F9FAFB]">
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Tiêu đề gốc</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider hidden sm:table-cell">Nguồn</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Trạng thái</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider hidden md:table-cell">Trùng lặp</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider hidden lg:table-cell">Thực thể</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider hidden lg:table-cell">Story</th>
                <th className="text-right px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5E7EB]">
              {sourceArticles.map(a => (
                <tr key={a.id} className="hover:bg-[#F9FAFB] transition-colors">
                  <td className="px-4 py-3">
                    <p className="font-medium text-[#111827] line-clamp-1">{a.title}</p>
                    <p className="text-xs text-[#9CA3AF] mt-0.5">{a.time}</p>
                  </td>
                  <td className="px-4 py-3 text-[#374151] hidden sm:table-cell">{a.source}</td>
                  <td className="px-4 py-3"><StatusChip status={a.status} /></td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    {a.duplicate ? <span className="text-xs text-amber-600 font-medium">Có</span> : <span className="text-xs text-[#9CA3AF]">Không</span>}
                  </td>
                  <td className="px-4 py-3 hidden lg:table-cell">
                    <div className="flex flex-wrap gap-1">
                      {a.entities.map(e => <span key={e} className="text-xs bg-[#F3F4F6] text-[#6B7280] px-1.5 py-0.5 rounded">{e}</span>)}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-[#6B7280] text-xs hidden lg:table-cell">{a.story}</td>
                  <td className="px-4 py-3 text-right">
                    <button className="px-2 py-1 text-xs text-[#78A83D] hover:bg-[#78A83D]/5 rounded transition-colors">Xem</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
