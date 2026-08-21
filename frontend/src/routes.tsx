import { createBrowserRouter } from 'react-router'

import PublicLayout from './layouts/PublicLayout'
import HomePage from './pages/HomePage'
import LatestNewsPage from './pages/LatestNewsPage'
import EntityDirectoryPage from './pages/EntityDirectoryPage'
import ArticleDetailPage from './pages/ArticleDetailPage'
import EntityDetailPage from './pages/EntityDetailPage'
import SearchPage from './pages/SearchPage'
import NotFoundPage from './pages/NotFoundPage'
import StoryPage from './pages/StoryPage'

import AdminLayout from './pages/admin/AdminLayout'
import AdminLoginPage from './pages/admin/AdminLoginPage'
import AdminDashboard from './pages/admin/AdminDashboard'
import AdminSourcesPage from './pages/admin/AdminSourcesPage'
import AdminDraftPage from './pages/admin/AdminDraftPage'
import AdminErrorsPage from './pages/admin/AdminErrorsPage'
import AdminPublishedPage from './pages/admin/AdminPublishedPage'
import AdminStoryPage from './pages/admin/AdminStoryPage'
import AdminArticlesPage from './pages/admin/AdminArticlesPage'

import StaticInfoPage from './pages/StaticInfoPage'

export const router = createBrowserRouter([
  {
    path: '/',
    Component: PublicLayout,
    children: [
      { index: true, Component: HomePage },
      { path: 'tin-moi', Component: LatestNewsPage },
      { path: 'cau-thu', element: <EntityDirectoryPage kind="player" /> },
      { path: 'cau-thu/:id', element: <EntityDetailPage kind="player" /> },
      { path: 'clb', element: <EntityDirectoryPage kind="club" /> },
      { path: 'clb/:id', element: <EntityDetailPage kind="club" /> },
      { path: 'hlv', element: <EntityDirectoryPage kind="coach" /> },
      { path: 'hlv/:id', element: <EntityDetailPage kind="coach" /> },
      { path: 'entity/:id', element: <EntityDetailPage /> },
      { path: 'bai-viet/:id', Component: ArticleDetailPage },
      { path: 'story/:id', Component: StoryPage },
      { path: 'tim-kiem', Component: SearchPage },
      { path: 'gioi-thieu', element: <StaticInfoPage type="about" /> },
      { path: 'nguon-tin', element: <StaticInfoPage type="sources" /> },
      { path: 'dieu-khoan', element: <StaticInfoPage type="terms" /> },
      { path: 'lien-he', element: <StaticInfoPage type="contact" /> },
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
