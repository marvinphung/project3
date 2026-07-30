import { useState } from 'react'

const drafts = [
  { id: 1, headline: 'Arsenal tăng tốc đàm phán trong thương vụ chiêu mộ tiền đạo trẻ', story: 'Arsenal Transfer Saga', status: 'pending', warning: true, time: '20 phút trước' },
  { id: 2, headline: 'Pep Guardiola lên tiếng về kế hoạch nhân sự mùa giải mới', story: 'Man City Squad Planning', status: 'pending', warning: false, time: '1 giờ trước' },
  { id: 3, headline: 'Barcelona công bố danh sách cầu thủ tham dự chuyến du đấu hè', story: 'Barcelona Pre-season', status: 'revision', warning: false, time: '3 giờ trước' },
  { id: 4, headline: 'Kylian Mbappé chia sẻ về mục tiêu đầy tham vọng trong mùa giải mới', story: 'Mbappe at Real Madrid', status: 'pending', warning: true, time: '5 giờ trước' },
  { id: 5, headline: 'Liverpool chuẩn bị thay đổi hệ thống thi đấu trong trận sắp tới', story: 'Liverpool Tactics', status: 'approved', warning: false, time: '6 giờ trước' },
]

const StatusBadge = ({ status }: { status: string }) => {
  const m: Record<string, { cls: string; label: string }> = {
    pending: { cls: 'bg-amber-50 text-amber-700', label: 'Chờ duyệt' },
    approved: { cls: 'bg-green-50 text-green-700', label: 'Đã duyệt' },
    revision: { cls: 'bg-blue-50 text-blue-700', label: 'Cần chỉnh sửa' },
    rejected: { cls: 'bg-red-50 text-red-600', label: 'Từ chối' },
  }
  const { cls, label } = m[status] ?? m.pending
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>{label}</span>
}

