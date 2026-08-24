import type { ReactNode } from 'react'

export function Card({
  children,
  className = '',
  title,
  subtitle,
}: {
  children: ReactNode
  className?: string
  title?: string
  subtitle?: string
}) {
  return (
    <div className={`card p-5 ${className}`}>
      {title && (
        <div className="mb-4">
          <h3 className="text-sm font-medium text-ink-primary">{title}</h3>
          {subtitle && <p className="text-xs text-ink-muted mt-0.5">{subtitle}</p>}
        </div>
      )}
      {children}
    </div>
  )
}
