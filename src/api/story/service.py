"""Agentic data-storyteller: a multi-turn investigation where the model
repeatedly writes read-only SQL, sees only small (SQL-reduced) results, and
narrates as it goes — streamed so the user can follow along and keep asking
follow-up questions.

This module owns the two things that are genuinely this agent's own: the tool
(`_run_tool_sql`) and the prompt (`_SYSTEM_INSTRUCTION_TEMPLATE`). The control
flow lives in `graph.py` and the model calls in `providers.py`.

Design:
  * The conversation history IS the agent's state. The API is stateless per
    request: the client holds the transcript and resends it (`history`) with
    each new `message`; the server replays it into the provider's native
    message format and continues from there. No server-side session store.
  * Every SQL the model writes still goes through the exact same guardrail +
    read-only role as /query and /nl-query (`sql_guard.run_read_only`). The
    agent gets no new database capability, only repeated safe use of the
    existing one.
  * Results handed back to the model are capped hard (`_AGENT_ROW_CAP`), same
    mechanism as everywhere else — the model is nudged (via the truncation
    note) toward writing further-reducing SQL (GROUP BY, corr(), rank()...)
    rather than ever depending on a huge table reaching its context.
  * The step ceiling (`_MAX_TOOL_CALLS`) is enforced by the executor in
    Python, not left to the model's judgement, and a turn always ends in
    narration (see `graph.finalize_node`).
  * Everything is a generator: each event is yielded the moment it happens, so
    the router can stream it to the client immediately.
  * Provider failure is recovered mid-turn: the executor rolls the state back
    to just before the failed node and re-runs it on the fallback provider,
    emitting a `provider_switch` event so the change is never silent. See the
    module docstring in `graph.py` for the rollback contract.
"""
from __future__ import annotations

import datetime
import decimal
import re
from collections.abc import Iterator
from typing import Any

import mlflow

from ..nl.schema import build_schema_prompt
from ..sql_guard import GuardrailError, run_read_only
from .graph import StoryState, execute
from .providers import build_providers

_MAX_TOOL_CALLS = 6
_AGENT_ROW_CAP = 25

_FENCE = re.compile(r"^```(?:sql)?\s*|\s*```$", re.IGNORECASE)


def _clean_sql(sql: str) -> str:
    s = sql.strip()
    return _FENCE.sub("", s).strip()


def _jsonable(value: Any) -> Any:
    """Make a DB row value safe to hand to the model / put in an API response."""
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


@mlflow.trace(name="run_tool_sql", span_type="TOOL")
def _run_tool_sql(sql: str, dataset: str = "olist") -> dict[str, Any]:
    """Execute one agent-proposed SQL statement through the normal guardrail
    + read-only path against `dataset`'s schema, capped small, and returned as
    a JSON-safe dict. Errors come back as a normal dict (not raised) so the
    model can see what went wrong and try a different query instead of the
    whole run failing."""
    try:
        sql = _clean_sql(sql)
        rows = run_read_only(sql, dataset, max_rows=_AGENT_ROW_CAP)
    except GuardrailError as exc:
        return {"error": f"guardrail rejected this query: {exc}"}
    except Exception as exc:  # noqa: BLE001  (DB error — surfaced to the model, not raised)
        return {"error": f"query failed: {exc}"}

    rows = [{k: _jsonable(v) for k, v in r.items()} for r in rows]
    columns = list(rows[0].keys()) if rows else []
    truncated = len(rows) >= _AGENT_ROW_CAP
    result: dict[str, Any] = {
        "columns": columns,
        "row_count": len(rows),
        "rows": rows,
        "truncated": truncated,
    }
    if truncated:
        result["note"] = (
            f"Result was capped at {_AGENT_ROW_CAP} rows. If you need the full "
            "picture, write a further-reducing query instead (GROUP BY, "
            "corr(), percentile_cont(), rank()+LIMIT for top/bottom N, etc.) "
            "rather than relying on these rows alone."
        )
    return result


_SYSTEM_INSTRUCTION_TEMPLATE = """\
You are a data storyteller investigating a Brazilian e-commerce analytics \
warehouse (Olist dataset, 2016-2018), in an ongoing conversation with a user.

You have ONE tool: `run_sql(sql)`. It executes a single read-only SQL \
SELECT/WITH statement against the `analytics` schema and returns its result \
(capped at a small row count — you will be told if a result was truncated).

Rules:
- Every query must be a single read-only SELECT or WITH statement (no writes,
  no DDL, no multiple statements).
- Prefer queries that already reduce the data server-side — aggregates,
  GROUP BY, corr(), percentile_cont(), rank()+LIMIT for top/bottom N — over
  queries that just dump many raw rows. If a result comes back truncated,
  write a smaller/smarter follow-up query rather than trusting the partial
  rows as the full picture. Reduce in stages with CTEs (WITH a AS (...), b AS
  (SELECT ... FROM a) ...) when one aggregate is still too large, instead of
  returning the intermediate result.
- After each tool result, narrate what you learned in one or two plain-English
  sentences before deciding your next step (or finishing).
- Investigate in at most a handful of steps per user message. Once you have
  enough findings to answer, stop calling the tool and give your final
  narration as plain text with no further tool call.
- Use Markdown in your narration (bold, bullet lists, headers, tables where useful).
- Every claim in your narration must be something you actually observed in a
  tool result — in this turn or an earlier one in the conversation. Do not
  state a number you didn't query for.
- The user may ask follow-up questions about what you already found, or ask
  you to investigate something new — treat both naturally as a continuation
  of the same conversation.

{schema_prompt}
"""

# Event shapes yielded by the executor:
#   {"type": "tool_call", "sql": "..."}                   -- about to run this query
#   {"type": "step", "role": "assistant", "narration": ..., "sql": ..., "columns": ..., "rows": ...}
#   {"type": "provider_switch", "from": ..., "to": ..., "node": ..., "message": ...}
#   {"type": "error", "message": "..."}                    -- terminal for this turn
#   {"type": "done"}                                       -- terminal, success


def run_story_stream(
    message: str, history: list[dict] | None = None, dataset: str = "olist"
) -> Iterator[dict]:
    """Top-level entry point. Builds the graph state from the client-held
    transcript and runs it, yielding events as they happen. Always ends with
    exactly one terminal event: `done` on success, `error` on failure."""
    history = history or []
    state = StoryState(
        dataset=dataset,
        system_instruction=_SYSTEM_INSTRUCTION_TEMPLATE.format(
            schema_prompt=build_schema_prompt(dataset)
        ),
        transcript=[*history, {"role": "user", "narration": message,
                               "sql": None, "columns": None, "rows": None}],
        max_steps=_MAX_TOOL_CALLS,
    )
    yield from execute(state, build_providers(), _run_tool_sql)
