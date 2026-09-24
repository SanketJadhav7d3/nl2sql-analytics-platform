import { useEffect, useRef, type FormEvent } from 'react'
import type { StoryStep } from '../lib/types'
import { useStory } from '../context/StoryContext'
import { Card } from '../components/Card'
import { ResultsView } from '../components/ResultsView'
import { Markdown } from '../components/Markdown'
import { ErrorNote } from '../components/Spinner'

const THEMES = [
  'Our delivery performance',
  'Revenue trends over time',
  'How our top sellers are performing',
  'Customer loyalty and repeat purchases',
  'Which product categories are winning',
]

function StepBubble({ step }: { step: StoryStep }) {
  if (step.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-accent/15 border border-accent/30 rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm text-ink-primary">
          {step.narration}
        </div>
      </div>
    )
  }

  if (step.narration) {
    return (
      <div className="card p-4 max-w-full">
        <Markdown>{step.narration}</Markdown>
      </div>
    )
  }

  if (step.sql) {
    return (
      <Card className="!p-4 max-w-full">
        <details className="mb-3">
          <summary className="text-xs text-ink-muted cursor-pointer hover:text-ink-secondary">
            Query used for this finding
          </summary>
          <pre className="text-xs bg-surface-raised rounded-lg p-3 overflow-x-auto text-series-3 font-mono mt-2">
            {step.sql}
          </pre>
        </details>
        {step.rows && step.rows.length > 0 && <ResultsView rows={step.rows} />}
      </Card>
    )
  }

  return null
}

function PendingQuery({ sql }: { sql: string }) {
  return (
    <div className="card !p-4 flex items-start gap-2.5 text-xs text-ink-muted">
      <span className="h-3 w-3 mt-0.5 rounded-full border-2 border-accent/30 border-t-accent animate-spin shrink-0" />
      <pre className="font-mono whitespace-pre-wrap break-all">Running: {sql}</pre>
    </div>
  )
}

export function Story() {
  const { messages, pendingSql, loading, error, input, setInput, send, stop, clear } = useStory()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, pendingSql, loading])

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    send(input)
  }

  const started = messages.length > 0

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-4xl">
      <div className="shrink-0">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold">Story</h1>
            <p className="text-sm text-ink-muted mt-1">
              Give it a theme — an agent investigates the warehouse across several steps, narrates what it finds
              live, and you can keep asking follow-up questions.
            </p>
          </div>
          {started && (
            <button
              onClick={clear}
              className="shrink-0 text-xs text-ink-secondary hover:text-ink-primary border border-hairline hover:border-hairline-strong rounded-lg px-3 py-1.5 transition-colors"
            >
              + New conversation
            </button>
          )}
        </div>
        <div className="text-xs text-warning bg-warning/10 border border-warning/25 rounded-lg px-3 py-2 mt-3">
          Each message runs multiple AI steps against a personal, rate-limited key — expect it to take longer than
          Ask AI, and to occasionally hit quota limits.
        </div>
      </div>

      <div className="flex-1 overflow-y-auto flex flex-col gap-4 py-6 min-h-0">
        {!started && (
          <div className="flex flex-wrap gap-2">
            {THEMES.map((t) => (
              <button
                key={t}
                onClick={() => send(t)}
                className="text-xs text-ink-secondary bg-white/5 hover:bg-white/10 border border-hairline rounded-full px-3 py-1.5 transition-colors"
              >
                {t}
              </button>
            ))}
          </div>
        )}

        {messages.map((step, i) => (
          <StepBubble key={i} step={step} />
        ))}

        {pendingSql && <PendingQuery sql={pendingSql} />}

        {loading && !pendingSql && (
          <div className="flex items-center gap-2 text-ink-muted text-sm">
            <span className="h-3.5 w-3.5 rounded-full border-2 border-accent/30 border-t-accent animate-spin" />
            Thinking…
          </div>
        )}
        {error && <ErrorNote message={error} />}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={onSubmit} className="shrink-0 card p-3 flex gap-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={started ? 'Ask a follow-up…' : 'e.g. Our delivery performance'}
          className="flex-1 bg-surface-raised border border-hairline rounded-lg px-3 py-2.5 text-sm outline-none focus:border-accent/60 focus:ring-2 focus:ring-accent/20 transition-all"
        />
        {loading ? (
          <button
            type="button"
            onClick={stop}
            className="bg-white/5 hover:bg-white/10 border border-hairline transition-colors text-ink-primary text-sm font-medium rounded-lg px-5"
          >
            Stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim()}
            className="bg-accent hover:bg-accent-glow transition-colors text-white text-sm font-medium rounded-lg px-5 disabled:opacity-50"
          >
            {started ? 'Ask' : 'Tell the story'}
          </button>
        )}
      </form>
    </div>
  )
}
