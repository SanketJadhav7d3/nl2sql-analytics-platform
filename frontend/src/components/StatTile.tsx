export function StatTile({
  label,
  value,
  delta,
  deltaLabel,
  accent = 'accent',
}: {
  label: string
  value: string
  delta?: number | null
  deltaLabel?: string
  accent?: 'accent' | 'good' | 'warning' | 'critical'
}) {
  const accentColor = {
    accent: 'text-accent-glow',
    good: 'text-good',
    warning: 'text-warning',
    critical: 'text-critical',
  }[accent]

  const isUp = (delta ?? 0) >= 0

  return (
    <div className="card p-5 flex flex-col gap-2">
      <span className="text-xs font-medium text-ink-muted uppercase tracking-wide">{label}</span>
      <span className={`text-3xl font-semibold tabular ${accentColor}`}>{value}</span>
      {delta !== undefined && delta !== null && (
        <span className={`text-xs tabular ${isUp ? 'text-good' : 'text-critical'}`}>
          {isUp ? '▲' : '▼'} {Math.abs(delta).toFixed(1)}% {deltaLabel}
        </span>
      )}
    </div>
  )
}
