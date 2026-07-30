import { useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router'

const navItems = [
  { label: 'Tổng quan', to: '/admin', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { label: 'Nguồn tin', to: '/admin/nguon-tin', icon: 'M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z' },
  { label: 'Bài nguồn', to: '/admin/bai-nguon', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
  { label: 'Story', to: '/admin/story', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
  { label: 'Bản nháp', to: '/admin/ban-nhap', icon: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z' },
  { label: 'Đã xuất bản', to: '/admin/xuat-ban', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
  { label: 'Lỗi xử lý', to: '/admin/loi-xu-ly', icon: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z' },
]

export default function AdminLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  const isActive = (to: string) => {
    if (to === '/admin') return location.pathname === '/admin'
    return location.pathname.startsWith(to)
  }

  return (
    <div className="min-h-screen bg-[#F7F8FA] flex">
      {/* Sidebar desktop */}
      <aside className="hidden lg:flex flex-col w-56 bg-white border-r border-[#E5E7EB] fixed top-0 bottom-0 left-0 z-30">
        <div className="p-4 border-b border-[#E5E7EB]">
          <Link to="/" className="flex items-center gap-2">
            <span className="w-7 h-7 rounded bg-[#78A83D] flex items-center justify-center text-white font-bold text-sm">FP</span>
            <div>
              <span className="font-semibold text-[#111827] text-sm block">FootballPulse</span>
              <span className="text-[10px] text-[#6B7280]">Admin</span>
            </div>
          </Link>
        </div>
        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          {navItems.map(item => (
            <Link
              key={item.to}
              to={item.to}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${isActive(item.to) ? 'bg-[#78A83D]/10 text-[#78A83D]' : 'text-[#6B7280] hover:bg-[#F3F4F6] hover:text-[#111827]'}`}
            >
              <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={item.icon} /></svg>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="p-3 border-t border-[#E5E7EB]">
          <Link to="/" className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-[#6B7280] hover:bg-[#F3F4F6] hover:text-[#111827] transition-colors">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
            Xem trang web
          </Link>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-30 bg-white border-b border-[#E5E7EB] px-4 h-14 flex items-center gap-3">
        <button onClick={() => setSidebarOpen(true)} className="p-2 text-[#6B7280]">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>
        </button>
        <span className="font-semibold text-[#111827] text-sm">FootballPulse Admin</span>
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-black/30" onClick={() => setSidebarOpen(false)} />
          <aside className="relative w-56 bg-white h-full flex flex-col shadow-xl">
            <div className="p-4 border-b border-[#E5E7EB] flex items-center justify-between">
              <span className="font-semibold text-[#111827] text-sm">FootballPulse Admin</span>
              <button onClick={() => setSidebarOpen(false)} className="p-1 text-[#6B7280]">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <nav className="flex-1 p-3 space-y-0.5">
              {navItems.map(item => (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={() => setSidebarOpen(false)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${isActive(item.to) ? 'bg-[#78A83D]/10 text-[#78A83D]' : 'text-[#6B7280] hover:bg-[#F3F4F6] hover:text-[#111827]'}`}
                >
                  <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={item.icon} /></svg>
                  {item.label}
                </Link>
              ))}
            </nav>
          </aside>
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 lg:ml-56 pt-14 lg:pt-0 min-h-screen">
        <Outlet />
      </main>
    </div>
  )
}
