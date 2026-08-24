import { useState, type FormEvent } from 'react'
import { api, apiErrorMessage } from '../lib/api'
import type { QueryResponse } from '../lib/types'
import { Card } from '../components/Card'
import { ResultsView } from '../components/ResultsView'
import { Spinner, ErrorNote } from '../components/Spinner'

export function SqlConsole() {
  const [sql, setSql] = useState('select * from analytics.dim_product limit 10;')
  const [result, setResult] = useState<QueryResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!sql.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const { data } = await api.post<QueryResponse>('/query', { sql })
      setResult(data)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">SQL Console</h1>
        <p className="text-sm text-ink-muted mt-1">
          Run vetted, read-only SQL directly against the analytics schema.
        </p>
      </div>

      <form onSubmit={onSubmit} className="card p-4 flex flex-col gap-3">
        <textarea
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          rows={6}
          spellCheck={false}
          className="bg-surface-raised border border-hairline rounded-lg px-3 py-2.5 text-sm font-mono outline-none focus:border-accent/60 focus:ring-2 focus:ring-accent/20 transition-all resize-y"
        />
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className="bg-accent hover:bg-accent-glow transition-colors text-white text-sm font-medium rounded-lg px-5 py-2 disabled:opacity-50"
          >
            {loading ? 'Running…' : 'Run query'}
          </button>
        </div>
      </form>

      {loading && <Spinner label="Running query…" />}
      {error && <ErrorNote message={error} />}

      {result && (
        <Card title="Results" subtitle={`${result.row_count} row${result.row_count === 1 ? '' : 's'}`}>
          <ResultsView rows={result.rows} />
        </Card>
      )}
    </div>
  )
}
