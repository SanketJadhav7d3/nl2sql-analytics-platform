import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ParticleField } from '../components/ParticleField'

const RAW_TABLES = [
  {
    name: 'customers',
    desc: 'One row per order-level customer identity.',
    columns: ['customer_id', 'customer_unique_id', 'customer_zip_code_prefix', 'customer_city', 'customer_state'],
  },
  {
    name: 'orders',
    desc: 'Order status and every timestamp in its lifecycle.',
    columns: [
      'order_id', 'customer_id', 'order_status', 'order_purchase_timestamp',
      'order_approved_at', 'order_delivered_carrier_date', 'order_delivered_customer_date',
      'order_estimated_delivery_date',
    ],
  },
  {
    name: 'order_items',
    desc: 'One row per line item — the grain the whole warehouse is built on.',
    columns: ['order_id', 'order_item_id', 'product_id', 'seller_id', 'shipping_limit_date', 'price', 'freight_value'],
  },
  {
    name: 'order_payments',
    desc: 'Payment method and installment plan per order.',
    columns: ['order_id', 'payment_sequential', 'payment_type', 'payment_installments', 'payment_value'],
  },
  {
    name: 'order_reviews',
    desc: 'Customer review score and free-text comments per order.',
    columns: ['review_id', 'order_id', 'review_score', 'review_comment_title', 'review_comment_message', 'review_creation_date'],
  },
  {
    name: 'products',
    desc: 'Product catalog with category and physical dimensions.',
    columns: ['product_id', 'product_category_name', 'product_weight_g', 'product_length_cm', 'product_height_cm', 'product_width_cm'],
  },
  {
    name: 'sellers',
    desc: 'Marketplace seller identity and location.',
    columns: ['seller_id', 'seller_zip_code_prefix', 'seller_city', 'seller_state'],
  },
  {
    name: 'geolocation',
    desc: 'Lat/lng lookup by Brazilian zip-code prefix.',
    columns: ['geolocation_zip_code_prefix', 'geolocation_lat', 'geolocation_lng', 'geolocation_city', 'geolocation_state'],
  },
]

const ANALYTICS_OBJECTS = [
  { name: 'dim_product', desc: 'One row per product, with English category name resolved.' },
  { name: 'dim_customer', desc: 'Customer identity + location, keyed for repeat-purchase analysis.' },
  { name: 'dim_seller', desc: 'Seller identity + location.' },
  { name: 'dim_date', desc: 'Continuous daily calendar spanning the order history.' },
  { name: 'fct_order_items', desc: 'Fact table: one row per order line, with revenue, delivery days, and on-time flag computed.' },
  { name: 'vw_monthly_revenue', desc: 'Monthly revenue with running total and month-over-month growth %.' },
  { name: 'vw_category_performance', desc: 'Revenue, items sold, and rank per product category.' },
  { name: 'vw_seller_scorecard', desc: 'Revenue, review score, and delivery time per seller, ranked.' },
  { name: 'vw_delivery_sla', desc: 'On-time delivery % and average delivery days per customer state.' },
]

export function Home() {
  const { isAuthenticated } = useAuth()

  return (
    <div className="relative min-h-screen">
      <div className="starfield" />
      <ParticleField />
      <div className="relative z-10 max-w-5xl mx-auto px-6 py-16">
        <header className="flex items-center justify-between mb-16">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-accent to-series-7 shadow-[0_0_20px_rgba(109,123,255,0.5)]" />
            <span className="text-sm font-semibold">Orbit Analytics</span>
          </div>
          <Link
            to={isAuthenticated ? '/dashboard' : '/login'}
            className="text-sm bg-accent hover:bg-accent-glow transition-colors text-white font-medium rounded-lg px-4 py-2"
          >
            {isAuthenticated ? 'Go to Dashboard' : 'Sign in'}
          </Link>
        </header>

        <section className="mb-20">
          <h1 className="text-4xl font-semibold leading-tight mb-4">
            An analytics warehouse built on
            <br />
            <span className="text-accent-glow">100,000 real Brazilian e-commerce orders</span>
          </h1>
          <p className="text-ink-secondary text-base max-w-2xl leading-relaxed">
            This platform is built on the{' '}
            <span className="text-ink-primary font-medium">Olist Brazilian E-Commerce Public Dataset</span> — real,
            anonymized orders placed on the Olist marketplace between{' '}
            <span className="text-ink-primary font-medium">September 2016 and September 2018</span>. It covers the
            full order lifecycle: purchase, payment, delivery, and customer review, across multiple sellers and
            product categories.
          </p>
          <div className="flex gap-3 mt-8">
            <Link
              to={isAuthenticated ? '/dashboard' : '/login'}
              className="text-sm bg-accent hover:bg-accent-glow transition-colors text-white font-medium rounded-lg px-5 py-2.5"
            >
              Explore the dashboard
            </Link>
            <Link
              to="/login"
              className="text-sm bg-white/5 hover:bg-white/10 border border-hairline transition-colors text-ink-primary font-medium rounded-lg px-5 py-2.5"
            >
              Continue as visitor
            </Link>
          </div>
        </section>

        <section className="mb-20">
          <h2 className="text-xl font-semibold mb-2">Raw source tables</h2>
          <p className="text-sm text-ink-muted mb-6">
            Nine CSVs, loaded verbatim into a <code className="text-series-3">raw</code> schema before any cleaning.
          </p>
          <div className="grid grid-cols-2 gap-4">
            {RAW_TABLES.map((t) => (
              <div key={t.name} className="card p-4">
                <p className="text-sm font-medium text-ink-primary mb-1">
                  raw.<span className="text-series-1">{t.name}</span>
                </p>
                <p className="text-xs text-ink-muted mb-3">{t.desc}</p>
                <div className="flex flex-wrap gap-1">
                  {t.columns.map((c) => (
                    <span key={c} className="text-[10px] font-mono bg-white/5 border border-hairline rounded px-1.5 py-0.5 text-ink-secondary">
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="mb-20">
          <h2 className="text-xl font-semibold mb-2">Analytics schema</h2>
          <p className="text-sm text-ink-muted mb-6">
            A star-style model built from the raw layer — this is what the dashboard, SQL console, and Ask AI all
            query against.
          </p>
          <div className="grid grid-cols-3 gap-3">
            {ANALYTICS_OBJECTS.map((o) => (
              <div key={o.name} className="card p-4">
                <p className="text-sm font-medium mb-1">
                  <span className="text-series-3">analytics.</span>
                  <span className="text-ink-primary">{o.name}</span>
                </p>
                <p className="text-xs text-ink-muted">{o.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <footer className="text-xs text-ink-muted border-t border-hairline pt-6">
          Source: Olist Store, "Brazilian E-Commerce Public Dataset by Olist" (Kaggle). Data is static and does not
          update beyond September 2018.
        </footer>
      </div>
    </div>
  )
}
