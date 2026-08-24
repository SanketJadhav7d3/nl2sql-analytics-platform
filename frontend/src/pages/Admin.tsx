import { useEffect, useState, type FormEvent } from 'react'
import { api, apiErrorMessage } from '../lib/api'
import type { AuditEntry, Role, UserOut } from '../lib/types'
import { Card } from '../components/Card'
import { Spinner, ErrorNote } from '../components/Spinner'

export function Admin() {
  const [users, setUsers] = useState<UserOut[] | null>(null)
  const [audit, setAudit] = useState<AuditEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState<Role>('viewer')
  const [creating, setCreating] = useState(false)

  function refresh() {
    Promise.all([api.get<UserOut[]>('/admin/users'), api.get<AuditEntry[]>('/admin/audit-log', { params: { limit: 50 } })])
      .then(([u, a]) => {
        setUsers(u.data)
        setAudit(a.data)
      })
      .catch((err) => setError(apiErrorMessage(err)))
  }

  useEffect(refresh, [])

  async function createUser(e: FormEvent) {
    e.preventDefault()
    setCreating(true)
    setError(null)
    try {
      await api.post('/admin/users', { username: newUsername, password: newPassword, role: newRole })
      setNewUsername('')
      setNewPassword('')
      setNewRole('viewer')
      refresh()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setCreating(false)
    }
  }

  async function toggleActive(u: UserOut) {
    try {
      await api.patch(`/admin/users/${u.id}`, { is_active: !u.is_active })
      refresh()
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  async function changeRole(u: UserOut, role: Role) {
    try {
      await api.patch(`/admin/users/${u.id}`, { role })
      refresh()
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  async function deleteUser(u: UserOut) {
    if (!confirm(`Delete user "${u.username}"?`)) return
    try {
      await api.delete(`/admin/users/${u.id}`)
      refresh()
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  if (error && !users) return <ErrorNote message={error} />
  if (!users || !audit) return <Spinner label="Loading admin panel…" />

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Admin</h1>
        <p className="text-sm text-ink-muted mt-1">Manage users and review the access audit log.</p>
      </div>

      {error && <ErrorNote message={error} />}

      <Card title="Users">
        <table className="w-full text-sm mb-4">
          <thead>
            <tr className="border-b border-hairline text-ink-secondary">
              <th className="text-left py-2 pr-4 font-medium">Username</th>
              <th className="text-left py-2 pr-4 font-medium">Role</th>
              <th className="text-left py-2 pr-4 font-medium">Status</th>
              <th className="text-left py-2 pr-4 font-medium">Created</th>
              <th className="text-right py-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-hairline last:border-0 hover:bg-white/[0.02]">
                <td className="py-2 pr-4">{u.username}</td>
                <td className="py-2 pr-4">
                  <select
                    value={u.role}
                    onChange={(e) => changeRole(u, e.target.value as Role)}
                    className="bg-surface-raised border border-hairline rounded px-2 py-1 text-xs outline-none focus:border-accent/60"
                  >
                    <option value="viewer">viewer</option>
                    <option value="analyst">analyst</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
                <td className="py-2 pr-4">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      u.is_active ? 'bg-good/15 text-good' : 'bg-critical/15 text-critical'
                    }`}
                  >
                    {u.is_active ? 'active' : 'disabled'}
                  </span>
                </td>
                <td className="py-2 pr-4 text-ink-muted text-xs tabular">
                  {new Date(u.created_at).toLocaleDateString()}
                </td>
                <td className="py-2 text-right">
                  <button
                    onClick={() => toggleActive(u)}
                    className="text-xs text-ink-secondary hover:text-ink-primary mr-3"
                  >
                    {u.is_active ? 'Disable' : 'Enable'}
                  </button>
                  <button onClick={() => deleteUser(u)} className="text-xs text-critical hover:text-critical/80">
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <form onSubmit={createUser} className="flex items-end gap-3 border-t border-hairline pt-4">
          <div className="flex flex-col gap-1 flex-1">
            <label className="text-xs text-ink-secondary">Username</label>
            <input
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
              required
              className="bg-surface-raised border border-hairline rounded-lg px-3 py-1.5 text-sm outline-none focus:border-accent/60"
            />
          </div>
          <div className="flex flex-col gap-1 flex-1">
            <label className="text-xs text-ink-secondary">Password</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              className="bg-surface-raised border border-hairline rounded-lg px-3 py-1.5 text-sm outline-none focus:border-accent/60"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-ink-secondary">Role</label>
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value as Role)}
              className="bg-surface-raised border border-hairline rounded-lg px-3 py-1.5 text-sm outline-none focus:border-accent/60"
            >
              <option value="viewer">viewer</option>
              <option value="analyst">analyst</option>
              <option value="admin">admin</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={creating}
            className="bg-accent hover:bg-accent-glow transition-colors text-white text-sm font-medium rounded-lg px-4 py-1.5 disabled:opacity-50"
          >
            Add user
          </button>
        </form>
      </Card>

      <Card title="Audit Log" subtitle="Most recent 50 actions">
        <div className="overflow-x-auto max-h-96 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-surface">
              <tr className="border-b border-hairline text-ink-secondary">
                <th className="text-left py-2 pr-4 font-medium">Time</th>
                <th className="text-left py-2 pr-4 font-medium">User</th>
                <th className="text-left py-2 pr-4 font-medium">Action</th>
                <th className="text-left py-2 pr-4 font-medium">Status</th>
                <th className="text-left py-2 font-medium">Detail</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((a) => (
                <tr key={a.id} className="border-b border-hairline last:border-0 hover:bg-white/[0.02]">
                  <td className="py-1.5 pr-4 text-ink-muted tabular whitespace-nowrap">
                    {new Date(a.created_at).toLocaleString()}
                  </td>
                  <td className="py-1.5 pr-4">{a.username ?? '—'}</td>
                  <td className="py-1.5 pr-4 font-mono">{a.action}</td>
                  <td className="py-1.5 pr-4">
                    <span
                      className={
                        a.status === 'allowed'
                          ? 'text-good'
                          : a.status === 'denied'
                            ? 'text-warning'
                            : 'text-critical'
                      }
                    >
                      {a.status}
                    </span>
                  </td>
                  <td className="py-1.5 text-ink-muted max-w-md truncate">{a.detail ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
