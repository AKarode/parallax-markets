import { useEffect, useRef, useState, useCallback } from 'react'

const POLL_INTERVAL = 300_000 // 5 minutes

interface UsePollingResult<T> {
  data: T | null
  error: string | null
  loading: boolean
  lastUpdated: Date | null
  refetch: () => void
}

export function usePolling<T>(url: string, interval = POLL_INTERVAL): UsePollingResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      const res = await fetch(url)
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }
      const json = (await res.json()) as T
      setData(json)
      setError(null)
      setLastUpdated(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [url])

  useEffect(() => {
    fetchData()

    intervalRef.current = setInterval(fetchData, interval)

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [fetchData, interval])

  return { data, error, loading, lastUpdated, refetch: fetchData }
}
