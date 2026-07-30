import { useState } from 'react'
import { Link } from 'react-router'
import { players } from '../data/mock'

function PlayerCard({ player }: { player: typeof players[0] }) {
  return (
    <Link to={`/cau-thu/${player.id}`} className="group bg-white border border-[#E5E7EB] rounded-xl p-4 hover:border-[#78A83D]/40 hover:shadow-sm transition-all">
      <div className="flex items-center gap-3 mb-3">
        <img src={player.img} alt={player.name} className="w-12 h-12 rounded-full object-cover bg-[#E5E7EB]" />
        <div>
          <h3 className="font-semibold text-[#111827] text-sm group-hover:text-[#78A83D] transition-colors">{player.name}</h3>
          <p className="text-xs text-[#6B7280]">{player.position}</p>
        </div>
      </div>
      <p className="text-xs text-[#6B7280] mb-2">{player.club}</p>
      <p className="text-xs text-[#9CA3AF]"><span className="font-medium text-[#374151]">{player.articles}</span> bài viết gần đây</p>
    </Link>
  )
}

export default function PlayersPage() {
  const [search, setSearch] = useState('')
  const filtered = players.filter(p => p.name.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="max-w-[1280px] mx-auto px-4 sm:px-6 py-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold text-[#111827] mb-1">Cầu thủ</h1>
          <p className="text-[#6B7280] text-sm">Khám phá tin tức về các cầu thủ nổi bật.</p>
        </div>
        <div className="relative w-full sm:w-64">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9CA3AF]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
          <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Tìm cầu thủ..." className="w-full pl-9 pr-4 py-2 text-sm border border-[#E5E7EB] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30 focus:border-[#78A83D] bg-white placeholder-[#9CA3AF]" />
        </div>
      </div>

      <div className="mb-10">
        <div className="flex items-center gap-3 mb-5">
          <span className="w-1 h-5 rounded bg-[#78A83D]" />
          <h2 className="text-lg font-bold text-[#111827]">Cầu thủ nổi bật</h2>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          {players.map(p => (
            <Link key={p.id} to={`/cau-thu/${p.id}`} className="group flex flex-col items-center text-center p-4 bg-white border border-[#E5E7EB] rounded-xl hover:border-[#78A83D]/40 hover:shadow-sm transition-all">
              <img src={p.img} alt={p.name} className="w-16 h-16 rounded-full object-cover bg-[#E5E7EB] mb-3" />
              <h3 className="text-sm font-semibold text-[#111827] group-hover:text-[#78A83D] transition-colors leading-tight">{p.name}</h3>
              <p className="text-xs text-[#6B7280] mt-1">{p.club}</p>
            </Link>
          ))}
        </div>
      </div>

      <div>
        <div className="flex items-center gap-3 mb-5">
          <span className="w-1 h-5 rounded bg-[#78A83D]" />
          <h2 className="text-lg font-bold text-[#111827]">Có tin gần đây</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(p => <PlayerCard key={p.id} player={p} />)}
        </div>
        {filtered.length === 0 && (
          <p className="text-[#6B7280] text-center py-12">Không tìm thấy cầu thủ phù hợp.</p>
        )}
      </div>

      <div className="mt-8 text-center">
        <button className="px-6 py-2.5 border border-[#E5E7EB] rounded-lg text-sm font-medium text-[#374151] hover:border-[#78A83D] hover:text-[#78A83D] transition-colors">
          Xem thêm
        </button>
      </div>
    </div>
  )
}
