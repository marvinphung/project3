import { Outlet } from 'react-router'
import Header from '../components/Header'
import Footer from '../components/Footer'

export default function PublicLayout() {
  return (
    <div className="min-h-screen flex flex-col bg-[#F7F8FA]">
      <Header />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
