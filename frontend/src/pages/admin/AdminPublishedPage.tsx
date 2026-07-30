import { Link } from 'react-router'

const published = [
  { id: 1, headline: 'Pep Guardiola lên tiếng về kế hoạch nhân sự mùa giải mới', time: '1 giờ trước', story: 'Man City Planning', editor: 'Minh Tuấn', revision: 1, views: '1.2k' },
  { id: 2, headline: 'Real Madrid xác nhận gia hạn hợp đồng với một cầu thủ trẻ', time: '3 giờ trước', story: 'Real Madrid News', editor: 'Hà Linh', revision: 2, views: '3.8k' },
  { id: 3, headline: 'Liverpool chuẩn bị thay đổi hệ thống thi đấu', time: '5 giờ trước', story: 'Liverpool Tactics', editor: 'Quang Huy', revision: 1, views: '890' },
]

export default function AdminPublishedPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-[#111827] mb-6">Bài đã xuất bản</h1>
      <div className="bg-white border border-[#E5E7EB] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E5E7EB] bg-[#F9FAFB]">
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Tiêu đề</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider hidden sm:table-cell">Xuất bản</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider hidden md:table-cell">Editor</th>
                <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider hidden md:table-cell">Lượt xem</th>
                <th className="text-right px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5E7EB]">
              {published.map(p => (
                <tr key={p.id} className="hover:bg-[#F9FAFB] transition-colors">
                  <td className="px-4 py-3 font-medium text-[#111827] line-clamp-1">{p.headline}</td>
                  <td className="px-4 py-3 text-[#6B7280] hidden sm:table-cell">{p.time}</td>
                  <td className="px-4 py-3 text-[#374151] hidden md:table-cell">{p.editor}</td>
                  <td className="px-4 py-3 text-[#374151] font-medium hidden md:table-cell">{p.views}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Link to="/bai-viet/arsenal-transfer-1" className="px-2 py-1 text-xs text-[#78A83D] hover:bg-[#78A83D]/5 rounded transition-colors">Xem bài</Link>
                      <button className="px-2 py-1 text-xs text-[#6B7280] hover:bg-[#F3F4F6] rounded transition-colors">Chỉnh sửa</button>
                      <button className="px-2 py-1 text-xs text-red-500 hover:bg-red-50 rounded transition-colors">Gỡ xuất bản</button>
                    </div>
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
