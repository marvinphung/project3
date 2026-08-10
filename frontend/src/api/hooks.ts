import { useEffect, useState } from 'react'
import { ApiError, listArticles, type PublicArticle } from './client'

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
