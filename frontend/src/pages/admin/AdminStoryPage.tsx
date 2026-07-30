const stories = [
  { id: 1, title: 'Arsenal theo đuổi tiền đạo trẻ trong kỳ chuyển nhượng', sources: 4, entities: ['Arsenal', 'Mikel Arteta'], status: 'active', level: 'multi', lastUpdate: '20 phút trước', draft: 'pending' },
  { id: 2, title: 'Real Madrid gia hạn hợp đồng cầu thủ trẻ', sources: 2, entities: ['Real Madrid', 'Jude Bellingham'], status: 'official', level: 'official', lastUpdate: '2 giờ trước', draft: 'approved' },
  { id: 3, title: 'Pep Guardiola kế hoạch mùa giải mới', sources: 5, entities: ['Man City', 'Pep Guardiola'], status: 'active', level: 'multi', lastUpdate: '3 giờ trước', draft: 'revision' },
  { id: 4, title: 'Liverpool thay đổi chiến thuật', sources: 2, entities: ['Liverpool', 'Arne Slot'], status: 'active', level: 'updating', lastUpdate: '4 giờ trước', draft: 'pending' },
]

const filters = ['Active', 'Official', 'Needs review', 'Possible duplicate']

const LevelChip = ({ level }: { level: string }) => {
  const m: Record<string, { cls: string; label: string }> = {
    multi: { cls: 'bg-amber-50 text-amber-700', label: 'Nhiều nguồn' },
    official: { cls: 'bg-green-50 text-green-700', label: 'Chính thức' },
    updating: { cls: 'bg-blue-50 text-blue-700', label: 'Đang cập nhật' },
  }
  const { cls, label } = m[level] ?? m.updating
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>{label}</span>
}

export default function AdminStoryPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-[#111827] mb-4">Story</h1>
      <div className="flex gap-2 mb-6 overflow-x-auto pb-1">
        {filters.map(f => (
          <button key={f} className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${f === 'Active' ? 'bg-[#78A83D] text-white border-[#78A83D]' : 'border-[#E5E7EB] text-[#6B7280] hover:border-[#78A83D] hover:text-[#78A83D]'}`}>{f}</button>
        ))}
      </div>
      <div className="bg-white border border-[#E5E7EB] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E5E7EB] bg-[#F9FAFB]">
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Tiêu đề làm việc</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider hidden sm:table-cell">Bài nguồn</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider hidden md:table-cell">Xác nhận</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider hidden md:table-cell">Cập nhật</th>
                <th className="text-right px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5E7EB]">
              {stories.map(s => (
                <tr key={s.id} className="hover:bg-[#F9FAFB] transition-colors">
                  <td className="px-4 py-3">
                    <p className="font-medium text-[#111827] line-clamp-1">{s.title}</p>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {s.entities.map(e => <span key={e} className="text-xs bg-[#F3F4F6] text-[#6B7280] px-1.5 py-0.5 rounded">{e}</span>)}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-[#374151] hidden sm:table-cell">{s.sources}</td>
                  <td className="px-4 py-3 hidden md:table-cell"><LevelChip level={s.level} /></td>
                  <td className="px-4 py-3 text-[#6B7280] hidden md:table-cell">{s.lastUpdate}</td>
                  <td className="px-4 py-3 text-right">
                    <button className="px-3 py-1.5 text-xs text-[#78A83D] border border-[#78A83D]/30 rounded-lg hover:bg-[#78A83D]/5 transition-colors">Xem</button>
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
