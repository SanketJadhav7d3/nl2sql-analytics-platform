# Milestone Prompts — Self-Service Analytics Platform

Paste these into Claude Code one at a time, in order. Run each as its own session (or clear
context between them) so the agent stays focused on a single milestone. `PROJECT_SPEC.md`
must be at the repo root.

A good habit for every milestone: let the agent restate a short plan first, glance at it,
then tell it to proceed. After it finishes, run the verification it gives you before moving on.

---

## Before you start (one-time setup)

- Create a free Kaggle account and download the Olist dataset
  (`https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce`).
- Unzip the CSVs into `data/raw/` in the repo.
- Have an LLM provider API key ready for Milestone 4 (not needed before then).

---

## Milestone 1 — Warehouse

```
Read PROJECT_SPEC.md in full. We are building ONLY Milestone 1 this session — do not start
any later milestone.

Set up: a Dockerised PostgreSQL via docker-compose; a `raw` schema matching the Olist CSVs
in data/raw/; a Python loader script that creates the schema and loads all 9 CSVs; and an
`analytics` schema with the cleaned fact/dim tables and the pre-aggregated views described
in sections 4 of the spec. Include at least three window functions (running total,
month-over-month growth, category rank by revenue).

First, restate a short plan and the file structure you'll create, then wait for me to say go.
After building, give me the exact commands to bring up the DB, run the loader, and a few
sample SQL queries I can run to confirm the views work.
```

---

## Milestone 2 — Read-only reporting API

```
Read PROJECT_SPEC.md. Milestone 1 (the Postgres warehouse and analytics views) is done.
We are building ONLY Milestone 2 this session — no auth, no NL-to-SQL, no frontend yet.

Build the FastAPI reporting backend with the /metrics/* endpoints in section 5 of the spec.
Requirements: a thin service layer between routes and the DB, SQLAlchemy with fully
parameterised SQL, Pydantic response models, and pytest tests for each endpoint's logic.

Restate a brief plan first. When done, give me the command to run the API locally and a
couple of example requests with expected-shape responses.
```

---

## Milestone 3 — Auth and role-based access control

```
Read PROJECT_SPEC.md. Milestones 1 and 2 are done. We are building ONLY Milestone 3.

Add JWT authentication and the three roles from section 6 (viewer, analyst, admin),
enforced as FastAPI dependencies. viewer = read-only /metrics/* access; analyst also gets
a /query endpoint for vetted read-only SQL against the analytics schema; admin manages
users/roles via /admin/users. Add an audit-log table that records who ran what and when.
Write pytest tests proving each role is correctly allowed or denied per endpoint.

Restate a short plan first. When done, show me how to create a user of each role and a
sequence of requests demonstrating the access rules and an audit-log entry.
```

---

## Milestone 4 — Natural-language-to-SQL assistant

```
Read PROJECT_SPEC.md. Milestones 1–3 are done. We are building ONLY Milestone 4.

Add POST /nl-query exactly as described in section 7. Put the LLM call behind a small
swappable adapter interface (I'll supply the API key via env var). Implement ALL guardrails:
reject anything that isn't a single read-only SELECT, enforce a LIMIT, run against a
read-only DB role, and validate table/view names against an allow-list. Return both the
generated SQL and the result rows. Write pytest tests specifically targeting the guardrails,
including malicious inputs (attempts at writes, multiple statements, disallowed tables).

Restate a short plan first, with emphasis on the guardrail design, before coding.
When done, show me example questions and their generated SQL + results.
```

---

## Milestone 5 — Dashboard

```
Read PROJECT_SPEC.md. Milestones 1–4 are done. We are building ONLY Milestone 5.

Build the dashboard from section 3: a chart for each /metrics/* endpoint plus an
"Ask your data" box that calls /nl-query and renders the returned rows as a table or an
auto-selected chart, and also shows the generated SQL for transparency. Use Streamlit for
speed unless you see a strong reason to use React — ask me before choosing React.
Wire it to the API using a logged-in token.

Restate a short plan first. When done, give me the command to launch the dashboard.
```

---

## Milestone 6 — Deploy and document

```
Read PROJECT_SPEC.md. Milestones 1–5 are done. We are building ONLY Milestone 6.

Containerise the full stack for deployment to a cloud container service, with clear env-var
configuration and a single docker-compose for local use. Then write the portfolio README per
section 10: a one-line architecture diagram, placeholders for a dashboard screenshot and the
NL-to-SQL box, and a "design decisions" section covering the star schema, the RBAC guards,
and the NL-to-SQL injection guardrails. Include setup, run, and deploy instructions.

Restate a short plan first. When done, list exactly what I need to provide (accounts, keys,
screenshots) to finish the deployment.
```

---

## Tips while building

- If a session drifts toward later milestones, stop it: "Stay within this milestone only."
- Commit after each milestone so you always have a working checkpoint.
- After Milestone 3 you already have a strong, demo-able project — a good point to update
  your resume even before finishing 4–6.