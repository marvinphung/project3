import { Link, useParams, useSearchParams } from 'react-router'
import { players, articles } from '../data/mock'
import { NewsRow, SectionHeading } from '../components/ui'
import StoryTimeline from '../components/StoryTimeline'

export default function PlayerDetailPage() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const storyId = searchParams.get('story')
  const player = players.find(p => p.id === id) ?? players[0]
  const related = articles.filter(a => a.entities.some(e => e.id === player.id))
  const allArticles = related.length > 0 ? related : articles.slice(0, 5)

  return (
    <div className="max-w-[1280px] mx-auto px-4 sm:px-6 py-8">
      {/* Hero */}
      <div className="bg-white border border-[#E5E7EB] rounded-xl p-6 mb-8">
        <div className="flex items-center gap-5">
          <img src={player.img} alt={player.name} className="w-20 h-20 rounded-full object-cover bg-[#E5E7EB] flex-shrink-0" />
          <div>
            <span className="text-xs font-semibold text-[#78A83D] uppercase tracking-wider">Cầu thủ</span>
            <h1 className="text-2xl sm:text-3xl font-bold text-[#111827] mt-0.5">{player.name}</h1>
            <p className="text-[#6B7280] text-sm mt-1">{player.club} · {player.position}</p>
            <p className="text-xs text-[#9CA3AF] mt-2"><span className="font-medium text-[#374151]">{player.articles}</span> bài viết gần đây</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_260px] gap-10">
        <section>
          <div className="mb-8 rounded-xl border border-[#E5E7EB] bg-white p-5">
            <SectionHeading>Timeline diễn biến</SectionHeading>
            <StoryTimeline storyId={storyId} entityType="PLAYER" entitySlug={player.id} />
          </div>
          <SectionHeading>Tin mới nhất về {player.name}</SectionHeading>
          {allArticles.map(a => <NewsRow key={a.id} article={a} />)}
        </section>
        <aside>
          <div className="bg-white border border-[#E5E7EB] rounded-xl p-4">
            <h3 className="text-sm font-bold text-[#111827] mb-3">Câu chuyện đang được cập nhật</h3>
            <div className="space-y-3">
              {articles.slice(0, 3).map(a => (
                <Link key={a.id} to={`/bai-viet/${a.id}`} className="block text-sm text-[#374151] hover:text-[#78A83D] leading-snug transition-colors">
                  {a.headline.slice(0, 60)}...
                </Link>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
