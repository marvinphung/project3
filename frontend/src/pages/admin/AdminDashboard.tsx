import { Link } from 'react-router'

const metrics = [
  { label: 'Bài thu thập hôm nay', value: '247', delta: '+12%', icon: 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z', color: 'text-blue-600 bg-blue-50' },
  { label: 'Story mới', value: '18', delta: '+3', icon: 'M13 10V3L4 14h7v7l9-11h-7z', color: 'text-purple-600 bg-purple-50' },
  { label: 'Bản nháp cần duyệt', value: '5', delta: '', icon: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z', color: 'text-amber-600 bg-amber-50' },
  { label: 'Bài đã xuất bản', value: '1,842', delta: '+8 hôm nay', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z', color: 'text-green-600 bg-green-50' },
  { label: 'Lỗi đang chờ', value: '3', delta: '', icon: 'M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z', color: 'text-red-600 bg-red-50' },
]

const pipeline = ['Thu thập', 'Chuẩn hóa', 'Nhận diện', 'Nhóm story', 'Tạo bản nháp', 'Xuất bản']

const recent = [
  { type: 'draft', msg: 'Bản nháp mới được tạo: "Arsenal tăng tốc đàm phán..."', time: '5 phút trước' },
  { type: 'crawl', msg: 'Hoàn thành thu thập từ BBC Sport: 12 bài mới', time: '15 phút trước' },
  { type: 'story', msg: 'Story mới được nhóm: Real Madrid gia hạn hợp đồng', time: '32 phút trước' },
  { type: 'publish', msg: 'Xuất bản: "Pep Guardiola lên tiếng về kế hoạch..."', time: '1 giờ trước' },
  { type: 'error', msg: 'Lỗi crawl: marca.com — timeout sau 3 lần thử', time: '2 giờ trước' },
]

export default function AdminDashboard() {
  return (
    <div className="p-6 max-w-[1200px]">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#111827]">Tổng quan hệ thống</h1>
        <p className="text-sm text-[#6B7280] mt-1">Thứ Tư, 30 tháng 7 năm 2025</p>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
        {metrics.map(m => (
          <div key={m.label} className="bg-white border border-[#E5E7EB] rounded-xl p-4">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center mb-3 ${m.color}`}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={m.icon} /></svg>
            </div>
            <p className="text-2xl font-bold text-[#111827]">{m.value}</p>
            <p className="text-xs text-[#6B7280] mt-0.5">{m.label}</p>
            {m.delta && <p className="text-xs text-[#78A83D] font-medium mt-1">{m.delta}</p>}
          </div>
        ))}
      </div>

      {/* Pipeline */}
      <div className="bg-white border border-[#E5E7EB] rounded-xl p-5 mb-6">
        <h2 className="text-sm font-bold text-[#111827] mb-4">Pipeline xử lý</h2>
        <div className="flex items-center gap-0 overflow-x-auto">
          {pipeline.map((stage, i) => (
            <div key={stage} className="flex items-center flex-shrink-0">
              <div className={`px-3 py-2 rounded-lg text-xs font-medium ${i < 4 ? 'bg-[#78A83D]/10 text-[#78A83D]' : i === 4 ? 'bg-amber-50 text-amber-700' : 'bg-[#F3F4F6] text-[#6B7280]'}`}>
                {stage}
                {i < 3 && <span className="ml-2 text-[10px] font-normal opacity-70">✓</span>}
                {i === 3 && <span className="ml-2 text-[10px] font-normal opacity-70">12</span>}
                {i === 4 && <span className="ml-2 text-[10px] font-normal opacity-70">5</span>}
              </div>
              {i < pipeline.length - 1 && <span className="text-[#D1D5DB] mx-1 text-sm">→</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Recent activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white border border-[#E5E7EB] rounded-xl p-5">
          <h2 className="text-sm font-bold text-[#111827] mb-4">Hoạt động gần đây</h2>
          <div className="space-y-3">
            {recent.map((r, i) => (
              <div key={i} className="flex items-start gap-3">
                <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${r.type === 'error' ? 'bg-red-400' : r.type === 'publish' ? 'bg-[#78A83D]' : r.type === 'draft' ? 'bg-amber-400' : 'bg-blue-400'}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-[#374151] leading-snug">{r.msg}</p>
                  <p className="text-xs text-[#9CA3AF] mt-0.5">{r.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white border border-[#E5E7EB] rounded-xl p-5">
          <h2 className="text-sm font-bold text-[#111827] mb-4">Thao tác nhanh</h2>
          <div className="space-y-2">
            <Link to="/admin/ban-nhap" className="flex items-center justify-between p-3 bg-[#F9FAFB] rounded-lg hover:bg-[#F3F4F6] transition-colors group">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 bg-amber-100 text-amber-700 rounded text-[10px] font-bold flex items-center justify-center">5</span>
                <span className="text-sm text-[#374151]">Bản nháp cần duyệt</span>
              </div>
              <svg className="w-4 h-4 text-[#9CA3AF] group-hover:text-[#78A83D]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
            </Link>
            <Link to="/admin/loi-xu-ly" className="flex items-center justify-between p-3 bg-[#F9FAFB] rounded-lg hover:bg-[#F3F4F6] transition-colors group">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 bg-red-100 text-red-600 rounded text-[10px] font-bold flex items-center justify-center">3</span>
                <span className="text-sm text-[#374151]">Lỗi chờ xử lý</span>
              </div>
              <svg className="w-4 h-4 text-[#9CA3AF] group-hover:text-[#78A83D]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
            </Link>
            <Link to="/admin/story" className="flex items-center justify-between p-3 bg-[#F9FAFB] rounded-lg hover:bg-[#F3F4F6] transition-colors group">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 bg-purple-100 text-purple-700 rounded text-[10px] font-bold flex items-center justify-center">18</span>
                <span className="text-sm text-[#374151]">Story đang hoạt động</span>
              </div>
              <svg className="w-4 h-4 text-[#9CA3AF] group-hover:text-[#78A83D]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
