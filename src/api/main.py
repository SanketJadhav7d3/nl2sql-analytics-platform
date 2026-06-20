"""FastAPI application entrypoint for the reporting backend."""
from __future__ import annotations

from fastapi import FastAPI

from .routers import admin, auth, metrics, nlquery, query

app = FastAPI(
    title="Self-Service Analytics — Reporting API",
    version="0.4.0",
    description="KPI endpoints, JWT RBAC, audit log, vetted ad-hoc SQL, and NL-to-SQL.",
)

app.include_router(auth.router)
app.include_router(metrics.router)
app.include_router(query.router)
app.include_router(nlquery.router)
app.include_router(admin.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
