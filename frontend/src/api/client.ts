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

type V2Article = {
  id: string
  slug: string
  title_en: string
  title_vi: string
  excerpt_vi: string | null
  body_en: string
  body_vi: string
  story_id: string | null
  published_at: string
}

function fromV2Article(article: V2Article): PublicArticle {
  return {
    id: article.id,
    slug: article.slug,
    title_vi: article.title_vi,
    body_vi: article.body_vi,
    story_id: article.story_id ?? article.id,
    story_version: 1,
    published_at: article.published_at,
    entities: [],
  }
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

export type PublicEntity = {
  id: string
  entity_type: 'PLAYER' | 'CLUB' | 'COACH' | 'COMPETITION'
  name: string
  slug: string
  story_count: number
  article_count: number
}

export type PublicStory = {
  id: string
  event_type: string
  status: string
  confidence_score: number
  version: number
  first_seen_at: string
  last_seen_at: string
}

export type PublicArticleSource = {
  source_id: string
  source_name: string
  source_url: string
  published_at: string
  reliability_tier: number
}

type ListResponse<T> = {
  items: T[]
  total?: number
  limit?: number
  offset?: number
  next_offset?: number | null
}

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
  const started = performance.now()
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...init?.headers },
    })
  } catch (error) {
    logUiEvent('api_request_failed', 'error', {
      method: init?.method ?? 'GET',
      path,
      error_type: error instanceof Error ? error.name : 'UnknownError',
      duration_ms: Math.round(performance.now() - started),
    })
    throw error
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { error?: { code?: string; message?: string } }
      | null
    const apiError = new ApiError(
      response.status,
      body?.error?.code ?? 'REQUEST_FAILED',
      body?.error?.message ?? 'Không thể tải dữ liệu',
    )
    logUiEvent(response.status === 401 ? 'authentication_failed' : 'api_request_failed', 'error', {
      method: init?.method ?? 'GET',
      path,
      status_code: response.status,
      error_code: apiError.code,
      request_id: response.headers.get('X-Request-ID'),
      duration_ms: Math.round(performance.now() - started),
    })
    throw apiError
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
  source_type: 'RSS' | 'SITEMAP' | 'HTML'
  reliability_tier: number
  enabled: boolean
  crawl_interval_minutes: number
  max_concurrency: number
  last_discovered_at: string | null
  version: number
}

export type SourceConfiguration = Pick<
  Source,
  'name' | 'rss_url' | 'allowed_domains' | 'source_type' | 'reliability_tier' | 'crawl_interval_minutes' | 'max_concurrency'
>

export type SourceArticle = {
  id: string
  title: string
  source_url: string
  collected_at: string
  extraction_status: string
  duplicate_type: string
}

export type OperationsSummary = {
  source_articles_total: number
  source_articles_today: number
  enrichments_validated: number
  enrichments_needs_content_review: number
  revisions_by_state: Record<string, number>
  publications_total: number
}

export type AdminStory = { id: string; event_type: string; status: string; confidence_score: number; version: number; last_seen_at: string; source_count: number }
export type AdminPublication = { id: string; slug: string; title_vi: string; story_id: string; published_at: string }
export type ProcessingFailure = { id: string; stage: string; status: string; message: string; attempts: number; occurred_at: string }

export function listSources() {
  return request<{ items: Source[] }>(`${CRAWLER_API_BASE_URL}/admin/v1/sources`, {
    headers: authHeaders(),
  })
}

export function createSource(configuration: SourceConfiguration) {
  return request<Source>(`${CRAWLER_API_BASE_URL}/admin/v1/sources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(configuration),
  })
}

export function updateSource(sourceId: string, configuration: SourceConfiguration, expectedVersion: number) {
  return request<Source>(`${CRAWLER_API_BASE_URL}/admin/v1/sources/${sourceId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ ...configuration, expected_version: expectedVersion }),
  })
}

export function listSourceArticles(params: { limit?: number; offset?: number; query?: string } = {}) {
  const query = new URLSearchParams()
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  if (params.offset !== undefined) query.set('offset', String(params.offset))
  if (params.query) query.set('q', params.query)
  const suffix = query.toString() ? `?${query}` : ''
  return request<ListResponse<SourceArticle>>(`/admin/v1/source-articles${suffix}`, {
    headers: authHeaders(),
  })
}

