export type Role = 'viewer' | 'analyst' | 'admin'
export type Dataset = 'olist' | 'us'

export interface TokenResponse {
  access_token: string
  token_type: string
  role: Role
}

export interface UserOut {
  id: number
  username: string
  role: Role
  is_active: boolean
  created_at: string
}

export interface AuditEntry {
  id: number
  username: string | null
  role: string | null
  action: string
  detail: string | null
  status: string
  created_at: string
}

export interface QueryResponse {
  sql: string
  row_count: number
  rows: Record<string, unknown>[]
}

export interface NLQueryResponse extends QueryResponse {
  question: string
}

export interface RevenuePoint {
  period: string
  revenue: number
  orders: number
  running_total_revenue: number
  mom_growth_pct: number | null
}

export interface RevenueResponse {
  granularity: string
  date_from: string | null
  date_to: string | null
  points: RevenuePoint[]
}

export interface CategoryPerformance {
  revenue_rank: number
  category: string
  revenue: number
  items_sold: number
  orders: number
  avg_review_score: number | null
  revenue_share_pct: number
}

export interface AovResponse {
  overall: { revenue: number; orders: number; aov: number }
  by_category: { category: string; aov: number; orders: number; revenue: number }[]
  by_payment_type: { payment_type: string; aov: number; orders: number; revenue: number }[]
}

export interface DeliverySlaResponse {
  overall: { delivered_items: number; avg_delivery_days: number | null; on_time_pct: number | null }
  by_state: {
    customer_state: string
    delivered_items: number
    avg_delivery_days: number | null
    on_time_pct: number | null
  }[]
}

export interface SellerScore {
  revenue_rank: number
  seller_id: string
  seller_state: string | null
  revenue: number
  items_sold: number
  orders: number
  avg_review_score: number | null
  avg_delivery_days: number | null
}

export interface StoryStep {
  role: 'user' | 'assistant'
  narration: string | null
  sql: string | null
  columns: string[] | null
  rows: Record<string, unknown>[] | null
}

export interface StoryRequest {
  message: string
  history: StoryStep[]
  dataset: Dataset
}

export interface StoryResponse {
  steps: StoryStep[]
}

export interface RepeatCustomersResponse {
  total_customers: number
  repeat_customers: number
  repeat_rate_pct: number
  total_revenue: number
  repeat_revenue: number
  repeat_revenue_share_pct: number
}
