import { useEffect, useState } from 'react'
import { ApiError, getArticle, getArticleSources, getEntity, getStory, listArticles, listEntities, type ArticleListParams, type PublicArticle, type PublicArticleSource, type PublicEntity, type PublicStory } from './client'

type QueryState<T> = {
  data: T | null
  loading: boolean
  error: ApiError | null
}

export function usePublicArticles(
  limit = 20,
  params: Omit<ArticleListParams, 'limit'> = {},
): QueryState<PublicArticle[]> {
  const [state, setState] = useState<QueryState<PublicArticle[]>>({
    data: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    let active = true
    setState({ data: null, loading: true, error: null })
    listArticles({ ...params, limit })
      .then((response) => {
        if (active) setState({ data: response.items, loading: false, error: null })
      })
      .catch((error: unknown) => {
        if (!active) return
        const apiError = error instanceof ApiError
          ? error
          : new ApiError(0, 'NETWORK_ERROR', 'Không thể kết nối tới FootballPulse')
        setState({ data: null, loading: false, error: apiError })
      })
    return () => {
      active = false
    }
  }, [limit, params.entitySlug, params.entityType, params.offset, params.query, params.sort, params.storyId])

  return state
}

export function usePublicArticle(slug: string | undefined): QueryState<PublicArticle> {
  const [state, setState] = useState<QueryState<PublicArticle>>({
    data: null,
    loading: Boolean(slug),
    error: null,
  })

  useEffect(() => {
    if (!slug) {
      setState({ data: null, loading: false, error: new ApiError(404, 'ARTICLE_NOT_FOUND', 'Không tìm thấy bài viết') })
      return
    }
    let active = true
    setState({ data: null, loading: true, error: null })
    getArticle(slug)
      .then((data) => {
        if (active) setState({ data, loading: false, error: null })
      })
      .catch((error: unknown) => {
        if (!active) return
        const apiError = error instanceof ApiError
          ? error
          : new ApiError(0, 'NETWORK_ERROR', 'Không thể kết nối tới FootballPulse')
        setState({ data: null, loading: false, error: apiError })
      })
    return () => {
      active = false
    }
  }, [slug])

  return state
}

export function usePublicEntities(entityType: string, query = ''): QueryState<PublicEntity[]> {
  const [state, setState] = useState<QueryState<PublicEntity[]>>({ data: null, loading: true, error: null })
  useEffect(() => {
    let active = true
    setState({ data: null, loading: true, error: null })
    listEntities({ type: entityType, query: query || undefined, limit: 100 })
      .then((response) => active && setState({ data: response.items, loading: false, error: null }))
      .catch((error: unknown) => active && setState({ data: null, loading: false, error: toApiError(error) }))
    return () => { active = false }
  }, [entityType, query])
  return state
}

export function usePublicEntity(entityType: string, slug: string): QueryState<PublicEntity> {
  const [state, setState] = useState<QueryState<PublicEntity>>({ data: null, loading: true, error: null })
  useEffect(() => {
    let active = true
    setState({ data: null, loading: true, error: null })
    getEntity(entityType, slug)
      .then((data) => active && setState({ data, loading: false, error: null }))
      .catch((error: unknown) => active && setState({ data: null, loading: false, error: toApiError(error) }))
    return () => { active = false }
  }, [entityType, slug])
  return state
}

function toApiError(error: unknown): ApiError {
  return error instanceof ApiError
    ? error
    : new ApiError(0, 'NETWORK_ERROR', 'Không thể kết nối tới FootballPulse')
}

export function usePublicStory(storyId: string): QueryState<PublicStory> {
  return useRemoteValue(storyId, getStory)
}

export function useArticleSources(slug: string): QueryState<PublicArticleSource[]> {
  const [state, setState] = useState<QueryState<PublicArticleSource[]>>({ data: null, loading: true, error: null })
  useEffect(() => {
    let active = true
    getArticleSources(slug)
      .then((response) => active && setState({ data: response.items, loading: false, error: null }))
      .catch((error: unknown) => active && setState({ data: null, loading: false, error: toApiError(error) }))
    return () => { active = false }
  }, [slug])
  return state
}

export function useTopEntities(limit = 10, window = '24h'): QueryState<PublicEntitySummary[]> {
  const [state, setState] = useState<QueryState<PublicEntitySummary[]>>({ data: null, loading: true, error: null })
  useEffect(() => {
    let active = true
    setState({ data: null, loading: true, error: null })
    getTopEntities(limit, window)
      .then((res) => active && setState({ data: res.items, loading: false, error: null }))
      .catch((err) => active && setState({ data: null, loading: false, error: toApiError(err) }))
    return () => { active = false }
  }, [limit, window])
  return state
}

export function useEntitySearch(query: string): QueryState<PublicEntitySummary[]> {
  const [state, setState] = useState<QueryState<PublicEntitySummary[]>>({ data: null, loading: Boolean(query.trim()), error: null })
  useEffect(() => {
    const q = query.trim()
    if (!q) {
      setState({ data: [], loading: false, error: null })
      return
    }
    let active = true
    setState({ data: null, loading: true, error: null })
    searchEntities(q)
      .then((res) => active && setState({ data: res.items, loading: false, error: null }))
      .catch((err) => active && setState({ data: null, loading: false, error: toApiError(err) }))
    return () => { active = false }
  }, [query])
  return state
}

export function useEntityTimeline(entityId: string, limit = 50, offset = 0): QueryState<PublicEntityTimeline> {
  const [state, setState] = useState<QueryState<PublicEntityTimeline>>({ data: null, loading: Boolean(entityId), error: null })
  useEffect(() => {
    if (!entityId) {
      setState({ data: null, loading: false, error: new ApiError(404, 'ENTITY_NOT_FOUND', 'Không tìm thấy entity') })
      return
    }
    let active = true
    setState({ data: null, loading: true, error: null })
    getEntityTimeline(entityId, limit, offset)
      .then((data) => active && setState({ data, loading: false, error: null }))
      .catch((err) => active && setState({ data: null, loading: false, error: toApiError(err) }))
    return () => { active = false }
  }, [entityId, limit, offset])
  return state
}

export function useEntityDetail(entityId: string): QueryState<PublicEntitySummary> {
  return useRemoteValue(entityId, getEntityById)
}

function useRemoteValue<T>(id: string, loader: (id: string) => Promise<T>): QueryState<T> {
  const [state, setState] = useState<QueryState<T>>({ data: null, loading: true, error: null })
  useEffect(() => {
    let active = true
    setState({ data: null, loading: true, error: null })
    loader(id)
      .then((data) => active && setState({ data, loading: false, error: null }))
      .catch((error: unknown) => active && setState({ data: null, loading: false, error: toApiError(error) }))
    return () => { active = false }
  }, [id, loader])
  return state
}
