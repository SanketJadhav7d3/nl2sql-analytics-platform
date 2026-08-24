import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ParticleField } from './ParticleField'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: OrbitIcon, roles: ['viewer', 'analyst', 'admin'] },
  { to: '/ask', label: 'Ask AI', icon: SparkIcon, roles: ['viewer', 'analyst', 'admin'] },
  { to: '/story', label: 'Story', icon: BookIcon, roles: ['viewer', 'analyst', 'admin'] },
  { to: '/query', label: 'SQL Console', icon: TerminalIcon, roles: ['analyst', 'admin'] },
  { to: '/admin', label: 'Admin', icon: ShieldIcon, roles: ['admin'] },
  { to: '/about', label: 'About the Data', icon: InfoIcon, roles: ['viewer', 'analyst', 'admin'] },
]

export function Layout() {
  const { username, role, logout } = useAuth()

  return (
    <div className="relative min-h-screen">
      <div className="starfield" />
      <ParticleField />
      <div className="relative z-10 flex min-h-screen">
        <aside className="w-60 shrink-0 border-r border-hairline flex flex-col px-4 py-6">
          <div className="flex items-center gap-2 px-2 mb-8">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-accent to-series-7 shadow-[0_0_20px_rgba(109,123,255,0.5)]" />
            <div>
              <p className="text-sm font-semibold leading-tight">Orbit Analytics</p>
              <p className="text-[11px] text-ink-muted leading-tight">Olist e-commerce</p>
            </div>
          </div>

          <nav className="flex flex-col gap-1">
            {navItems
              .filter((item) => !role || item.roles.includes(role))
              .map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                      isActive
                        ? 'bg-accent/15 text-ink-primary border border-accent/30'
                        : 'text-ink-secondary hover:bg-white/5 hover:text-ink-primary border border-transparent'
                    }`
                  }
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {label}
                </NavLink>
              ))}
          </nav>

          <div className="mt-auto pt-6 border-t border-hairline">
            <div className="flex items-center justify-between px-2">
              <div>
                <p className="text-sm font-medium truncate max-w-[120px]">{username}</p>
                <p className="text-[11px] text-ink-muted capitalize">{role}</p>
              </div>
              <button
                onClick={logout}
                className="text-xs text-ink-muted hover:text-critical transition-colors px-2 py-1 rounded"
              >
                Sign out
              </button>
            </div>
          </div>
        </aside>

        <main className="flex-1 min-w-0 px-8 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function OrbitIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" {...props}>
      <circle cx="12" cy="12" r="2.5" />
      <ellipse cx="12" cy="12" rx="9" ry="3.5" />
      <ellipse cx="12" cy="12" rx="3.5" ry="9" transform="rotate(60 12 12)" />
    </svg>
  )
}
function SparkIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" {...props}>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M18 6l-2.5 2.5M8.5 15.5L6 18" />
    </svg>
  )
}
function TerminalIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" {...props}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M7 9l3 3-3 3M13 15h4" />
    </svg>
  )
}
function ShieldIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" {...props}>
      <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" />
    </svg>
  )
}
function BookIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" {...props}>
      <path d="M4 5.5C4 4.7 4.7 4 5.5 4H12v16H5.5c-.8 0-1.5-.7-1.5-1.5v-13z" />
      <path d="M20 5.5c0-.8-.7-1.5-1.5-1.5H12v16h6.5c.8 0 1.5-.7 1.5-1.5v-13z" />
    </svg>
  )
}
function InfoIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5.5M12 8v.01" strokeLinecap="round" />
    </svg>
  )
}
