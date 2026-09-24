import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { api, apiErrorMessage } from '../lib/api'
import type { NLQueryResponse } from '../lib/types'
import { useDataset } from './DatasetContext'

interface AskAIState {
  question: string
  setQuestion: (v: string) => void
  result: NLQueryResponse | null
  loading: boolean
  error: string | null
  ask: (question: string) => void
  clear: () => void
}

const AskAIContext = createContext<AskAIState | null>(null)

/**
 * Owns the Ask AI question/result at a level above the route tree (mounted
 * once in App, not per-visit to /ask), so navigating to another tab while a
 * question is still in flight no longer loses the answer — the request
 * keeps running in the background and the page picks the result back up
 * whenever the user returns.
 */
export function AskAIProvider({ children }: { children: ReactNode }) {
  const { dataset } = useDataset()
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<NLQueryResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Bumped on every dataset switch or explicit "clear" — a request in
  // flight captures the generation it started with and discards its
  // response if that generation has moved on by the time it resolves.
  const genRef = useRef(0)

  // Dataset switched — the previous answer/error describes a different
  // schema now, so it shouldn't keep showing under the new selection.
  useEffect(() => {
    genRef.current += 1
    setResult(null)
    setError(null)
    setLoading(false)
  }, [dataset])

  async function ask(q: string) {
    if (!q.trim() || loading) return
    const askedGen = genRef.current
    const askedDataset = dataset
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const { data } = await api.post<NLQueryResponse>('/nl-query', { question: q, dataset: askedDataset })
      if (genRef.current === askedGen) setResult(data)
    } catch (err) {
      if (genRef.current === askedGen) setError(apiErrorMessage(err))
    } finally {
      if (genRef.current === askedGen) setLoading(false)
    }
  }

  // Starts a fresh question — any in-flight request's response is discarded
  // via genRef (axios has no cancellation wired here, so it still completes
  // on the wire, it just no longer writes into state).
  function clear() {
    genRef.current += 1
    setQuestion('')
    setResult(null)
    setError(null)
    setLoading(false)
  }

  return (
    <AskAIContext.Provider value={{ question, setQuestion, result, loading, error, ask, clear }}>
      {children}
    </AskAIContext.Provider>
  )
}

export function useAskAI() {
  const ctx = useContext(AskAIContext)
  if (!ctx) throw new Error('useAskAI must be used within AskAIProvider')
  return ctx
}
