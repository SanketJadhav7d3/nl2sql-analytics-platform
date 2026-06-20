"""Guardrails for ad-hoc SQL submitted to /query (and reused by /nl-query).

Defence in depth — a query must clear ALL of these before it runs:
  1. single statement (no stacked statements via ';')
  2. no SQL comments ('--', '/* */') that could hide payloads
  3. starts with SELECT or WITH (read-only shape)
  4. contains no DML/DDL/transaction keywords (blocklist)
  5. every FROM/JOIN target is an allow-listed `analytics` object
  6. a hard row cap is wrapped around it (enforced LIMIT)
And independently, execution happens on the `analytics_ro` Postgres role, which
has SELECT-only rights on the `analytics` schema and nothing else.
"""
from __future__ import annotations

import re

from sqlalchemy import text

from .config import settings
from .db import readonly_engine

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|merge|"
    r"call|copy|vacuum|analyze|reindex|comment|do|set|begin|commit|rollback|"
    r"savepoint|listen|notify|prepare|execute|into|lock|refresh)\b",
    re.IGNORECASE,
)
_STARTS_OK = re.compile(r"^\s*(with|select)\b", re.IGNORECASE)
_REFS = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][\w.]*)", re.IGNORECASE)
_CTE_NAMES = re.compile(r"([a-zA-Z_]\w*)\s+as\s*\(", re.IGNORECASE)
# SQL functions that use FROM/IN as an argument separator, e.g.
# EXTRACT(year FROM col) or SUBSTRING(x FROM 1 FOR 3). These must be stripped
# before scanning FROM/JOIN, or the column would be misread as a table.
_FUNC_FROM = re.compile(
    r"\b(?:extract|substring|trim|overlay|position)\s*\([^()]*\)",
    re.IGNORECASE,
)


class GuardrailError(ValueError):
    """Raised when a query fails validation."""


_allow_cache: set[str] | None = None


def _allowed_objects() -> set[str]:
    """Lowercased names of all tables + views in the analytics schema."""
    global _allow_cache
    if _allow_cache is None:
        with readonly_engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'analytics'
                    """
                )
            )
            _allow_cache = {r[0].lower() for r in rows}
    return _allow_cache


def validate(sql: str) -> None:
    """Raise GuardrailError if `sql` is not a safe, read-only analytics query."""
    if not sql or not sql.strip():
        raise GuardrailError("empty query")

    s = sql.strip().rstrip(";")

    if ";" in s:
        raise GuardrailError("multiple statements are not allowed")
    if "--" in s or "/*" in s:
        raise GuardrailError("SQL comments are not allowed")
    if not _STARTS_OK.match(s):
        raise GuardrailError("only SELECT/WITH (read-only) queries are allowed")
    if _FORBIDDEN.search(s):
        raise GuardrailError("query contains a forbidden (non-read-only) keyword")

    allowed = _allowed_objects()
    cte_names = {m.lower() for m in _CTE_NAMES.findall(s)}
    # Scan for table refs on a copy with FROM-using functions removed, so e.g.
    # EXTRACT(year FROM order_month) isn't mistaken for "FROM order_month".
    scan = _FUNC_FROM.sub(" ", s)
    for ref in _REFS.findall(scan):
        name = ref.lower()
        if "." in name:
            schema, _, obj = name.partition(".")
            if schema != "analytics":
                raise GuardrailError(f"table not allowed: {ref}")
            name = obj
        if name not in allowed and name not in cte_names:
            raise GuardrailError(f"table not allowed: {ref}")


def enforce_limit(sql: str, max_rows: int | None = None) -> str:
    """Wrap the (already validated) query so it can never return more than the cap."""
    cap = max_rows or settings.query_max_rows
    inner = sql.strip().rstrip(";")
    return f"SELECT * FROM (\n{inner}\n) AS _guarded LIMIT {int(cap)}"


def run_read_only(sql: str, max_rows: int | None = None) -> list[dict]:
    """Validate, cap, and execute on the read-only role. Returns row dicts."""
    validate(sql)
    wrapped = enforce_limit(sql, max_rows)
    with readonly_engine.connect() as conn:
        rows = conn.execute(text(wrapped)).mappings()
        return [dict(r) for r in rows]
