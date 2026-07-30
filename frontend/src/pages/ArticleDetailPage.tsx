import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { articles, timeline, sources, clubs, players, coaches } from '../data/mock'
import { EntityChips, StatusBadge, MediumNewsCard } from '../components/ui'

export default function ArticleDetailPage() {
  const { id } = useParams()
  const article = articles.find(a => a.id === id) ?? articles[0]
  const related = articles.filter(a => a.id !== article.id).slice(0, 3)
  const [timelineOpen, setTimelineOpen] = useState(true)

  const relatedClub = clubs.find(c => article.entities.find(e => e.id === c.id))
  const relatedPlayer = players.find(p => article.entities.find(e => e.id === p.id))

  return (
    <div className="max-w-[1280px] mx-auto px-4 sm:px-6 py-8">
      <div className="max-w-[760px] mx-auto">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-[#6B7280] mb-6">
          <Link to="/" className="hover:text-[#78A83D]">Trang chủ</Link>
          <span>/</span>
          <Link to="/tin-moi" className="hover:text-[#78A83D]">Tin mới</Link>
          <span>/</span>
          <span className="text-[#374151] truncate">Bài viết</span>
        </div>

        {/* Category + status */}
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-semibold text-[#78A83D] uppercase tracking-wider">Chuyển nhượng</span>
          {article.status && <StatusBadge status={article.status} />}
        </div>

        {/* Headline */}
        <h1 className="text-3xl sm:text-4xl font-bold text-[#111827] leading-tight mb-4">
          {article.headline}
        </h1>

        {/* Summary */}
        <p className="text-lg text-[#374151] leading-relaxed mb-4">{article.summary}</p>

        {/* Meta */}
        <div className="flex items-center gap-3 flex-wrap mb-2">
          <p className="text-sm text-[#6B7280]">Cập nhật {article.time} · Tổng hợp từ <strong className="text-[#374151]">{article.sources} nguồn</strong></p>
        </div>
        <div className="mb-6">
          <EntityChips entities={article.entities} />
        </div>

        {/* Cover image */}
        <div className="relative aspect-[16/9] rounded-xl overflow-hidden bg-[#E5E7EB] mb-8">
          <img src={article.img} alt={article.headline} className="w-full h-full object-cover" />
        </div>

        {/* Body */}
        <div className="prose-like space-y-5 mb-10">
          {(article.body && article.body.length > 0 ? article.body : [
            'Arsenal đang đẩy mạnh các cuộc đàm phán với đại diện của tiền đạo trẻ mà họ nhắm tới trong kỳ chuyển nhượng hè này. Theo thông tin từ nhiều nguồn uy tín, câu lạc bộ London đã có những tiến triển đáng kể.',
            'Tuy nhiên, trở ngại lớn nhất vẫn là mức phí chuyển nhượng. Câu lạc bộ chủ quản yêu cầu khoản phí lên đến 80 triệu euro, trong khi Arsenal chỉ sẵn sàng trả tối đa 65 triệu euro.',
            'HLV Mikel Arteta đã xác nhận rằng đội bóng đang tìm kiếm sự tăng cường, nhưng từ chối tiết lộ cụ thể về tên cầu thủ.',
          ]).map((p, i) => (
            <p key={i} className="text-base sm:text-[17px] text-[#1F2937] leading-[1.75]">{p}</p>
          ))}

          <h2 className="text-xl font-bold text-[#111827] mt-8 mb-3">Diễn biến tiếp theo</h2>
          <p className="text-base sm:text-[17px] text-[#1F2937] leading-[1.75]">
            Thương vụ này dự kiến sẽ ngã ngũ trong vòng hai tuần tới khi cửa sổ chuyển nhượng sắp đóng lại. Arsenal cần ít nhất một tiền đạo mới để cạnh tranh ở Premier League và Champions League mùa tới.
          </p>

          {/* Pull quote */}
          <blockquote className="border-l-4 border-[#78A83D] pl-5 py-1 my-6">
            <p className="text-lg italic text-[#374151] leading-relaxed">"Chúng tôi đang làm việc rất chăm chỉ trong kỳ chuyển nhượng này." — Mikel Arteta</p>
          </blockquote>
        </div>

        <hr className="border-[#E5E7EB] my-8" />

        {/* Related entities */}
        <section className="mb-8">
          <h3 className="text-base font-bold text-[#111827] mb-4">Liên quan</h3>
          <div className="flex flex-wrap gap-3">
            {article.entities.map(e => (
              <Link
                key={e.id}
                to={e.type === 'club' ? `/clb/${e.id}` : e.type === 'player' ? `/cau-thu/${e.id}` : `/hlv/${e.id}`}
                className="flex items-center gap-2.5 bg-white border border-[#E5E7EB] rounded-lg px-3 py-2 hover:border-[#78A83D]/40 transition-colors"
              >
                <span className="w-8 h-8 rounded-full bg-[#F3F4F6] flex items-center justify-center text-xs font-bold text-[#6B7280]">
                  {e.name.charAt(0)}
                </span>
                <div>
                  <p className="text-sm font-medium text-[#111827]">{e.name}</p>
                  <p className="text-xs text-[#6B7280]">{e.type === 'club' ? 'CLB' : e.type === 'player' ? 'Cầu thủ' : 'HLV'}</p>
                </div>
              </Link>
            ))}
          </div>
        </section>

        {/* Timeline */}
        <section className="mb-8">
          <button
            onClick={() => setTimelineOpen(!timelineOpen)}
            className="flex items-center justify-between w-full mb-4 group"
          >
            <h3 className="text-base font-bold text-[#111827]">Diễn biến câu chuyện</h3>
            <svg className={`w-5 h-5 text-[#6B7280] transition-transform ${timelineOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
          </button>
          {timelineOpen && (
            <div className="relative pl-6">
              <div className="absolute left-2 top-2 bottom-2 w-px bg-[#E5E7EB]" />
              {timeline.map((item, i) => (
                <div key={i} className="relative mb-5 last:mb-0">
                  <div className={`absolute -left-4 top-1.5 w-3 h-3 rounded-full border-2 ${item.current ? 'bg-[#78A83D] border-[#78A83D]' : 'bg-white border-[#D1D5DB]'}`} />
                  <div className="flex items-baseline gap-3">
                    <span className="text-xs font-mono text-[#6B7280] flex-shrink-0">{item.time}</span>
                    <p className="text-sm text-[#374151]">{item.event}</p>
                  </div>
                  <p className="text-xs text-[#9CA3AF] mt-0.5 ml-10">{item.sources} nguồn</p>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Sources */}
        <section className="mb-8">
          <h3 className="text-base font-bold text-[#111827] mb-4">Nguồn tham khảo</h3>
          <div className="space-y-3">
            {sources.map(s => (
              <a key={s.id} href={s.url} className="flex items-center justify-between p-3 bg-white border border-[#E5E7EB] rounded-lg hover:border-[#78A83D]/40 transition-colors group">
                <div>
                  <p className="text-xs font-semibold text-[#78A83D] mb-0.5">{s.name}</p>
                  <p className="text-sm text-[#374151] group-hover:text-[#111827]">{s.title}</p>
                  <p className="text-xs text-[#9CA3AF] mt-0.5">{s.time}</p>
                </div>
                <svg className="w-4 h-4 text-[#9CA3AF] flex-shrink-0 ml-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
              </a>
            ))}
          </div>
        </section>

        {/* Related news */}
        <section>
          <h3 className="text-base font-bold text-[#111827] mb-4">Tin liên quan</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {related.map(a => (
              <div key={a.id}>
                <MediumNewsCard article={a} />
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
