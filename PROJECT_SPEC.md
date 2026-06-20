# Self-Service Analytics Platform — Project Brief

A cloud-ready analytics platform with a SQL data warehouse, a reporting backend that
serves business KPIs over a REST API, role-based access control, a dashboard, and a
natural-language-to-SQL assistant powered by an LLM.

This brief is the build spec. Hand it to Claude Code and build it milestone by milestone.

---

## 1. Why this project

It mirrors a real "Data & Business Intelligence" engineering role. Each component maps to
a concrete responsibility an employer cares about:

| Component | What it demonstrates |
|---|---|
| Relational warehouse + analytical SQL | SQL, databases, data modelling |
| Reporting backend (REST API) | Backend services, business logic in a reporting layer |
| Role-based access control | Managing access rights, roles and permissions |
| Dashboard | Business intelligence / reporting |
| Natural-language-to-SQL assistant | Prototyping applied GenAI use cases |
| Cloud deployment | Cloud architecture, data platforms |

The goal is one cohesive, demo-able product — not six disconnected scripts.

---

## 2. Dataset

**Brazilian E-Commerce Public Dataset by Olist** (Kaggle).
`https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce`

- ~100,000 real (anonymised) orders, 2016–2018, across Brazilian marketplaces.
- Genuinely relational: 9 linked tables, which is what makes the SQL meaningful (joins,
  window functions, views) rather than a single flat file.
- Rich business semantics: revenue, order value, delivery performance, review scores,
  product categories, seller and customer geography — exactly the dimensions a BI team
  reports on.

**Tables**

- `olist_orders_dataset` — order status, purchase/approval/delivery timestamps
- `olist_order_items_dataset` — line items, price, freight
- `olist_order_payments_dataset` — payment type, installments, value
- `olist_order_reviews_dataset` — review scores and comments
- `olist_products_dataset` — product attributes, category
- `olist_customers_dataset` — customer location
- `olist_sellers_dataset` — seller location
- `olist_geolocation_dataset` — zip-code → lat/lng
- `product_category_name_translation` — category names in English

> A ready-made SQLite version also exists if you want to skip CSV loading during early
> prototyping: `https://www.kaggle.com/datasets/terencicp/e-commerce-dataset-by-olist-as-an-sqlite-database`.
> Recommendation: prototype on SQLite, then move to PostgreSQL for the real build so you
> can show production-grade SQL and access control.

---

## 3. Architecture

```
                +------------------+
   NL question  |  Dashboard (UI)  |  charts + "Ask your data" box
  ------------> |  React / Streamlit|
                +---------+--------+
                          | REST (JWT)
                +---------v--------+
                | Reporting Backend |  FastAPI
                |  - /metrics/*     |  business-logic endpoints
                |  - /nl-query      |  NL -> SQL
                |  - auth + RBAC    |
                +---------+--------+
                          | parameterised SQL
                +---------v--------+
                |   PostgreSQL      |  star-style warehouse + views
                +------------------+
```

---

## 4. Data model

Load the raw CSVs into a `raw` schema, then build an `analytics` schema with cleaned,
query-friendly views/tables:

- `fct_order_items` — one row per order line, joined to order, product, payment, customer,
  seller, with computed fields (item_revenue = price + freight, delivery_days, on_time flag).
- `dim_product` (with English category), `dim_customer`, `dim_seller`, `dim_date`.
- Pre-aggregated views used by the API, e.g. `vw_monthly_revenue`, `vw_category_performance`,
  `vw_seller_scorecard`, `vw_delivery_sla`.

Use at least a few **window functions** (running totals, month-over-month growth,
rank of categories by revenue) so the SQL clearly shows analytical depth.

---

## 5. Reporting backend (FastAPI)

Metric endpoints (each computes business logic server-side, returns JSON ready to chart):

- `GET /metrics/revenue?from=&to=&granularity=month` — revenue trend
- `GET /metrics/categories/top?limit=10` — top categories by revenue
- `GET /metrics/aov` — average order value, overall and by category/payment type
- `GET /metrics/delivery-sla` — % delivered on time, avg delivery days, by state
- `GET /metrics/sellers/scorecard` — seller revenue + avg review score
- `GET /metrics/repeat-customers` — repeat-purchase rate and revenue share

Rules:
- All SQL parameterised (no string interpolation).
- Pydantic response models.
- A thin service layer between routes and the DB so logic is testable.

---

## 6. Role-based access control

JWT auth with three roles, enforced as FastAPI dependencies:

- **viewer** — read-only access to aggregated `/metrics/*` endpoints only.
- **analyst** — everything viewer has, plus a `/query` endpoint that runs vetted read-only
  SQL against the `analytics` schema.
- **admin** — manage users and roles (`/admin/users`), see audit log.

Add a simple **audit log** table recording who queried what and when. This single feature
is what makes "manages access rights, roles and permissions" a demonstrated skill rather
than a buzzword.

---

## 7. Natural-language-to-SQL assistant

`POST /nl-query` with `{ "question": "top 5 product categories by revenue in 2018" }`:

1. Build a prompt containing the `analytics` schema (table + column names, descriptions).
2. Call an LLM to generate a **single read-only** SQL statement.
3. **Guardrails:** reject anything that isn't a single `SELECT`; enforce a `LIMIT`; run
   against a read-only DB role; validate against an allow-list of tables/views.
4. Execute, then return both the generated SQL (for transparency) and the result rows.
5. The dashboard renders the result as a table or auto-selected chart.

Keep the LLM provider behind an interface so it's swappable. This is the component that
shows applied GenAI on top of a real data platform.

---

## 8. Tech stack

- **DB:** PostgreSQL (Docker). SQLite acceptable for the earliest prototype.
- **Backend:** Python, FastAPI, SQLAlchemy (Core or 2.0), Pydantic, `python-jose` for JWT.
- **Frontend:** Streamlit for speed, or React if you want a stronger portfolio piece.
- **LLM:** any provider behind a small adapter interface.
- **Infra:** Docker Compose for local; deployable to a cloud run-style container service.
- **Quality:** pytest for the service layer and the NL-to-SQL guardrails; a Makefile or
  task runner; a seed script that loads the CSVs.

---

## 9. Build order (milestones)

1. **Warehouse** — Docker Postgres, schema, CSV loader, `analytics` views with window functions.
2. **Read-only API** — the `/metrics/*` endpoints over the views; pytest coverage.
3. **Auth + RBAC** — users, roles, JWT, dependency guards, audit log.
4. **NL-to-SQL** — `/nl-query` with strict guardrails and tests for the guardrails.
5. **Dashboard** — charts for each metric plus the "Ask your data" box.
6. **Deploy** — containerise, push to a cloud container service, write the README.

Ship milestone 1–3 first; that alone is a strong project. 4–6 make it stand out.

---

## 10. README / portfolio framing

In the final README, lead with a one-line architecture diagram, a screenshot of the
dashboard and the NL-to-SQL box, and a short "design decisions" section (why a star schema,
how the RBAC guards work, how the NL-to-SQL injection guardrails work). Recruiters skim
READMEs; make the data + access-control + GenAI story obvious in the first screen.

**Suggested resume bullet once built:**
> Built a self-service analytics platform: a PostgreSQL warehouse with analytical SQL views,
> a FastAPI reporting backend exposing KPI endpoints, JWT role-based access control with an
> audit log, and an LLM-powered natural-language-to-SQL assistant with injection guardrails;
> containerised and deployed to the cloud.