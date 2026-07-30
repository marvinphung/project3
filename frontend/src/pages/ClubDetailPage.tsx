import { Link, useParams } from 'react-router'
import { clubs, articles, players, coaches } from '../data/mock'
import { NewsRow, SectionHeading, EntityChip } from '../components/ui'

export default function ClubDetailPage() {
  const { id } = useParams()
  const club = clubs.find(c => c.id === id) ?? clubs[0]
  const related = articles.filter(a => a.entities.some(e => e.id === club.id))
  const allArticles = related.length > 0 ? related : articles.slice(0, 5)

  const mentionedEntities = [
    { type: 'player' as const, id: 'saka', name: 'Bukayo Saka' },
    { type: 'coach' as const, id: 'arteta', name: 'Mikel Arteta' },
    { type: 'player' as const, id: 'haaland', name: 'Erling Haaland' },
  ]

  return (
    <div className="max-w-[1280px] mx-auto px-4 sm:px-6 py-8">
      <div className="bg-white border border-[#E5E7EB] rounded-xl p-6 mb-8">
        <div className="flex items-center gap-5">
          <div className="w-20 h-20 rounded-full bg-[#F3F4F6] flex items-center justify-center text-4xl flex-shrink-0">{club.crest}</div>
          <div>
            <span className="text-xs font-semibold text-[#78A83D] uppercase tracking-wider">Câu lạc bộ</span>
            <h1 className="text-2xl sm:text-3xl font-bold text-[#111827] mt-0.5">{club.name}</h1>
            <p className="text-[#6B7280] text-sm mt-1">{club.league} · {club.country}</p>
            <p className="text-xs text-[#9CA3AF] mt-2"><span className="font-medium text-[#374151]">{club.articles}</span> bài viết gần đây</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_260px] gap-10">
        <section>
          <SectionHeading>Tin mới nhất về {club.name}</SectionHeading>
          {allArticles.map(a => <NewsRow key={a.id} article={a} />)}
        </section>
        <aside>
          <div className="bg-white border border-[#E5E7EB] rounded-xl p-4">
            <h3 className="text-sm font-bold text-[#111827] mb-3">Được nhắc đến nhiều</h3>
            <div className="flex flex-col gap-2">
              {mentionedEntities.map(e => (
                <div key={e.id} className="py-1">
                  <EntityChip entity={e} />
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
