"""NL-to-SQL orchestration: prompt -> LLM -> clean -> guardrails -> execute."""
from __future__ import annotations

import re

from .adapter import LLMAdapter
from .schema import build_schema_prompt
from ..sql_guard import run_read_only

_FENCE = re.compile(r"^```(?:sql)?\s*|\s*```$", re.IGNORECASE)


def _clean(sql: str) -> str:
    """Strip markdown fences / stray whitespace an adapter might add."""
    s = sql.strip()
    s = _FENCE.sub("", s).strip()
    return s


def nl_query(question: str, adapter: LLMAdapter) -> dict:
    """Generate SQL for `question`, run it through the guardrails + read-only
    role, and return the generated SQL plus result rows. Raises GuardrailError
    (or a DB error) which the router maps to a 400."""
    schema_prompt = build_schema_prompt()
    raw_sql = adapter.generate_sql(question, schema_prompt)
    sql = _clean(raw_sql)
    # run_read_only validates (single read-only SELECT, allow-list, no comments,
    # no stacked statements), enforces a LIMIT, and executes as analytics_ro.
    rows = run_read_only(sql)
    return {"question": question, "sql": sql, "row_count": len(rows), "rows": rows}
