"""NL-to-SQL orchestration: prompt -> LLM -> clean -> guardrails -> execute."""
from __future__ import annotations

import re

from ..sql_guard import run_read_only
from .adapter import LLMAdapter
from .schema import build_schema_prompt

_FENCE = re.compile(r"^```(?:sql)?\s*|\s*```$", re.IGNORECASE)


def _clean(sql: str) -> str:
    """Strip markdown fences / stray whitespace an adapter might add."""
    s = sql.strip()
    s = _FENCE.sub("", s).strip()
    return s


def nl_query(question: str, adapter: LLMAdapter, dataset: str = "olist") -> dict:
    """Generate SQL for `question`, run it through the guardrails + read-only
    role against `dataset`'s schema, and return the generated SQL plus result
    rows. Raises GuardrailError (or a DB error) which the router maps to 400."""
    schema_prompt = build_schema_prompt(dataset)
    raw_sql = adapter.generate_sql(question, schema_prompt)
    sql = _clean(raw_sql)
    # run_read_only validates (single read-only SELECT, allow-list, no comments,
    # no stacked statements), enforces a LIMIT, and executes as analytics_ro.
    rows = run_read_only(sql, dataset)
    return {"question": question, "sql": sql, "row_count": len(rows), "rows": rows}
