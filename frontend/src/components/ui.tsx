import { Link } from 'react-router'
import type { Article } from '../data/mock'

type Entity = { type: 'club' | 'player' | 'coach'; id: string; name: string }

const entityRoute = (e: Entity) => {
  if (e.type === 'club') return `/clb/${e.id}`
  if (e.type === 'player') return `/cau-thu/${e.id}`
  return `/hlv/${e.id}`
}

export function EntityChip({ entity, small }: { entity: Entity; small?: boolean }) {
  return (
    <Link
      to={entityRoute(entity)}
      className={`inline-flex items-center gap-1 bg-[#F3F4F6] hover:bg-[#E5E7EB] text-[#374151] rounded-full transition-colors ${small ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs font-medium'}`}
    >
      <span className="w-3.5 h-3.5 rounded-full bg-[#D1D5DB] flex-shrink-0" />
      {entity.name}
    </Link>
  )
}

export function EntityChips({ entities }: { entities: Entity[] }) {
  const max = 3
  const visible = entities.slice(0, max)
  const extra = entities.length - max
  return (
    <div className="flex flex-wrap gap-1.5">
      {visible.map(e => <EntityChip key={e.id} entity={e} />)}
      {extra > 0 && (
        <span className="inline-flex items-center px-2.5 py-1 text-xs font-medium bg-[#F3F4F6] text-[#6B7280] rounded-full">+{extra}</span>
      )}
    </div>
  )
}

export function StatusBadge({ status }: { status: 'multi' | 'official' | 'updating' }) {
  const map = {
    multi: { label: 'Nhiều nguồn xác nhận', cls: 'bg-[#FEF3C7] text-[#B7791F]' },
    official: { label: 'Chính thức', cls: 'bg-[#DCFCE7] text-[#2E7D32]' },
    updating: { label: 'Đang cập nhật', cls: 'bg-[#EFF6FF] text-[#3B82F6]' },
  }
  const { label, cls } = map[status]
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>
}

export function MetaRow({ time, sources }: { time: string; sources: number }) {
  return (
    <p className="text-xs text-[#6B7280]">
      {time} · Tổng hợp từ <span className="font-medium text-[#374151]">{sources} nguồn</span>
    </p>
  )
}

export function LargeNewsCard({ article }: { article: Article }) {
  return (
    <Link to={`/bai-viet/${article.id}`} className="group block">
      <div className="relative aspect-[16/9] rounded-xl overflow-hidden bg-[#E5E7EB] mb-3">
        <img src={article.img} alt={article.headline} className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-300" />
        {article.status && (
          <div className="absolute top-3 left-3">
            <StatusBadge status={article.status} />
          </div>
        )}
      </div>
      <h2 className="text-xl font-bold text-[#111827] leading-snug mb-2 group-hover:text-[#78A83D] transition-colors line-clamp-2">
        {article.headline}
      </h2>
      <p className="text-sm text-[#6B7280] leading-relaxed mb-3 line-clamp-2">{article.summary}</p>
      <MetaRow time={article.time} sources={article.sources} />
      {article.entities.length > 0 && (
        <div className="mt-2">
          <EntityChips entities={article.entities} />
        </div>
      )}
    </Link>
  )
}

export function MediumNewsCard({ article }: { article: Article }) {
  return (
    <Link to={`/bai-viet/${article.id}`} className="group flex gap-3">
      <div className="w-24 h-16 sm:w-28 sm:h-20 flex-shrink-0 rounded-lg overflow-hidden bg-[#E5E7EB]">
        <img src={article.img} alt={article.headline} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200" />
      </div>
      <div className="flex-1 min-w-0">
        <h3 className="text-sm font-semibold text-[#111827] leading-snug line-clamp-3 group-hover:text-[#78A83D] transition-colors mb-1">
          {article.headline}
        </h3>
        <MetaRow time={article.time} sources={article.sources} />
      </div>
    </Link>
  )
}

export function NewsRow({ article }: { article: Article }) {
  return (
    <Link to={`/bai-viet/${article.id}`} className="group flex gap-4 py-4 border-b border-[#E5E7EB] last:border-0">
      <div className="w-20 h-14 sm:w-24 sm:h-16 flex-shrink-0 rounded-lg overflow-hidden bg-[#E5E7EB]">
        <img src={article.img} alt={article.headline} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200" />
      </div>
      <div className="flex-1 min-w-0">
        <h3 className="text-[15px] font-semibold text-[#111827] leading-snug line-clamp-2 group-hover:text-[#78A83D] transition-colors mb-1">
          {article.headline}
        </h3>
        <p className="text-xs text-[#6B7280] line-clamp-1 mb-1.5 hidden sm:block">{article.summary}</p>
        <div className="flex items-center gap-3 flex-wrap">
          <MetaRow time={article.time} sources={article.sources} />
          {article.status && <StatusBadge status={article.status} />}
        </div>
        {article.entities.length > 0 && (
          <div className="mt-1.5 hidden sm:flex">
            <EntityChips entities={article.entities} />
          </div>
        )}
      </div>
    </Link>
  )
}

export function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 mb-5">
      <span className="w-1 h-5 rounded bg-[#78A83D]" />
      <h2 className="text-lg font-bold text-[#111827]">{children}</h2>
    </div>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton rounded ${className}`} />
}

export function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3, 4].map(i => (
        <div key={i} className="flex gap-4 py-4 border-b border-[#E5E7EB]">
          <Skeleton className="w-24 h-16 flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
            <Skeleton className="h-3 w-1/4" />
          </div>
        </div>
      ))}
    </div>
  )
}

export function EmptyState({ message = 'Không có dữ liệu', sub = '' }: { message?: string; sub?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-12 h-12 rounded-full bg-[#F3F4F6] flex items-center justify-center mb-4">
        <svg className="w-6 h-6 text-[#9CA3AF]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
      </div>
      <p className="text-[#374151] font-medium">{message}</p>
      {sub && <p className="text-sm text-[#6B7280] mt-1">{sub}</p>}
    </div>
  )
}
