import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router'

export default function Header() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchFocused, setSearchFocused] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  const navLinks = [
    { label: 'Tin mới', to: '/tin-moi' },
    { label: 'Cầu thủ', to: '/cau-thu' },
    { label: 'CLB', to: '/clb' },
    { label: 'HLV', to: '/hlv' },
  ]

  const isActive = (to: string) => location.pathname === to

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      navigate(`/tim-kiem?q=${encodeURIComponent(searchQuery.trim())}`)
      setSearchFocused(false)
    }
  }

  return (
    <header className="bg-white border-b border-[#E5E7EB] sticky top-0 z-50">
      <div className="max-w-[1280px] mx-auto px-4 sm:px-6">
        {/* Desktop */}
        <div className="hidden md:flex items-center h-16 gap-8">
          <Link to="/" className="flex items-center gap-2 flex-shrink-0">
            <span className="w-7 h-7 rounded bg-[#78A83D] flex items-center justify-center text-white font-bold text-sm">FP</span>
            <span className="font-semibold text-[#111827] text-base tracking-tight">FootballPulse</span>
          </Link>
          <nav className="flex items-center gap-6">
            {navLinks.map(l => (
              <Link
                key={l.to}
                to={l.to}
                className={`text-sm font-medium transition-colors ${isActive(l.to) ? 'text-[#78A83D]' : 'text-[#6B7280] hover:text-[#111827]'}`}
              >
                {l.label}
              </Link>
            ))}
          </nav>
          <form onSubmit={handleSearch} className="ml-auto flex-1 max-w-sm">
            <div className="relative">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9CA3AF]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onFocus={() => setSearchFocused(true)}
                onBlur={() => setTimeout(() => setSearchFocused(false), 200)}
                placeholder="Tìm tin, cầu thủ, CLB hoặc HLV..."
                className="w-full pl-9 pr-4 py-2 text-sm border border-[#E5E7EB] rounded-lg bg-[#F9FAFB] focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30 focus:border-[#78A83D] placeholder-[#9CA3AF]"
              />
            </div>
          </form>
        </div>
        {/* Mobile */}
        <div className="flex md:hidden items-center h-14 gap-3">
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="p-2 text-[#6B7280] hover:text-[#111827]"
            aria-label="Menu"
          >
            {menuOpen ? (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>
            )}
          </button>
          <Link to="/" className="flex items-center gap-2">
            <span className="w-6 h-6 rounded bg-[#78A83D] flex items-center justify-center text-white font-bold text-xs">FP</span>
            <span className="font-semibold text-[#111827] text-sm">FootballPulse</span>
          </Link>
          <Link to="/tim-kiem" className="ml-auto p-2 text-[#6B7280] hover:text-[#111827]" aria-label="Tìm kiếm">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
          </Link>
        </div>
      </div>
      {/* Mobile drawer */}
      {menuOpen && (
        <div className="md:hidden border-t border-[#E5E7EB] bg-white px-4 py-3 flex flex-col gap-1">
          {navLinks.map(l => (
            <Link
              key={l.to}
              to={l.to}
              onClick={() => setMenuOpen(false)}
              className={`py-2.5 px-3 rounded-md text-sm font-medium transition-colors ${isActive(l.to) ? 'text-[#78A83D] bg-[#78A83D]/5' : 'text-[#374151] hover:bg-[#F3F4F6]'}`}
            >
              {l.label}
            </Link>
          ))}
          <form onSubmit={handleSearch} className="mt-2">
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Tìm tin, cầu thủ, CLB hoặc HLV..."
              className="w-full px-3 py-2.5 text-sm border border-[#E5E7EB] rounded-lg bg-[#F9FAFB] focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30 focus:border-[#78A83D] placeholder-[#9CA3AF]"
            />
          </form>
        </div>
      )}
    </header>
  )
}
