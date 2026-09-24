import { useState, type FormEvent } from 'react'
import { useAskAI } from '../context/AskAIContext'
import { Card } from '../components/Card'
import { ResultsView } from '../components/ResultsView'
import { Spinner, ErrorNote } from '../components/Spinner'

const EXAMPLES = [
  'What were the top 5 categories by revenue last year?',
  'Which states have the slowest average delivery time?',
  'How many repeat customers do we have?',
  'What is the average order value by payment type?',
  'Which sellers have the highest average review score?',
  'What percentage of orders were delivered on time?',
  'Show monthly revenue growth for the last 12 months',
  'Which product category has the most items sold?',
  'What is the most common number of payment installments?',
  'Which customer state generates the most revenue?',
  'What is the average delivery time by product category?',
  'Which sellers have the lowest on-time delivery rate?',
]

function pickRandomExamples(n: number): string[] {
  const shuffled = [...EXAMPLES].sort(() => Math.random() - 0.5)
  return shuffled.slice(0, n)
}

export function AskAI() {
  const { question, setQuestion, result, loading, error, ask, clear } = useAskAI()
  const [examples, setExamples] = useState(() => pickRandomExamples(6))

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    ask(question)
  }

  const started = !!result || !!error || loading

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Ask AI</h1>
          <p className="text-sm text-ink-muted mt-1">
            Ask a question in plain English — it's turned into guarded, read-only SQL against the warehouse.
          </p>
        </div>
        {started && (
          <button
            onClick={clear}
            className="shrink-0 text-xs text-ink-secondary hover:text-ink-primary border border-hairline hover:border-hairline-strong rounded-lg px-3 py-1.5 transition-colors"
          >
            + New question
          </button>
        )}
      </div>

      <div className="text-xs text-warning bg-warning/10 border border-warning/25 rounded-lg px-3 py-2">
        This runs on a personal, rate-limited Gemini API key (a hobby project, not a production service) — you may
        occasionally hit the limit.
      </div>

      <form onSubmit={onSubmit} className="card p-4 flex gap-3">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. What was our revenue by month this year?"
          className="flex-1 bg-surface-raised border border-hairline rounded-lg px-3 py-2.5 text-sm outline-none focus:border-accent/60 focus:ring-2 focus:ring-accent/20 transition-all"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-accent hover:bg-accent-glow transition-colors text-white text-sm font-medium rounded-lg px-5 disabled:opacity-50"
        >
          {loading ? 'Thinking…' : 'Ask'}
        </button>
      </form>

      {!result && !loading && !error && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap gap-2">
            {examples.map((ex) => (
              <button
                key={ex}
                onClick={() => setQuestion(ex)}
                className="text-xs text-ink-secondary bg-white/5 hover:bg-white/10 border border-hairline rounded-full px-3 py-1.5 transition-colors"
              >
                {ex}
              </button>
            ))}
          </div>
          <button
            onClick={() => setExamples(pickRandomExamples(6))}
            className="self-start text-[11px] text-ink-muted hover:text-ink-secondary transition-colors"
          >
            ↻ Shuffle examples
          </button>
        </div>
      )}

      {loading && <Spinner label="Generating SQL and running query…" />}
      {error && <ErrorNote message={error} />}

      {result && (
        <div className="flex flex-col gap-4">
          <Card title="Generated SQL">
            <pre className="text-xs bg-surface-raised rounded-lg p-3 overflow-x-auto text-series-3 font-mono">
              {result.sql}
            </pre>
          </Card>
          <Card title={`Results`} subtitle={`${result.row_count} row${result.row_count === 1 ? '' : 's'}`}>
            <ResultsView rows={result.rows} />
          </Card>
        </div>
      )}
    </div>
  )
}
