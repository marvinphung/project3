import { useState } from 'react'
import { Link } from 'react-router'
import { clubs } from '../data/mock'

export default function ClubsPage() {
  const [search, setSearch] = useState('')
  const filtered = clubs.filter(c => c.name.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="max-w-[1280px] mx-auto px-4 sm:px-6 py-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold text-[#111827] mb-1">Câu lạc bộ</h1>
          <p className="text-[#6B7280] text-sm">Theo dõi tin tức từ các câu lạc bộ hàng đầu thế giới.</p>
        </div>
        <div className="relative w-full sm:w-64">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9CA3AF]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
          <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Tìm câu lạc bộ..." className="w-full pl-9 pr-4 py-2 text-sm border border-[#E5E7EB] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30 focus:border-[#78A83D] bg-white placeholder-[#9CA3AF]" />
        </div>
      </div>

      <div className="mb-10">
        <div className="flex items-center gap-3 mb-5">
          <span className="w-1 h-5 rounded bg-[#78A83D]" />
          <h2 className="text-lg font-bold text-[#111827]">CLB nổi bật</h2>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-4">
          {clubs.map(c => (
            <Link key={c.id} to={`/clb/${c.id}`} className="group flex flex-col items-center text-center p-4 bg-white border border-[#E5E7EB] rounded-xl hover:border-[#78A83D]/40 hover:shadow-sm transition-all">
              <div className="w-12 h-12 rounded-full bg-[#F3F4F6] flex items-center justify-center text-2xl mb-3">{c.crest}</div>
              <h3 className="text-xs font-semibold text-[#111827] group-hover:text-[#78A83D] transition-colors leading-tight">{c.name}</h3>
              <p className="text-[10px] text-[#6B7280] mt-0.5">{c.league}</p>
            </Link>
          ))}
        </div>
      </div>

      <div>
        <div className="flex items-center gap-3 mb-5">
          <span className="w-1 h-5 rounded bg-[#78A83D]" />
          <h2 className="text-lg font-bold text-[#111827]">CLB có tin mới</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {filtered.map(c => (
            <Link key={c.id} to={`/clb/${c.id}`} className="group bg-white border border-[#E5E7EB] rounded-xl p-4 hover:border-[#78A83D]/40 hover:shadow-sm transition-all">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-full bg-[#F3F4F6] flex items-center justify-center text-xl flex-shrink-0">{c.crest}</div>
                <div>
                  <h3 className="font-semibold text-[#111827] text-sm group-hover:text-[#78A83D] transition-colors">{c.name}</h3>
                  <p className="text-xs text-[#6B7280]">{c.league}</p>
                </div>
              </div>
              <p className="text-xs text-[#9CA3AF]"><span className="font-medium text-[#374151]">{c.articles}</span> bài viết gần đây</p>
            </Link>
          ))}
        </div>
        {filtered.length === 0 && (
          <p className="text-[#6B7280] text-center py-12">Không tìm thấy câu lạc bộ phù hợp.</p>
        )}
      </div>
    </div>
  )
}
