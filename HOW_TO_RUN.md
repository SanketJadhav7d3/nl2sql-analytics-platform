# How to Run & Test

Self-Service Analytics Platform. All commands run from the project root
(`C:\Users\Darkness\Learnings\analytics-platform`) using the project's virtual
environment Python (`.\.venv\Scripts\python.exe`).

> Prerequisites: Docker Desktop running, and the `.venv` already created with
> dependencies installed (`.\.venv\Scripts\python.exe -m pip install -r requirements.txt`).

---

## 1. Start the database

```powershell
docker compose up -d
```

Postgres data lives in a Docker volume, so it stays loaded between restarts.

**First-time setup only** (or after wiping the volume) — load the data and seed auth:

```powershell
.\.venv\Scripts\python.exe -m src.warehouse.load          # load 9 CSVs + build analytics schema
.\.venv\Scripts\python.exe -m src.api.auth.manage init    # create app schema + seed admin / admin123
```

Create extra users if you want (role = viewer | analyst | admin):

```powershell
.\.venv\Scripts\python.exe -m src.api.auth.manage create-user alice pw123456 analyst
```

---

## 2. Start the API

The NL-to-SQL endpoint uses Google Gemini and needs `GOOGLE_API_KEY` (or
`GEMINI_API_KEY`) in the environment. Set it for the current terminal if needed:

```powershell
$env:GOOGLE_API_KEY = "your-key-here"
```

Then launch the server:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api.main:app --reload --port 8000
```

Interactive API docs: **http://127.0.0.1:8000/docs**

To run the NL-to-SQL pipeline **offline** (no API key, returns a fixed safe query):

```powershell
$env:LLM_PROVIDER = "echo"
.\.venv\Scripts\python.exe -m uvicorn src.api.main:app --reload --port 8000
```

---

## 3. Test it via the Swagger UI (easiest)

1. `POST /auth/login` with `{"username":"admin","password":"admin123"}` → copy the `access_token`.
2. Click **Authorize** (top-right), paste the token.
3. Try `GET /metrics/categories/top`, `GET /metrics/revenue`,
   then `POST /nl-query` with `{"question":"top 5 product categories by revenue"}`.
4. As admin, `GET /admin/audit-log` to see who ran what.

## 3b. Or test from PowerShell (server must be running)

```powershell
$tok = (Invoke-RestMethod -Method Post http://127.0.0.1:8000/auth/login `
        -ContentType application/json `
        -Body '{"username":"admin","password":"admin123"}').access_token
$h = @{ Authorization = "Bearer $tok" }

Invoke-RestMethod "http://127.0.0.1:8000/metrics/categories/top?limit=3" -Headers $h
Invoke-RestMethod -Method Post http://127.0.0.1:8000/nl-query -Headers $h `
  -ContentType application/json `
  -Body '{"question":"which 5 states have the worst on-time delivery?"}'
```

---

## 4. Launch the dashboard (Streamlit)

The dashboard talks to the API over HTTP, so the API (section 2) must be running.
In a separate terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard/app.py
```

Opens at **http://localhost:8501**. Log in from the sidebar (default admin / admin123).
You get a chart for each metric plus an **"Ask your data"** box (analyst/admin) that
calls `/nl-query` and shows the generated SQL.

If the API runs on a different host/port, point the dashboard at it:

```powershell
$env:API_BASE_URL = "http://127.0.0.1:8000"
```

---

## 5. Run the automated tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: **45 passed**. The database must be up (tests run against the loaded
warehouse). Tests use a fake LLM adapter, so no API key is needed.

---

## Roles (RBAC)

| Role    | Access                                                            |
|---------|-------------------------------------------------------------------|
| viewer  | `/metrics/*` (read-only)                                          |
| analyst | metrics + `POST /query` (vetted SQL) + `POST /nl-query`           |
| admin   | everything + `/admin/users` (manage users) + `/admin/audit-log`   |

Default seeded admin: **admin / admin123**.

---

## Stop everything

```powershell
# Ctrl+C in the uvicorn terminal to stop the API, then:
docker compose down        # stops Postgres (data volume is kept)
```

---

## Troubleshooting

- **`/nl-query` returns 400 "could not answer question"** → `GOOGLE_API_KEY`
  isn't set in that terminal, or the model produced SQL that failed a guardrail.
  Set the key, or use `LLM_PROVIDER=echo`.
- **`python` not found** → use the venv interpreter `.\.venv\Scripts\python.exe`
  (bare `python` hits the Windows Store alias on this machine).
- **Tests skipped / connection errors** → the database isn't up; run
  `docker compose up -d` first.
```
