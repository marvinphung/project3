import { Link } from 'react-router'

export default function Footer() {
  return (
    <footer className="bg-white border-t border-[#E5E7EB] mt-16">
      <div className="max-w-[1280px] mx-auto px-4 sm:px-6 py-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded bg-[#78A83D] flex items-center justify-center text-white font-bold text-xs">FP</span>
            <span className="font-semibold text-[#111827] text-sm">FootballPulse</span>
          </div>
          <nav className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-[#6B7280]">
            <Link to="/gioi-thieu" className="hover:text-[#111827] transition-colors">Giới thiệu</Link>
            <Link to="/nguon-tin" className="hover:text-[#111827] transition-colors">Nguồn tin</Link>
            <Link to="/dieu-khoan" className="hover:text-[#111827] transition-colors">Điều khoản</Link>
            <Link to="/lien-he" className="hover:text-[#111827] transition-colors">Liên hệ</Link>
          </nav>
          <p className="text-xs text-[#9CA3AF]">© 2025 FootballPulse. All rights reserved.</p>
        </div>
      </div>
    </footer>
  )
}
