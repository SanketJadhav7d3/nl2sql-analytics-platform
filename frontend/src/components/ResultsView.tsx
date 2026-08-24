import { useMemo, useState } from 'react'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import { RowsTable } from './RowsTable'

const SERIES_COLORS = [
  'var(--color-series-1)',
  'var(--color-series-2)',
  'var(--color-series-3)',
  'var(--color-series-4)',
  'var(--color-series-5)',
  'var(--color-series-6)',
  'var(--color-series-7)',
  'var(--color-series-8)',
]

type ChartKind = 'table' | 'bar' | 'line' | 'pie'

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="card px-3 py-2 text-xs shadow-xl">
      {label !== undefined && <p className="text-ink-muted mb-1">{String(label)}</p>}
      {payload.map((p: any) => (
        <p key={p.dataKey ?? p.name} className="tabular text-ink-primary">
          {p.name}: <span className="font-medium">{typeof p.value === 'number' ? p.value.toLocaleString() : p.value}</span>
        </p>
      ))}
    </div>
  )
}

function isNumericValue(v: unknown): boolean {
  if (typeof v === 'number') return Number.isFinite(v)
  if (typeof v === 'string' && v.trim() !== '') return Number.isFinite(Number(v))
  return false
}

export function ResultsView({ rows }: { rows: Record<string, unknown>[] }) {
  const columns = useMemo(() => (rows.length ? Object.keys(rows[0]) : []), [rows])
  // a column counts as numeric only if every row's value for it parses as a number
  const numericColumns = useMemo(
    () => columns.filter((c) => rows.length > 0 && rows.every((r) => r[c] == null || isNumericValue(r[c]))),
    [columns, rows],
  )
  const categoricalColumns = useMemo(
    () => columns.filter((c) => !numericColumns.includes(c)),
    [columns, numericColumns],
  )

  const canChart = numericColumns.length > 0 && categoricalColumns.length > 0 && rows.length > 0
  const [kind, setKind] = useState<ChartKind>(canChart ? 'bar' : 'table')
  const [xKey, setXKey] = useState(categoricalColumns[0] ?? columns[0])
  const [yKey, setYKey] = useState(numericColumns[0])

  if (rows.length === 0) return <RowsTable rows={rows} />

  const activeX = categoricalColumns.includes(xKey) ? xKey : categoricalColumns[0]
  const activeY = numericColumns.includes(yKey) ? yKey : numericColumns[0]

  // cap to a readable number of marks/slices; coerce the y value to a real number for recharts
  const chartData = rows.slice(0, 25).map((r) => ({ ...r, [activeY]: Number(r[activeY]) }))

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1 bg-surface-raised border border-hairline rounded-lg p-1">
          {(['table', 'bar', 'line', 'pie'] as ChartKind[]).map((k) => (
            <button
              key={k}
              disabled={k !== 'table' && !canChart}
              onClick={() => setKind(k)}
              className={`text-xs px-3 py-1.5 rounded-md capitalize transition-colors disabled:opacity-30 disabled:cursor-not-allowed ${
                kind === k ? 'bg-accent text-white' : 'text-ink-secondary hover:text-ink-primary'
              }`}
            >
              {k}
            </button>
          ))}
        </div>

        {kind !== 'table' && canChart && (
          <>
            <label className="flex items-center gap-1.5 text-xs text-ink-secondary">
              {kind === 'pie' ? 'Slice by' : 'X axis'}
              <select
                value={activeX}
                onChange={(e) => setXKey(e.target.value)}
                className="bg-surface-raised border border-hairline rounded px-2 py-1 text-xs outline-none focus:border-accent/60"
              >
                {categoricalColumns.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-1.5 text-xs text-ink-secondary">
              {kind === 'pie' ? 'Value' : 'Y axis'}
              <select
                value={activeY}
                onChange={(e) => setYKey(e.target.value)}
                className="bg-surface-raised border border-hairline rounded px-2 py-1 text-xs outline-none focus:border-accent/60"
              >
                {numericColumns.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            {rows.length > 25 && (
              <span className="text-[11px] text-ink-muted">showing first 25 of {rows.length} rows</span>
            )}
          </>
        )}
      </div>

      {kind === 'table' && <RowsTable rows={rows} />}

      {kind === 'bar' && canChart && (
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
            <CartesianGrid stroke="var(--color-hairline)" vertical={false} />
            <XAxis
              dataKey={activeX}
              stroke="var(--color-ink-muted)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: 'var(--color-hairline-strong)' }}
              interval={0}
              angle={chartData.length > 8 ? -30 : 0}
              textAnchor={chartData.length > 8 ? 'end' : 'middle'}
              height={chartData.length > 8 ? 60 : 30}
            />
            <YAxis stroke="var(--color-ink-muted)" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} width={60} />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
            <Bar dataKey={activeY} radius={[4, 4, 0, 0]}>
              {chartData.map((_, i) => (
                <Cell key={i} fill={SERIES_COLORS[i % SERIES_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}

      {kind === 'line' && canChart && (
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
            <CartesianGrid stroke="var(--color-hairline)" vertical={false} />
            <XAxis
              dataKey={activeX}
              stroke="var(--color-ink-muted)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: 'var(--color-hairline-strong)' }}
            />
            <YAxis stroke="var(--color-ink-muted)" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} width={60} />
            <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'var(--color-hairline-strong)' }} />
            <Line
              type="monotone"
              dataKey={activeY}
              stroke="var(--color-series-1)"
              strokeWidth={2}
              dot={chartData.length <= 20}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      {kind === 'pie' && canChart && (
        <ResponsiveContainer width="100%" height={340}>
          <PieChart margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
            <Tooltip content={<ChartTooltip />} />
            <Legend wrapperStyle={{ fontSize: 12, color: 'var(--color-ink-secondary)' }} />
            <Pie
              data={chartData.slice(0, 8)}
              dataKey={activeY}
              nameKey={activeX}
              innerRadius={60}
              outerRadius={110}
              paddingAngle={2}
            >
              {chartData.slice(0, 8).map((_, i) => (
                <Cell key={i} fill={SERIES_COLORS[i % SERIES_COLORS.length]} stroke="var(--color-surface)" strokeWidth={2} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      )}

      {kind !== 'table' && !canChart && (
        <p className="text-sm text-ink-muted py-4">
          Charting needs at least one text/category column and one numeric column in the result.
        </p>
      )}
    </div>
  )
}
