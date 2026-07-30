import { useParams } from 'react-router'
import { coaches, articles } from '../data/mock'
import { NewsRow, SectionHeading } from '../components/ui'

export default function CoachDetailPage() {
  const { id } = useParams()
  const coach = coaches.find(c => c.id === id) ?? coaches[0]
  const related = articles.filter(a => a.entities.some(e => e.id === coach.id))
  const allArticles = related.length > 0 ? related : articles.slice(0, 5)

  return (
    <div className="max-w-[1280px] mx-auto px-4 sm:px-6 py-8">
      <div className="bg-white border border-[#E5E7EB] rounded-xl p-6 mb-8">
        <div className="flex items-center gap-5">
          <img src={coach.img} alt={coach.name} className="w-20 h-20 rounded-full object-cover bg-[#E5E7EB] flex-shrink-0" />
          <div>
            <span className="text-xs font-semibold text-[#78A83D] uppercase tracking-wider">Huấn luyện viên</span>
            <h1 className="text-2xl sm:text-3xl font-bold text-[#111827] mt-0.5">{coach.name}</h1>
            <p className="text-[#6B7280] text-sm mt-1">{coach.club}</p>
            <p className="text-xs text-[#9CA3AF] mt-2"><span className="font-medium text-[#374151]">{coach.articles}</span> bài viết gần đây</p>
          </div>
        </div>
      </div>

      <SectionHeading>Tin mới nhất về {coach.name}</SectionHeading>
      {allArticles.map(a => <NewsRow key={a.id} article={a} />)}
    </div>
  )
}
