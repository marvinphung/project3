export type PublicArticle = {
  id: string
  slug: string
  title_vi: string
  body_vi: string
  story_id: string
  story_version: number
  published_at: string
  entities: { id: string; entity_type: string; name: string; slug: string }[]
}

export type PublicTimelineEntry = {
  story_id: string
  window_start: string
  summary_vi: string
  confirmation: string
}

export type PublicEntityStories = {
  entity_type: string
  entity_slug: string
  story_ids: string[]
}

type ListResponse<T> = { items: T[] }

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''
const CRAWLER_API_BASE_URL = import.meta.env.VITE_CRAWLER_API_BASE_URL ?? ''

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { Accept: 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { error?: { code?: string; message?: string } }
      | null
    throw new ApiError(
      response.status,
      body?.error?.code ?? 'REQUEST_FAILED',
      body?.error?.message ?? 'Không thể tải dữ liệu',
    )
  }
  return (await response.json()) as T
}

export type AuthToken = {
  access_token: string
  token_type: string
  expires_in: number
  role: 'EDITOR' | 'ADMIN'
}

export function login(username: string, password: string) {
  return request<AuthToken>('/auth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
}

const AUTH_STORAGE_KEY = 'footballpulse.auth'

export function saveAuthToken(token: AuthToken) {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(token))
}

export function getAuthToken(): AuthToken | null {
  const raw = localStorage.getItem(AUTH_STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as AuthToken
  } catch {
    localStorage.removeItem(AUTH_STORAGE_KEY)
    return null
  }
}

export function clearAuthToken() {
  localStorage.removeItem(AUTH_STORAGE_KEY)
}

export function authHeaders(): Record<string, string> {
  const token = getAuthToken()
  return token ? { Authorization: `${token.token_type} ${token.access_token}` } : {}
}

export type Source = {
  id: string
  name: string
  rss_url: string
  allowed_domains: string[]
  source_type: 'RSS' | 'HTML' | 'MOCK'
  reliability_tier: number
  enabled: boolean
  crawl_interval_minutes: number
  max_concurrency: number
  last_discovered_at: string | null
  version: number
}

export function listSources() {
  return request<{ items: Source[] }>(`${CRAWLER_API_BASE_URL}/admin/v1/sources`, {
    headers: authHeaders(),
  })
}

export function toggleSource(sourceId: string, enabled: boolean, expectedVersion: number) {
  return request<Source>(`${CRAWLER_API_BASE_URL}/admin/v1/sources/${sourceId}/toggle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ enabled, expected_version: expectedVersion }),
  })
}

export function triggerSourceCrawl(sourceId: string, idempotencyKey: string) {
  return request(`${CRAWLER_API_BASE_URL}/admin/v1/sources/${sourceId}/crawl`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ idempotency_key: idempotencyKey }),
  })
}

export type EditorialRevision = {
  generated_article_id: string
  revision_id: string
  revision_number: number
  story_version: number
  state: string
  updated_at: string
}

async function adminRequest<T>(path: string, body: unknown) {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
}

export function submitArticle(articleId: string, expectedRevisionNumber: number) {
  return adminRequest<EditorialRevision>(`/admin/v1/articles/${articleId}/submit`, {
    expected_revision_number: expectedRevisionNumber,
  })
}

export function approveArticle(articleId: string, expectedRevisionNumber: number) {
  return adminRequest<EditorialRevision>(`/admin/v1/articles/${articleId}/approve`, {
    expected_revision_number: expectedRevisionNumber,
  })
}

export function rejectArticle(articleId: string, expectedRevisionNumber: number) {
  return adminRequest<EditorialRevision>(`/admin/v1/articles/${articleId}/reject`, {
    expected_revision_number: expectedRevisionNumber,
  })
}

export function publishArticle(articleId: string, slug: string, idempotencyKey: string) {
  return adminRequest(`/admin/v1/articles/${articleId}/publish`, {
    slug,
    idempotency_key: idempotencyKey,
  })
}

export function listArticles(params: { limit?: number; offset?: number; storyId?: string } = {}) {
  const query = new URLSearchParams()
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  if (params.offset !== undefined) query.set('offset', String(params.offset))
  if (params.storyId) query.set('story_id', params.storyId)
  const suffix = query.toString() ? `?${query}` : ''
  return request<ListResponse<PublicArticle>>(`/api/v1/articles${suffix}`)
}

export function getArticle(slug: string) {
  return request<PublicArticle>(`/api/v1/articles/${encodeURIComponent(slug)}`)
}

export function getStoryTimeline(
  storyId: string,
  params: { limit?: number; offset?: number; confirmation?: string } = {},
) {
  const query = new URLSearchParams()
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  if (params.offset !== undefined) query.set('offset', String(params.offset))
  if (params.confirmation) query.set('confirmation', params.confirmation)
  const suffix = query.toString() ? `?${query}` : ''
  return request<ListResponse<PublicTimelineEntry>>(
    `/api/v1/stories/${encodeURIComponent(storyId)}/timeline${suffix}`,
  )
}

export function getEntityStories(entityType: string, entitySlug: string) {
  return request<PublicEntityStories>(
    `/api/v1/entities/${encodeURIComponent(entityType)}/${encodeURIComponent(entitySlug)}/stories`,
  )
}