export function getOperationsSummary() {
  return request<OperationsSummary>('/admin/v1/operations/summary', {
    headers: authHeaders(),
  })
}

export function listAdminStories(params: { limit?: number; offset?: number; status?: string } = {}) {
  const query = new URLSearchParams()
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  if (params.offset !== undefined) query.set('offset', String(params.offset))
  if (params.status) query.set('status', params.status)
  return request<ListResponse<AdminStory>>(`/admin/v1/stories?${query}`, { headers: authHeaders() })
}

export function listAdminPublications(params: { limit?: number; offset?: number } = {}) {
  const query = new URLSearchParams()
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  if (params.offset !== undefined) query.set('offset', String(params.offset))
  return request<ListResponse<AdminPublication>>(`/admin/v1/publications?${query}`, { headers: authHeaders() })
}

export function listProcessingFailures() { return request<ListResponse<ProcessingFailure>>('/admin/v1/processing-failures?limit=50', { headers: authHeaders() }) }

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

export type EditorialRevisionDetail = EditorialRevision & {
  story_id: string
  title_en: string
  body_en: string
  title_vi: string
  body_vi: string
}

async function adminRequest<T>(path: string, body: unknown) {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
}

export function listEditorialRevisions(params: { limit?: number; offset?: number; state?: string } = {}) {
  const query = new URLSearchParams()
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  if (params.offset !== undefined) query.set('offset', String(params.offset))
  if (params.state) query.set('state', params.state)
  return request<ListResponse<EditorialRevisionDetail>>(`/admin/v1/editorial/revisions?${query}`, {
    headers: authHeaders(),
  })
}

export function updateEditorialRevision(articleId: string, payload: Pick<EditorialRevisionDetail, 'title_vi' | 'body_vi'>, expectedRevisionNumber: number) {
  return request<EditorialRevisionDetail>(`/admin/v1/articles/${articleId}/revision`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ ...payload, expected_revision_number: expectedRevisionNumber }),
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

export type ArticleListParams = {
  limit?: number
  offset?: number
  storyId?: string
  query?: string
  entityType?: string
  entitySlug?: string
  sort?: 'newest' | 'oldest'
}

export function listArticles(params: ArticleListParams = {}) {
  const query = new URLSearchParams()
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  if (params.offset !== undefined) query.set('offset', String(params.offset))
  const suffix = query.toString() ? `?${query}` : ''
  return request<{ items: V2Article[]; limit: number; offset: number }>(`/api/v2/articles${suffix}`)
    .then((response) => ({ ...response, items: response.items.map(fromV2Article) }))
}

export function getArticle(slug: string) {
  return request<V2Article>(`/api/v2/articles/${encodeURIComponent(slug)}`)
    .then(fromV2Article)
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
  return request<{ items: { story_id: string; happened_at: string; summary_vi: string; confirmation: string }[] }>(
    `/api/v2/stories/${encodeURIComponent(storyId)}/timeline${suffix}`,
  ).then((response) => ({
    items: response.items.map((item) => ({
      story_id: item.story_id,
      window_start: item.happened_at,
      summary_vi: item.summary_vi,
      confirmation: item.confirmation,
    })),
  }))
}

export function getEntityStories(entityType: string, entitySlug: string) {
  return request<PublicEntityStories>(
    `/api/v1/entities/${encodeURIComponent(entityType)}/${encodeURIComponent(entitySlug)}/stories`,
  )
}

export function listEntities(params: { type?: string; query?: string; limit?: number; offset?: number } = {}) {
  const query = new URLSearchParams()
  if (params.type) query.set('type', params.type)
  if (params.query) query.set('q', params.query)
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  if (params.offset !== undefined) query.set('offset', String(params.offset))
  return request<ListResponse<PublicEntity>>(`/api/v1/entities?${query}`)
}

export function getEntity(entityType: string, entitySlug: string) {
  return request<PublicEntity>(
    `/api/v1/entities/${encodeURIComponent(entityType)}/${encodeURIComponent(entitySlug)}`,
  )
}

export function getStory(storyId: string) {
  return request<PublicStory>(`/api/v1/stories/${encodeURIComponent(storyId)}`)
}

export function getArticleSources(slug: string) {
  return request<ListResponse<PublicArticleSource>>(
    `/api/v2/articles/${encodeURIComponent(slug)}/sources`,
  )
}
import { logUiEvent } from '../observability'
