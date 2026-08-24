export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-ink-muted text-sm py-8 justify-center">
      <span className="h-3.5 w-3.5 rounded-full border-2 border-accent/30 border-t-accent animate-spin" />
      {label}
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="text-sm text-critical bg-critical/10 border border-critical/30 rounded-lg px-3 py-2">
      {message}
    </div>
  )
}
