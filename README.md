# Self-Service Analytics Platform

A cloud-deployed analytics platform on the **Brazilian E-Commerce (Olist)** dataset:
a PostgreSQL warehouse, a FastAPI backend with JWT/RBAC and an audit log, and an
LLM-powered natural-language-to-SQL assistant — behind a React dashboard.

```
React frontend  ──REST + JWT──▶  FastAPI backend  ──guarded SQL──▶  PostgreSQL
  dashboard · SQL console         /metrics · /query               star schema + views
  Ask AI · Story agent            /nl-query · /story
                                   auth · RBAC · audit log
                                        │
                                        └──▶ Gemini (fallback: Groq) — NL → SQL, or a
                                             multi-step agentic investigation ("Story")
```

**Live demo:** [analytics-frontend-421143431694.europe-west1.run.app](https://analytics-frontend-421143431694.europe-west1.run.app)

---

## What it demonstrates

| Component | Skill shown |
|---|---|
| Star-schema warehouse + analytical SQL (window functions, views) | SQL, data modelling |
| FastAPI backend, JWT auth, 3 roles, audit log | Backend services, access control |
| NL-to-SQL assistant with injection guardrails | Applied GenAI, secure-by-construction |
| Agentic "Story" endpoint — multi-step tool-calling, streamed via SSE | Agentic workflows |
| React dashboard + Docker, deployed to Cloud Run | Cloud architecture, full delivery |

---

## Quick start (local, Docker)

```bash
cp .env.example .env          # set GEMINI_API_KEY (or LLM_PROVIDER=echo to skip the LLM)
# ensure the 9 Olist CSVs are in data/raw/ (see Dataset below)
docker compose up
```

Brings up Postgres, runs the one-shot loader + auth seed, then starts the API:

- API + interactive docs → **http://localhost:8000/docs**
- Frontend (separately, `cd frontend && npm install && npm run dev`) → **http://localhost:5173**  (log in with `admin` / `admin123`, or "Continue as Visitor")

> Prefer running without Docker? See **[HOW_TO_RUN.md](HOW_TO_RUN.md)**.

---

## Dataset

[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
— ~100k real orders across 9 linked tables. Unzip the CSVs into `data/raw/` (gitignored).

---

## API surface

| Endpoint | Role | Purpose |
|---|---|---|
| `POST /auth/login` | any | exchange credentials for a JWT |
| `GET /metrics/*` | viewer+ | pre-computed KPIs (revenue, categories, AOV, delivery SLA, sellers, repeat customers) |
| `POST /nl-query` | viewer+ | natural-language question → guarded SQL → rows |
| `POST /story` | viewer+ | agentic multi-step investigation, streamed as SSE |
| `POST /query` | analyst+ | run vetted read-only SQL directly |
| `/admin/*` | admin | manage users, read the audit log |

Roles: **viewer** ⊂ **analyst** (+ `/query`) ⊂ **admin** (+ user management).

---

## How the guardrails work

Every LLM-generated SQL statement — from `/nl-query` or the `/story` agent — passes
through `sql_guard.py` before it runs: single statement, no comments, must start with
`SELECT`/`WITH`, a DML/DDL keyword blocklist, a table allow-list, and a hard `LIMIT`.
Execution then happens on a dedicated **read-only Postgres role**, so even a guardrail
bypass hits a database permission wall. `authorized(*roles)` — one FastAPI dependency —
gates every protected route and writes an audit row for every decision, allowed or denied.

If Gemini errors (e.g. quota exhausted), both LLM endpoints automatically retry on
**Groq**, with its own backoff-and-fallback-model logic for Groq's rate limits.

---

## Tests

```bash
pytest -q          # metric logic, RBAC allow/deny matrix, NL-to-SQL guardrails
```

Guardrail tests feed malicious "model output" through a fake adapter and assert
each is rejected — no API key needed.

---

## Deploy

Cloud-Run-friendly (binds `$PORT`). Three pieces, each independently deployable:

1. **PostgreSQL** — managed instance or a container.
2. **API** — `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`.
3. **Frontend** — static build served via the included `frontend/Dockerfile` (nginx, proxies `/api` to the backend).

Run the loader/seed once against the cloud DB: `python -m src.warehouse.load` then
`python -m src.api.auth.manage init`.

---

## Build order (milestones)

1. Warehouse — schema, loader, analytical views ✅
2. Reporting API — `/metrics/*`, pytest coverage ✅
3. Auth + RBAC — JWT, roles, audit log ✅
4. NL-to-SQL — guardrailed `/nl-query` ✅
5. Dashboard — Streamlit, then rebuilt in React ✅
6. Deploy — containerised, live on Cloud Run ✅
7. Agentic Story — multi-step SQL investigation, streamed, dual-LLM fallback ✅

---

> **Resume bullet:** Built and deployed a self-service analytics platform — a
> PostgreSQL warehouse, a FastAPI backend with JWT/RBAC and an audit log, a
> guardrailed NL-to-SQL assistant with an agentic multi-step investigation mode
> (streamed, dual-LLM fallback), and a React frontend — containerised and live
> on Cloud Run.
