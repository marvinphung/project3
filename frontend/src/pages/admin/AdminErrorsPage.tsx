const errors = [
  { id: 1, item: 'marca.com', stage: 'Thu thập (Crawl)', category: 'Timeout', attempts: 3, last: '2 giờ trước', status: 'pending' },
  { id: 2, item: 'BBC Sport — Article #4821', stage: 'Nhận diện thực thể', category: 'NLP Error', attempts: 1, last: '4 giờ trước', status: 'retrying' },
  { id: 3, item: 'Story #892 Draft', stage: 'Tạo bản nháp (AI)', category: 'Generation Failed', attempts: 2, last: '6 giờ trước', status: 'pending' },
]

const StatusChip = ({ status }: { status: string }) => {
  const m: Record<string, string> = {
    pending: 'bg-red-50 text-red-600',
    retrying: 'bg-amber-50 text-amber-700',
    resolved: 'bg-green-50 text-green-700',
  }
  const l: Record<string, string> = { pending: 'Chờ xử lý', retrying: 'Đang thử lại', resolved: 'Đã xử lý' }
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${m[status]}`}>{l[status]}</span>
}

export default function AdminErrorsPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-[#111827] mb-6">Lỗi xử lý</h1>

      {errors.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white border border-[#E5E7EB] rounded-xl text-center">
          <div className="w-12 h-12 rounded-full bg-green-50 flex items-center justify-center mb-3">
            <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
          </div>
          <p className="font-medium text-[#374151]">Không có lỗi nào đang chờ xử lý</p>
        </div>
      ) : (
        <div className="bg-white border border-[#E5E7EB] rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#E5E7EB] bg-[#F9FAFB]">
                  <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Mục bị lỗi</th>
                  <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider hidden sm:table-cell">Giai đoạn</th>
                  <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Loại lỗi</th>
                  <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider hidden md:table-cell">Lần thử</th>
                  <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider hidden md:table-cell">Lần cuối</th>
                  <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Trạng thái</th>
                  <th className="text-right px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E7EB]">
                {errors.map(e => (
                  <tr key={e.id} className="hover:bg-[#F9FAFB] transition-colors">
                    <td className="px-4 py-3 font-medium text-[#111827]">{e.item}</td>
                    <td className="px-4 py-3 text-[#6B7280] hidden sm:table-cell">{e.stage}</td>
                    <td className="px-4 py-3"><span className="text-xs font-mono bg-[#FEF2F2] text-red-700 px-2 py-0.5 rounded">{e.category}</span></td>
                    <td className="px-4 py-3 text-[#374151] hidden md:table-cell">{e.attempts}</td>
                    <td className="px-4 py-3 text-[#6B7280] hidden md:table-cell">{e.last}</td>
                    <td className="px-4 py-3"><StatusChip status={e.status} /></td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button className="px-2 py-1 text-xs text-[#78A83D] hover:bg-[#78A83D]/5 rounded transition-colors">Thử lại</button>
                        <button className="px-2 py-1 text-xs text-[#6B7280] hover:bg-[#F3F4F6] rounded transition-colors">Bỏ qua</button>
                        <button className="px-2 py-1 text-xs text-[#6B7280] hover:bg-[#F3F4F6] rounded transition-colors">Xem chi tiết</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
