import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { apiErrorMessage } from '../lib/api'
import { ErrorNote } from '../components/Spinner'
import { ParticleField } from '../components/ParticleField'

const VISITOR_USERNAME = 'visitor'
const VISITOR_PASSWORD = 'visitor-guest-2026'

export function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [visitorLoading, setVisitorLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(username, password)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  async function continueAsVisitor() {
    setError(null)
    setVisitorLoading(true)
    try {
      await login(VISITOR_USERNAME, VISITOR_PASSWORD)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setVisitorLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center px-4">
      <div className="starfield" />
      <ParticleField />
      <div className="relative z-10 w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <Link to="/">
            <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-accent to-series-7 shadow-[0_0_30px_rgba(109,123,255,0.6)] mb-4" />
          </Link>
          <h1 className="text-xl font-semibold">Orbit Analytics</h1>
          <p className="text-sm text-ink-muted mt-1">Sign in to view the warehouse</p>
        </div>

        <form onSubmit={onSubmit} className="card p-6 flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-ink-secondary">Username</label>
            <input
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="bg-surface-raised border border-hairline rounded-lg px-3 py-2 text-sm outline-none focus:border-accent/60 focus:ring-2 focus:ring-accent/20 transition-all"
              placeholder="admin"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-ink-secondary">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="bg-surface-raised border border-hairline rounded-lg px-3 py-2 text-sm outline-none focus:border-accent/60 focus:ring-2 focus:ring-accent/20 transition-all"
              placeholder="••••••••"
            />
          </div>

          {error && <ErrorNote message={error} />}

          <button
            type="submit"
            disabled={loading || visitorLoading}
            className="mt-1 bg-accent hover:bg-accent-glow transition-colors text-white text-sm font-medium rounded-lg py-2.5 disabled:opacity-50"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>

          <div className="flex items-center gap-3 text-[11px] text-ink-muted">
            <div className="flex-1 h-px bg-hairline" />
            or
            <div className="flex-1 h-px bg-hairline" />
          </div>

          <button
            type="button"
            onClick={continueAsVisitor}
            disabled={loading || visitorLoading}
            className="bg-white/5 hover:bg-white/10 border border-hairline transition-colors text-ink-primary text-sm font-medium rounded-lg py-2.5 disabled:opacity-50"
          >
            {visitorLoading ? 'Signing in…' : 'Continue as Visitor'}
          </button>
          <p className="text-[11px] text-ink-muted text-center -mt-1">
            Read-only access to the dashboard and Ask AI. No account needed.
          </p>
        </form>
      </div>
    </div>
  )
}
