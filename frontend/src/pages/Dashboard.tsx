import { useEffect, useState } from 'react'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from 'recharts'
import { api, apiErrorMessage } from '../lib/api'
import type {
  RevenueResponse,
  CategoryPerformance,
  AovResponse,
  DeliverySlaResponse,
  SellerScore,
  RepeatCustomersResponse,
  Dataset,
} from '../lib/types'
import { useDataset } from '../context/DatasetContext'
import { Card } from '../components/Card'
import { StatTile } from '../components/StatTile'
import { Spinner, ErrorNote } from '../components/Spinner'

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n)
const pct = (n: number | null) => (n === null ? '—' : `${n.toFixed(1)}%`)

const CATEGORY_COLORS = [
  'var(--color-series-1)',
  'var(--color-series-2)',
  'var(--color-series-3)',
  'var(--color-series-4)',
  'var(--color-series-5)',
  'var(--color-series-6)',
  'var(--color-series-7)',
  'var(--color-series-8)',
]

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="card px-3 py-2 text-xs shadow-xl">
      <p className="text-ink-muted mb-1">{label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} className="tabular text-ink-primary">
          {p.name}: <span className="font-medium">{typeof p.value === 'number' ? p.value.toLocaleString() : p.value}</span>
        </p>
      ))}
    </div>
  )
}

interface DashboardData {
  revenue: RevenueResponse
  categories: CategoryPerformance[]
  aov: AovResponse
  sla: DeliverySlaResponse
  sellers: SellerScore[]
  repeat: RepeatCustomersResponse
}

// Module-level cache: survives route unmount/remount within the session,
// so navigating away and back doesn't refetch. Keyed per dataset so switching
// datasets doesn't show stale data from the other one. Cleared on page reload.
const cache: Partial<Record<Dataset, DashboardData>> = {}

function fetchDashboardData(dataset: Dataset): Promise<DashboardData> {
  const params = { dataset }
  return Promise.all([
    api.get<RevenueResponse>('/metrics/revenue', { params: { ...params, granularity: 'month' } }),
    api.get<CategoryPerformance[]>('/metrics/categories/top', { params: { ...params, limit: 8 } }),
    api.get<AovResponse>('/metrics/aov', { params }),
    api.get<DeliverySlaResponse>('/metrics/delivery-sla', { params }),
    api.get<SellerScore[]>('/metrics/sellers/scorecard', { params: { ...params, limit: 8 } }),
    api.get<RepeatCustomersResponse>('/metrics/repeat-customers', { params }),
  ]).then(([r, c, a, s, sc, rc]) => ({
    revenue: r.data,
    categories: c.data,
    aov: a.data,
    sla: s.data,
    sellers: sc.data,
    repeat: rc.data,
  }))
}

