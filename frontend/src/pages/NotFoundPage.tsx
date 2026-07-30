import { Link } from 'react-router'

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <p className="text-8xl font-bold text-[#E5E7EB] mb-4">404</p>
      <h1 className="text-2xl font-bold text-[#111827] mb-2">Không tìm thấy trang</h1>
      <p className="text-[#6B7280] mb-8">Trang bạn tìm kiếm không tồn tại hoặc đã bị xóa.</p>
      <Link to="/" className="inline-flex items-center gap-2 px-6 py-2.5 bg-[#78A83D] text-white rounded-lg text-sm font-medium hover:bg-[#6a9435] transition-colors">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>
        Quay lại trang chủ
      </Link>
    </div>
  )
}