export default function AdminDraftPage() {
  const [selected, setSelected] = useState<typeof drafts[0] | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)

  const draft = selected ?? drafts[0]

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-[#111827] mb-6">Bản nháp</h1>

      {selected ? (
        /* Draft editor */
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-6">
          {/* Left: editor */}
          <div className="bg-white border border-[#E5E7EB] rounded-xl p-6">
            <button onClick={() => setSelected(null)} className="flex items-center gap-1 text-sm text-[#6B7280] hover:text-[#111827] mb-5 transition-colors">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
              Quay lại
            </button>
            <div className="mb-4">
              <label className="block text-xs font-semibold text-[#6B7280] uppercase tracking-wider mb-1.5">Tiêu đề</label>
              <textarea className="w-full px-3 py-2 border border-[#E5E7EB] rounded-lg text-xl font-bold text-[#111827] resize-none focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30 focus:border-[#78A83D] leading-snug" rows={2} defaultValue={draft.headline} />
            </div>
            <div className="mb-4">
              <label className="block text-xs font-semibold text-[#6B7280] uppercase tracking-wider mb-1.5">Tóm tắt</label>
              <textarea className="w-full px-3 py-2 border border-[#E5E7EB] rounded-lg text-sm text-[#374151] resize-none focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30 focus:border-[#78A83D]" rows={3} defaultValue="Nhiều nguồn cho biết Arsenal đã đạt tiến triển trong đàm phán với cầu thủ, nhưng hai câu lạc bộ vẫn chưa thống nhất mức phí chuyển nhượng." />
            </div>
            <div className="mb-5">
              <label className="block text-xs font-semibold text-[#6B7280] uppercase tracking-wider mb-1.5">Nội dung bài viết</label>
              <div className="border border-[#E5E7EB] rounded-lg p-3 min-h-[300px]">
                <textarea className="w-full text-sm text-[#374151] leading-relaxed resize-none focus:outline-none min-h-[280px]" defaultValue={"Arsenal đang đẩy mạnh các cuộc đàm phán với đại diện của tiền đạo trẻ mà họ nhắm tới trong kỳ chuyển nhượng hè này. Theo thông tin từ nhiều nguồn uy tín, câu lạc bộ London đã có những tiến triển đáng kể trong việc thỏa thuận các điều khoản cá nhân với cầu thủ.\n\nTuy nhiên, trở ngại lớn nhất vẫn là mức phí chuyển nhượng. Câu lạc bộ chủ quản hiện tại yêu cầu một khoản phí lên đến 80 triệu euro, trong khi Arsenal chỉ sẵn sàng trả tối đa 65 triệu euro. Hai bên hiện đang tiếp tục thương lượng.\n\nHLV Mikel Arteta đã xác nhận rằng đội bóng đang tìm kiếm sự tăng cường trong mùa hè này, nhưng từ chối tiết lộ cụ thể về tên cầu thủ hay câu lạc bộ liên quan."} />
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-wrap gap-2">
              <button className="px-4 py-2 border border-[#E5E7EB] text-[#374151] rounded-lg text-sm font-medium hover:bg-[#F3F4F6] transition-colors">Lưu bản nháp</button>
              <button className="px-4 py-2 border border-[#E5E7EB] text-[#374151] rounded-lg text-sm font-medium hover:bg-[#F3F4F6] transition-colors">Yêu cầu tạo lại</button>
              <button className="px-4 py-2 bg-[#2E7D32] text-white rounded-lg text-sm font-semibold hover:bg-[#246328] transition-colors">Phê duyệt</button>
              <button className="px-4 py-2 border border-red-200 text-red-600 rounded-lg text-sm font-medium hover:bg-red-50 transition-colors">Từ chối</button>
              <button
                onClick={() => setShowConfirm(true)}
                className="px-4 py-2 bg-[#78A83D] text-white rounded-lg text-sm font-semibold hover:bg-[#6a9435] transition-colors"
              >
                Xuất bản
              </button>
            </div>
          </div>

          {/* Right: review panel */}
          <div className="space-y-4">
            <div className="bg-white border border-[#E5E7EB] rounded-xl p-4">
              <h3 className="text-sm font-bold text-[#111827] mb-3">Thông tin bản nháp</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-[#6B7280]">Trạng thái</span><StatusBadge status={draft.status} /></div>
                <div className="flex justify-between"><span className="text-[#6B7280]">Story</span><span className="text-[#374151] text-right text-xs">{draft.story}</span></div>
                <div className="flex justify-between"><span className="text-[#6B7280]">Tạo lúc</span><span className="text-[#374151]">{draft.time}</span></div>
              </div>
            </div>

            {draft.warning && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                <div className="flex items-start gap-2">
                  <svg className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                  <p className="text-xs text-amber-800">Một thông tin trong bài chưa có đủ nguồn tham khảo.</p>
                </div>
              </div>
            )}

            <div className="bg-white border border-[#E5E7EB] rounded-xl p-4">
              <h3 className="text-sm font-bold text-[#111827] mb-3">Nguồn hỗ trợ</h3>
              <div className="space-y-2">
                {['BBC Sport', 'Sky Sports', 'The Athletic', 'Fabrizio Romano'].map(s => (
                  <div key={s} className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#78A83D] flex-shrink-0" />
                    <span className="text-xs text-[#374151]">{s}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Draft list */
        <div className="bg-white border border-[#E5E7EB] rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#E5E7EB] bg-[#F9FAFB]">
                  <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Tiêu đề</th>
                  <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider hidden sm:table-cell">Story</th>
                  <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider">Trạng thái</th>
                  <th className="text-left px-4 py-3 font-semibold text-[#374151] text-xs uppercase tracking-wider hidden md:table-cell">Thời gian</th>
                  <th className="text-right px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E7EB]">
                {drafts.map(d => (
                  <tr key={d.id} className="hover:bg-[#F9FAFB] transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-start gap-2">
                        {d.warning && <svg className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>}
                        <span className="font-medium text-[#111827] line-clamp-2 leading-snug">{d.headline}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-[#6B7280] hidden sm:table-cell">{d.story}</td>
                    <td className="px-4 py-3"><StatusBadge status={d.status} /></td>
                    <td className="px-4 py-3 text-[#6B7280] hidden md:table-cell">{d.time}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => setSelected(d)} className="px-3 py-1.5 text-xs font-medium text-[#78A83D] border border-[#78A83D]/30 rounded-lg hover:bg-[#78A83D]/5 transition-colors">
                        Xem & duyệt
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Confirm publish modal */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowConfirm(false)} />
          <div className="relative bg-white rounded-xl shadow-xl w-full max-w-sm p-6 text-center">
            <div className="w-12 h-12 rounded-full bg-[#78A83D]/10 flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-[#78A83D]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
            </div>
            <h2 className="font-bold text-[#111827] mb-2">Xác nhận xuất bản</h2>
            <p className="text-sm text-[#6B7280] mb-6">Bài viết sẽ được công bố ngay lập tức cho tất cả người dùng. Bạn có chắc chắn muốn xuất bản không?</p>
            <div className="flex gap-3">
              <button onClick={() => setShowConfirm(false)} className="flex-1 py-2 border border-[#E5E7EB] text-[#374151] rounded-lg text-sm font-medium hover:bg-[#F3F4F6] transition-colors">Hủy</button>
              <button onClick={() => setShowConfirm(false)} className="flex-1 py-2 bg-[#78A83D] text-white rounded-lg text-sm font-semibold hover:bg-[#6a9435] transition-colors">Xuất bản</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
