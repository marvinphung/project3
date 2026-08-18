import { useState } from 'react'
import { useNavigate } from 'react-router'
import { ApiError, login, saveAuthToken } from '../../api/client'

export default function AdminLoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!email || !password) {
      setError('Vui lòng nhập đầy đủ thông tin.')
      return
    }
    setLoading(true)
    try {
      const token = await login(email, password)
      saveAuthToken(token)
      navigate('/admin')
    } catch (error) {
      setError(error instanceof ApiError ? error.message : 'Không thể kết nối tới hệ thống.')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#F7F8FA] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-[#78A83D] mb-4">
            <span className="text-white font-bold text-lg">FP</span>
          </div>
          <h1 className="text-2xl font-bold text-[#111827]">Đăng nhập quản trị</h1>
          <p className="text-sm text-[#6B7280] mt-1">FootballPulse Admin Panel</p>
        </div>

        <div className="bg-white border border-[#E5E7EB] rounded-xl p-6 shadow-sm">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
              <svg className="w-4 h-4 text-red-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-[#374151] mb-1.5">Email</label>
              <input
                type="text"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="admin@footballpulse.vn"
                className="w-full px-3 py-2.5 border border-[#E5E7EB] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30 focus:border-[#78A83D] bg-white placeholder-[#9CA3AF]"
                autoComplete="email"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#374151] mb-1.5">Mật khẩu</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-3 py-2.5 border border-[#E5E7EB] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#78A83D]/30 focus:border-[#78A83D] bg-white placeholder-[#9CA3AF]"
                autoComplete="current-password"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-[#78A83D] text-white rounded-lg text-sm font-semibold hover:bg-[#6a9435] transition-colors disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                  Đang đăng nhập...
                </>
              ) : 'Đăng nhập'}
            </button>
          </form>

          <p className="text-xs text-[#9CA3AF] mt-4 text-center">Dùng tài khoản đã bootstrap trong API gateway.</p>
        </div>
      </div>
    </div>
  )
}