export function Dashboard() {
  const { dataset } = useDataset()
  const [data, setData] = useState<DashboardData | null>(cache[dataset] ?? null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  function load() {
    setRefreshing(true)
    setError(null)
    fetchDashboardData(dataset)
      .then((d) => {
        cache[dataset] = d
        setData(d)
      })
      .catch((err) => setError(apiErrorMessage(err)))
      .finally(() => setRefreshing(false))
  }

  useEffect(() => {
    const cached = cache[dataset]
    if (cached) {
      setData(cached)
    } else {
      setData(null)
      load()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset])

  if (error && !data) return <ErrorNote message={error} />
  if (!data) return <Spinner label="Loading dashboard…" />

  const { revenue, categories, aov, sla, sellers, repeat } = data
  const latest = revenue.points[revenue.points.length - 1]

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-ink-muted mt-1">Revenue, delivery, and customer performance across the warehouse.</p>
        </div>
        <button
          onClick={load}
          disabled={refreshing}
          className="text-xs text-ink-secondary hover:text-ink-primary border border-hairline hover:border-hairline-strong rounded-lg px-3 py-1.5 transition-colors disabled:opacity-50"
        >
          {refreshing ? 'Refreshing…' : '↻ Refresh'}
        </button>
      </div>
      {error && <ErrorNote message={error} />}

      <div className="grid grid-cols-4 gap-4">
        <StatTile label="Avg. Order Value" value={money(aov.overall.aov)} />
        <StatTile
          label="Monthly Revenue"
          value={money(latest.revenue)}
          delta={latest.mom_growth_pct}
          deltaLabel="MoM"
        />
        <StatTile
          label="On-Time Delivery"
          value={pct(sla.overall.on_time_pct)}
          accent={(sla.overall.on_time_pct ?? 0) >= 85 ? 'good' : 'warning'}
        />
        <StatTile label="Repeat Customer Rate" value={pct(repeat.repeat_rate_pct)} accent="accent" />
      </div>

      <Card title="Revenue Trend" subtitle="Monthly revenue with cumulative total">
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={revenue.points} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
            <CartesianGrid stroke="var(--color-hairline)" vertical={false} />
            <XAxis
              dataKey="period"
              stroke="var(--color-ink-muted)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: 'var(--color-hairline-strong)' }}
            />
            <YAxis
              stroke="var(--color-ink-muted)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
              width={50}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'var(--color-hairline-strong)' }} />
            <Line
              type="monotone"
              dataKey="revenue"
              name="Revenue"
              stroke="var(--color-series-1)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <div className="grid grid-cols-2 gap-6">
        <Card title="Top Categories by Revenue">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={categories} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid stroke="var(--color-hairline)" horizontal={false} />
              <XAxis
                type="number"
                stroke="var(--color-ink-muted)"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
              />
              <YAxis
                type="category"
                dataKey="category"
                stroke="var(--color-ink-muted)"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={110}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
              <Bar dataKey="revenue" name="Revenue" radius={[0, 4, 4, 0]}>
                {categories.map((_, i) => (
                  <Cell key={i} fill={CATEGORY_COLORS[i % CATEGORY_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Delivery SLA by State" subtitle="Top states by delivered items">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={sla.by_state.slice(0, 8)} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid stroke="var(--color-hairline)" vertical={false} />
              <XAxis
                dataKey="customer_state"
                stroke="var(--color-ink-muted)"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: 'var(--color-hairline-strong)' }}
              />
              <YAxis
                stroke="var(--color-ink-muted)"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => `${v}%`}
                width={40}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
              <Bar dataKey="on_time_pct" name="On-time %" fill="var(--color-series-3)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card title="Seller Scorecard" subtitle="Top sellers by revenue">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline text-ink-secondary">
                <th className="text-left py-2 pr-4 font-medium">#</th>
                <th className="text-left py-2 pr-4 font-medium">Seller</th>
                <th className="text-left py-2 pr-4 font-medium">State</th>
                <th className="text-right py-2 pr-4 font-medium">Revenue</th>
                <th className="text-right py-2 pr-4 font-medium">Orders</th>
                <th className="text-right py-2 pr-4 font-medium">Avg. Review</th>
                <th className="text-right py-2 font-medium">Avg. Delivery (d)</th>
              </tr>
            </thead>
            <tbody>
              {sellers.map((s) => (
                <tr key={s.seller_id} className="border-b border-hairline last:border-0 hover:bg-white/[0.02]">
                  <td className="py-2 pr-4 text-ink-muted tabular">{s.revenue_rank}</td>
                  <td className="py-2 pr-4 font-mono text-xs text-ink-secondary">{s.seller_id.slice(0, 10)}…</td>
                  <td className="py-2 pr-4">{s.seller_state ?? '—'}</td>
                  <td className="py-2 pr-4 text-right tabular">{money(s.revenue)}</td>
                  <td className="py-2 pr-4 text-right tabular">{s.orders}</td>
                  <td className="py-2 pr-4 text-right tabular">{s.avg_review_score?.toFixed(2) ?? '—'}</td>
                  <td className="py-2 text-right tabular">{s.avg_delivery_days?.toFixed(1) ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
