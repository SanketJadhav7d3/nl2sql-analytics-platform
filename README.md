# Self-Service Analytics Platform

A cloud-deployed analytics platform on the **Brazilian E-Commerce (Olist)** dataset:
a PostgreSQL warehouse, a FastAPI backend with JWT/RBAC and an audit log, and an
LLM-powered natural-language-to-SQL assistant (with an agentic "Story" mode) —
behind a React dashboard.

**Live demo:** [analytics-frontend-421143431694.europe-west1.run.app](https://analytics-frontend-421143431694.europe-west1.run.app)

https://github.com/user-attachments/assets/7c0e6672-9cae-4dd5-9375-b1def725e1ef

https://github.com/user-attachments/assets/229f18ba-c3b7-4163-8260-385f4ceeec89

---

## Stack

- **Warehouse**: Postgres star schema (fact + dimensions), analytical views with window functions
- **API**: FastAPI, JWT auth, 3 roles (viewer/analyst/admin), audit log, guardrailed SQL execution on a read-only DB role
- **AI**: `/nl-query` (question → guarded SQL) and `/story` (multi-step agentic investigation, streamed via SSE) — Gemini, with automatic Groq fallback
- **Frontend**: React, deployed via Docker/nginx to Cloud Run

---

## Quick start

```bash
cp .env.example .env          # set GEMINI_API_KEY (or LLM_PROVIDER=echo)
docker compose up             # Postgres + API (loads the Olist CSVs from data/raw/)
cd frontend && npm install && npm run dev
```

API docs → `http://localhost:8000/docs` · Frontend → `http://localhost:5173` (log in as `admin`/`admin123`, or "Continue as Visitor")

Dataset: [Olist e-commerce CSVs](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), unzipped into `data/raw/`.

---

## Tests

```bash
pytest -q
```

---

## Deploy

Cloud-Run-friendly (binds `$PORT`). Deploy Postgres, the API
(`uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`), and the frontend
(`frontend/Dockerfile`, nginx proxying `/api` to the backend) as separate services.
