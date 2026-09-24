import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { streamStory, apiErrorMessage } from '../lib/api'
import type { StoryStep } from '../lib/types'
import { useDataset } from './DatasetContext'

// Keyed per dataset — a conversation started against one dataset's schema
// shouldn't silently continue against another's when the user switches.
const storageKey = (dataset: string) => `story:messages:${dataset}`

function loadStoredMessages(dataset: string): StoryStep[] {
  try {
    const raw = sessionStorage.getItem(storageKey(dataset))
    return raw ? (JSON.parse(raw) as StoryStep[]) : []
  } catch {
    return []
  }
}

interface StoryState {
  messages: StoryStep[]
  pendingSql: string | null
  loading: boolean
  error: string | null
  input: string
  setInput: (v: string) => void
  send: (message: string) => void
  stop: () => void
  clear: () => void
}

const StoryContext = createContext<StoryState | null>(null)

/**
 * Owns the Story conversation and its in-flight SSE stream at a level above
 * the route tree (mounted once in App, not per-visit to /story), so
 * navigating to another tab while a message is still streaming no longer
 * kills the request or drops the state — this provider just keeps running
 * quietly in the background and the page re-attaches to it whenever the
 * user comes back.
 */
export function StoryProvider({ children }: { children: ReactNode }) {
  const { dataset } = useDataset()
  const [messages, setMessages] = useState<StoryStep[]>(() => loadStoredMessages(dataset))
  const [pendingSql, setPendingSql] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  // Bumped on every dataset switch or explicit "clear" — a stream in flight
  // captures the generation it started with and stops applying events the
  // moment it no longer matches, covering both "dataset changed" and
  // "conversation was cleared" without two separate checks.
  const genRef = useRef(0)
  // Set right after the dataset-switch effect reloads `messages` below, so
  // the very next persist-effect run (which would otherwise still see the
  // *previous* dataset's messages, since setState hasn't applied yet) is
  // skipped instead of writing stale data under the new dataset's key.
  const skipNextPersist = useRef(false)

  // Dataset switched — abort any in-flight request for the previous dataset
  // (its response would otherwise land in the new dataset's transcript) and
  // load that dataset's own saved conversation instead of carrying the
  // previous one over (its history references the wrong schema).
  useEffect(() => {
    genRef.current += 1
    abortRef.current?.abort()
    setLoading(false)
    setPendingSql(null)
    setError(null)
    skipNextPersist.current = true
    setMessages(loadStoredMessages(dataset))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset])

  useEffect(() => {
    if (skipNextPersist.current) {
      skipNextPersist.current = false
      return
    }
    try {
      sessionStorage.setItem(storageKey(dataset), JSON.stringify(messages))
    } catch {
      /* storage unavailable/full — conversation just won't persist */
    }
  }, [messages, dataset])

  async function send(message: string) {
    if (!message.trim() || loading) return
    // Notices are UI-only markers, not conversation content.
    const history = messages.filter((m) => !m.notice)
    const sendGen = genRef.current
    const userStep: StoryStep = { role: 'user', narration: message, sql: null, columns: null, rows: null }
    setMessages((m) => [...m, userStep])
    setInput('')
    setLoading(true)
    setError(null)
    setPendingSql(null)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      for await (const event of streamStory({ message, history, dataset }, controller.signal)) {
        // The conversation moved on (dataset switched or was cleared) while
        // this was in flight — abort() was already called, but a step
        // already on the wire can still land here, so stop applying events
        // for a conversation that's no longer the active one.
        if (genRef.current !== sendGen) break

        if (event.type === 'tool_call') {
          setPendingSql(event.sql ?? null)
        } else if (event.type === 'step') {
          setPendingSql(null)
          setMessages((m) => [
            ...m,
            {
              role: event.role ?? 'assistant',
              narration: event.narration ?? null,
              sql: event.sql ?? null,
              columns: event.columns ?? null,
              rows: event.rows ?? null,
            },
          ])
        } else if (event.type === 'provider_switch') {
          // The primary provider failed mid-turn and the executor recovered
          // onto the fallback. Surface it inline rather than silently changing
          // voice halfway through the investigation.
          setPendingSql(null)
          setMessages((m) => [
            ...m,
            {
              role: 'assistant',
              narration: null,
              sql: null,
              columns: null,
              rows: null,
              // Headline is built from the structured fields, never by
              // parsing `message` — that string ends with the raw provider
              // error, which is JSON and may contain any punctuation.
              notice: `Continuing on ${event.to ?? 'the fallback model'} — ${
                event.from ?? 'the primary model'
              } was unavailable. Findings so far are kept.`,
              noticeDetail: event.message ?? null,
            },
          ])
        } else if (event.type === 'error') {
          setPendingSql(null)
          setError(event.message ?? 'The agent hit an error')
        }
        // "done" needs no handling — the loop just ends naturally after it
      }
    } catch (err) {
      if ((err as Error)?.name !== 'AbortError' && genRef.current === sendGen) {
        setError(apiErrorMessage(err))
      }
    } finally {
      if (genRef.current === sendGen) {
        setPendingSql(null)
        setLoading(false)
      }
      abortRef.current = null
    }
  }

  function stop() {
    abortRef.current?.abort()
  }

  // Starts a fresh conversation for the current dataset — aborts any
  // in-flight request (its late response is discarded via genRef, same as a
  // dataset switch) and clears both the in-memory and persisted transcript.
  function clear() {
    genRef.current += 1
    abortRef.current?.abort()
    setLoading(false)
    setPendingSql(null)
    setError(null)
    setInput('')
    setMessages([])
    try {
      sessionStorage.removeItem(storageKey(dataset))
    } catch {
      /* storage unavailable — nothing to remove */
    }
  }

  return (
    <StoryContext.Provider value={{ messages, pendingSql, loading, error, input, setInput, send, stop, clear }}>
      {children}
    </StoryContext.Provider>
  )
}

export function useStory() {
  const ctx = useContext(StoryContext)
  if (!ctx) throw new Error('useStory must be used within StoryProvider')
  return ctx
}
