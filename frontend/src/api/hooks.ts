import { useEffect, useState } from 'react'
import { ApiError, getArticle, listArticles, type PublicArticle } from './client'

type QueryState<T> = {
  data: T | null
  loading: boolean
  error: ApiError | null
}

export function usePublicArticles(limit = 20): QueryState<PublicArticle[]> {
  const [state, setState] = useState<QueryState<PublicArticle[]>>({
    data: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    let active = true
    setState({ data: null, loading: true, error: null })
    listArticles({ limit })
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
  }, [limit])

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
