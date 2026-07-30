import { createBrowserRouter } from 'react-router'

import PublicLayout from './layouts/PublicLayout'
import HomePage from './pages/HomePage'
import LatestNewsPage from './pages/LatestNewsPage'
import PlayersPage from './pages/PlayersPage'
import ClubsPage from './pages/ClubsPage'
import CoachesPage from './pages/CoachesPage'
import ArticleDetailPage from './pages/ArticleDetailPage'
import PlayerDetailPage from './pages/PlayerDetailPage'
import ClubDetailPage from './pages/ClubDetailPage'
import CoachDetailPage from './pages/CoachDetailPage'
import SearchPage from './pages/SearchPage'
import NotFoundPage from './pages/NotFoundPage'

import AdminLayout from './pages/admin/AdminLayout'
import AdminLoginPage from './pages/admin/AdminLoginPage'
import AdminDashboard from './pages/admin/AdminDashboard'
import AdminSourcesPage from './pages/admin/AdminSourcesPage'
import AdminDraftPage from './pages/admin/AdminDraftPage'
import AdminErrorsPage from './pages/admin/AdminErrorsPage'
import AdminPublishedPage from './pages/admin/AdminPublishedPage'
import AdminStoryPage from './pages/admin/AdminStoryPage'
import AdminArticlesPage from './pages/admin/AdminArticlesPage'

export const router = createBrowserRouter([
  {
    path: '/',
    Component: PublicLayout,
    children: [
      { index: true, Component: HomePage },
      { path: 'tin-moi', Component: LatestNewsPage },
      { path: 'cau-thu', Component: PlayersPage },
      { path: 'cau-thu/:id', Component: PlayerDetailPage },
      { path: 'clb', Component: ClubsPage },
      { path: 'clb/:id', Component: ClubDetailPage },
      { path: 'hlv', Component: CoachesPage },
      { path: 'hlv/:id', Component: CoachDetailPage },
      { path: 'bai-viet/:id', Component: ArticleDetailPage },
      { path: 'tim-kiem', Component: SearchPage },
      { path: '*', Component: NotFoundPage },
    ],
  },
  { path: '/admin/login', Component: AdminLoginPage },
  {
    path: '/admin',
    Component: AdminLayout,
    children: [
      { index: true, Component: AdminDashboard },
      { path: 'nguon-tin', Component: AdminSourcesPage },
      { path: 'bai-nguon', Component: AdminArticlesPage },
      { path: 'story', Component: AdminStoryPage },
      { path: 'ban-nhap', Component: AdminDraftPage },
      { path: 'xuat-ban', Component: AdminPublishedPage },
      { path: 'loi-xu-ly', Component: AdminErrorsPage },
    ],
  },
])
