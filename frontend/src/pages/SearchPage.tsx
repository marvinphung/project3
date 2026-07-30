import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { articles, players, clubs, coaches } from '../data/mock'

const tabs = ['Tất cả', 'Tin tức', 'Cầu thủ', 'CLB', 'HLV']

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [query, setQuery] = useState(searchParams.get('q') ?? '')
  const [activeTab, setActiveTab] = useState('Tất cả')

  const q = (searchParams.get('q') ?? '').toLowerCase()

  const matchedArticles = articles.filter(a =>
    a.headline.toLowerCase().includes(q) || a.summary.toLowerCase().includes(q)
  )
  const matchedPlayers = players.filter(p => p.name.toLowerCase().includes(q))
  const matchedClubs = clubs.filter(c => c.name.toLowerCase().includes(q))
  const matchedCoaches = coaches.filter(c => c.name.toLowerCase().includes(q))

  const totalResults = matchedArticles.length + matchedPlayers.length + matchedClubs.length + matchedCoaches.length

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) setSearchParams({ q: query.trim() })
  }

  return (
    <div className="max-w-[1280px] mx-auto px-4 sm:px-6 py-8">
      <h1 className="text-2xl font-bold text-[#111827] mb-6">
        {q ? `Kết quả tìm kiếm cho "${q}"` : 'Tìm kiếm'}
      </h1>

      <form onSubmit={handleSearch} className="mb-6">
        <div className="relative max-w-2xl">
          <svg className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#9CA3AF]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Tìm tin, cầu thủ, CLB hoặc HLV..."
            className="w-full pl-12 pr-4 py-3 text-base border border-[#E5E7EB] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30 focus:border-[#78A83D] bg-white placeholder-[#9CA3AF]"
          />
        </div>
      </form>

      {q && (
        <>
          <div className="flex gap-1 mb-8 overflow-x-auto pb-1">
            {tabs.map(t => (
              <button
                key={t}
                onClick={() => setActiveTab(t)}
                className={`flex-shrink-0 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === t ? 'bg-[#78A83D] text-white' : 'text-[#374151] hover:bg-[#F3F4F6]'}`}
              >
                {t}
              </button>
            ))}
          </div>

          {totalResults === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-14 h-14 rounded-full bg-[#F3F4F6] flex items-center justify-center mb-4">
                <svg className="w-7 h-7 text-[#9CA3AF]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
              </div>
              <h2 className="text-lg font-semibold text-[#374151] mb-2">Không tìm thấy kết quả phù hợp</h2>
              <p className="text-sm text-[#6B7280]">Thử kiểm tra lại từ khóa hoặc tìm bằng tên khác.</p>
            </div>
          ) : (
            <div className="space-y-10">
              {(activeTab === 'Tất cả' || activeTab === 'CLB') && matchedClubs.length > 0 && (
                <section>
                  <h2 className="text-sm font-semibold text-[#6B7280] uppercase tracking-wider mb-4">CLB</h2>
                  <div className="space-y-2">
                    {matchedClubs.map(c => (
                      <Link key={c.id} to={`/clb/${c.id}`} className="flex items-center gap-3 p-3 bg-white border border-[#E5E7EB] rounded-lg hover:border-[#78A83D]/40 transition-colors">
                        <div className="w-9 h-9 rounded-full bg-[#F3F4F6] flex items-center justify-center text-lg flex-shrink-0">{c.crest}</div>
                        <div>
                          <p className="font-medium text-[#111827] text-sm">{c.name}</p>
                          <p className="text-xs text-[#6B7280]">{c.league} · {c.articles} bài viết</p>
                        </div>
                        <span className="ml-auto text-xs text-[#9CA3AF] bg-[#F3F4F6] px-2 py-0.5 rounded-full">CLB</span>
                      </Link>
                    ))}
                  </div>
                </section>
              )}

              {(activeTab === 'Tất cả' || activeTab === 'Cầu thủ') && matchedPlayers.length > 0 && (
                <section>
                  <h2 className="text-sm font-semibold text-[#6B7280] uppercase tracking-wider mb-4">Cầu thủ</h2>
                  <div className="space-y-2">
                    {matchedPlayers.map(p => (
                      <Link key={p.id} to={`/cau-thu/${p.id}`} className="flex items-center gap-3 p-3 bg-white border border-[#E5E7EB] rounded-lg hover:border-[#78A83D]/40 transition-colors">
                        <img src={p.img} alt={p.name} className="w-9 h-9 rounded-full object-cover bg-[#E5E7EB] flex-shrink-0" />
                        <div>
                          <p className="font-medium text-[#111827] text-sm">{p.name}</p>
                          <p className="text-xs text-[#6B7280]">{p.club} · {p.articles} bài viết</p>
                        </div>
                        <span className="ml-auto text-xs text-[#9CA3AF] bg-[#F3F4F6] px-2 py-0.5 rounded-full">Cầu thủ</span>
                      </Link>
                    ))}
                  </div>
                </section>
              )}

              {(activeTab === 'Tất cả' || activeTab === 'HLV') && matchedCoaches.length > 0 && (
                <section>
                  <h2 className="text-sm font-semibold text-[#6B7280] uppercase tracking-wider mb-4">HLV</h2>
                  <div className="space-y-2">
                    {matchedCoaches.map(c => (
                      <Link key={c.id} to={`/hlv/${c.id}`} className="flex items-center gap-3 p-3 bg-white border border-[#E5E7EB] rounded-lg hover:border-[#78A83D]/40 transition-colors">
                        <img src={c.img} alt={c.name} className="w-9 h-9 rounded-full object-cover bg-[#E5E7EB] flex-shrink-0" />
                        <div>
                          <p className="font-medium text-[#111827] text-sm">{c.name}</p>
                          <p className="text-xs text-[#6B7280]">{c.club} · {c.articles} bài viết</p>
                        </div>
                        <span className="ml-auto text-xs text-[#9CA3AF] bg-[#F3F4F6] px-2 py-0.5 rounded-full">HLV</span>
                      </Link>
                    ))}
                  </div>
                </section>
              )}

              {(activeTab === 'Tất cả' || activeTab === 'Tin tức') && matchedArticles.length > 0 && (
                <section>
                  <h2 className="text-sm font-semibold text-[#6B7280] uppercase tracking-wider mb-4">Tin tức</h2>
                  <div className="space-y-2">
                    {matchedArticles.map(a => (
                      <Link key={a.id} to={`/bai-viet/${a.id}`} className="flex items-center gap-3 p-3 bg-white border border-[#E5E7EB] rounded-lg hover:border-[#78A83D]/40 transition-colors">
                        <img src={a.img} alt={a.headline} className="w-14 h-10 rounded object-cover bg-[#E5E7EB] flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-[#111827] text-sm line-clamp-1">{a.headline}</p>
                          <p className="text-xs text-[#6B7280]">{a.time} · {a.sources} nguồn</p>
                        </div>
                        <span className="ml-auto text-xs text-[#9CA3AF] bg-[#F3F4F6] px-2 py-0.5 rounded-full flex-shrink-0">Tin</span>
                      </Link>
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}
        </>
      )}

      {!q && (
        <div className="flex flex-col items-center justify-center py-20 text-center text-[#9CA3AF]">
          <svg className="w-12 h-12 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
          <p className="text-base">Nhập từ khóa để tìm kiếm tin tức, cầu thủ, CLB hoặc HLV.</p>
        </div>
      )}
    </div>
  )
}
