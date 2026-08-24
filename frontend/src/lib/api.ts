import axios from 'axios'

export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('role')
      localStorage.removeItem('username')
      if (location.pathname !== '/login') location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export function apiErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (err.message) return err.message
  }
  if (err instanceof Error) return err.message
  return 'Something went wrong'
}

export interface StoryEvent {
  type: 'tool_call' | 'step' | 'error' | 'done'
  sql?: string
  role?: 'user' | 'assistant'
  narration?: string | null
  columns?: string[] | null
  rows?: Record<string, unknown>[] | null
  message?: string
}

/**
 * Streams /story as Server-Sent Events. Uses raw `fetch` (not axios) since
 * axios doesn't expose a readable-stream body reader. Robust to: non-2xx
 * responses (parsed as normal JSON error, same shape as the rest of the
 * API), chunk boundaries splitting a UTF-8 character or an SSE frame,
 * malformed individual frames (skipped rather than aborting the stream),
 * and caller-initiated cancellation via AbortSignal.
 */
export async function* streamStory(
  body: { message: string; history: unknown[] },
  signal?: AbortSignal,
): AsyncGenerator<StoryEvent> {
  const token = localStorage.getItem('access_token')
  const res = await fetch('/api/story', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  })

  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try {
      const data = await res.json()
      if (typeof data?.detail === 'string') message = data.detail
    } catch {
      /* non-JSON error body — keep the generic message */
    }
    if (res.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('role')
      localStorage.removeItem('username')
      if (location.pathname !== '/login') location.href = '/login'
    }
    throw new Error(message)
  }
  if (!res.body) throw new Error('Streaming is not supported by this browser')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let sepIndex: number
      while ((sepIndex = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, sepIndex)
        buffer = buffer.slice(sepIndex + 2)
        const dataLines = frame.split('\n').filter((l) => l.startsWith('data:'))
        if (dataLines.length === 0) continue
        const jsonStr = dataLines.map((l) => l.slice(5).trimStart()).join('\n')
        if (!jsonStr) continue
        try {
          yield JSON.parse(jsonStr) as StoryEvent
        } catch {
          // malformed frame — skip it rather than killing the whole stream
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
