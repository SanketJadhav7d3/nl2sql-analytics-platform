import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { api, clearStorySessions } from '../lib/api'
import type { Role, TokenResponse } from '../lib/types'

interface AuthState {
  username: string | null
  role: Role | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(localStorage.getItem('username'))
  const [role, setRole] = useState<Role | null>(localStorage.getItem('role') as Role | null)

  const login = useCallback(async (u: string, p: string) => {
    const { data } = await api.post<TokenResponse>('/auth/login', { username: u, password: p })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('role', data.role)
    localStorage.setItem('username', u)
    setUsername(u)
    setRole(data.role)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('role')
    localStorage.removeItem('username')
    clearStorySessions()
    setUsername(null)
    setRole(null)
  }, [])

  return (
    <AuthContext.Provider
      value={{ username, role, isAuthenticated: !!username, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
