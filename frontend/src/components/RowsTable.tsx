export function RowsTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-ink-muted py-4">No rows returned.</p>
  }
  const columns = Object.keys(rows[0])

  return (
    <div className="overflow-x-auto rounded-lg border border-hairline">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-hairline bg-white/[0.03]">
            {columns.map((c) => (
              <th
                key={c}
                className="text-left px-3 py-2 font-medium text-ink-secondary whitespace-nowrap"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-hairline last:border-0 hover:bg-white/[0.02]">
              {columns.map((c) => (
                <td key={c} className="px-3 py-2 tabular text-ink-primary whitespace-nowrap">
                  {String(row[c] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
