import { useEffect, useState } from 'react'
import { ApiError, getStoryTimeline, type PublicTimelineEntry } from './client'

export function useStoryTimeline(storyId: string | null): {
  data: PublicTimelineEntry[] | null
  loading: boolean
  error: ApiError | null
} {
  const [state, setState] = useState<{
    data: PublicTimelineEntry[] | null
    loading: boolean
    error: ApiError | null
  }>({ data: null, loading: false, error: null })

  useEffect(() => {
    if (!storyId) {
      setState({ data: null, loading: false, error: null })
      return
    }
    let active = true
    setState({ data: null, loading: true, error: null })
    getStoryTimeline(storyId)
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
  }, [storyId])

  return state
}
