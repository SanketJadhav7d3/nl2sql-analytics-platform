"""Agentic data-storyteller: a multi-turn tool-calling loop where the model
investigates a theme by repeatedly writing read-only SQL, sees only small
(SQL-reduced) results, and narrates as it goes — as an ongoing, STREAMED
conversation the user can keep asking follow-up questions in.

Design (see project discussion for the full reasoning):
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
  * The loop has a hard step ceiling (`_MAX_TOOL_CALLS`) per turn, enforced
    in Python, not left to the model's judgement.
  * Everything is a generator: each event (a tool call starting, a tool
    result, a narration chunk) is yielded the moment it happens, so the
    router can stream it to the client immediately instead of holding the
    whole turn in memory until it's done.
  * Provider fallback (Gemini -> Groq) is a *pre-flight* decision: once any
    event has actually been yielded to the caller, we never silently swap
    providers mid-turn — a partial transcript in one provider's "voice"
    then continuing in another's would be a worse failure mode than just
    surfacing the error. See `run_story_stream`.
"""
from __future__ import annotations

import datetime
import decimal
import re
from collections.abc import Iterator
from typing import Any

import mlflow

from ..config import settings
from ..nl.schema import build_schema_prompt
from ..sql_guard import GuardrailError, run_read_only

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
  rows as the full picture.
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

_RUN_SQL_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "sql": {
            "type": "string",
            "description": "One read-only SQL SELECT/WITH statement against the analytics schema.",
        }
    },
    "required": ["sql"],
}

# Event shapes yielded by every generator below:
#   {"type": "tool_call", "sql": "..."}                               -- about to run this query
#   {"type": "step", "role": "assistant", "narration": ..., "sql": ..., "columns": ..., "rows": ...}
#   {"type": "error", "message": "..."}                                -- terminal for this turn
#   {"type": "done"}                                                   -- terminal, success


def _echo_story(message: str, history: list[dict], dataset: str = "olist") -> Iterator[dict]:
    """Offline fallback (LLM_PROVIDER=echo) — no API key required."""
    sql = "SELECT category, revenue, revenue_rank FROM vw_category_performance ORDER BY revenue_rank LIMIT 5"
    yield {"type": "tool_call", "sql": sql}
    result = _run_tool_sql(sql, dataset)
    yield {
        "type": "step",
        "role": "assistant",
        "narration": None,
        "sql": sql,
        "columns": result.get("columns"),
        "rows": result.get("rows"),
    }
    yield {
        "type": "step",
        "role": "assistant",
        "narration": (
            f"This is an offline demo story (LLM_PROVIDER=echo) responding to: *{message}*. The top "
            "categories by revenue are shown above.\n\n**Key takeaway:** set a real GEMINI_API_KEY to get "
            "an actual investigated narrative."
        ),
        "sql": None,
        "columns": None,
        "rows": None,
    }


def _replay_gemini(history: list[dict]):
    """Rebuild a Gemini `contents` list from our neutral step history, so a
    follow-up message continues the same investigation regardless of which
    provider actually ran each earlier turn."""
    from google.genai import types

    contents = []
    for step in history:
        role = step.get("role", "assistant")
        if step.get("narration") is not None:
            contents.append(
                types.Content(role=("user" if role == "user" else "model"), parts=[types.Part(text=step["narration"])])
            )
        elif step.get("sql") is not None:
            contents.append(
                types.Content(
                    role="model",
                    parts=[types.Part(functionCall=types.FunctionCall(name="run_sql", args={"sql": step["sql"]}))],
                )
            )
            payload = {
                "columns": step.get("columns") or [],
                "rows": step.get("rows") or [],
                "row_count": len(step.get("rows") or []),
            }
            contents.append(
                types.Content(role="user", parts=[types.Part.from_function_response(name="run_sql", response=payload)])
            )
    return contents


def _run_story_gemini(message: str, history: list[dict], dataset: str = "olist") -> Iterator[dict]:
    from google import genai
    from google.genai import types

    key = settings.gemini_api_key
    client = genai.Client(api_key=key) if key else genai.Client()

    system_instruction = _SYSTEM_INSTRUCTION_TEMPLATE.format(schema_prompt=build_schema_prompt(dataset))
    tool = types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="run_sql",
                description="Execute one read-only SQL statement against the analytics schema.",
                parametersJsonSchema=_RUN_SQL_TOOL_SCHEMA,
            )
        ]
    )
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.2,
        tools=[tool],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    contents: list = _replay_gemini(history) + [types.Content(role="user", parts=[types.Part(text=message)])]
    produced_any_narration = False

    for _ in range(_MAX_TOOL_CALLS):
        with mlflow.start_span(name="gemini.generate_content", span_type="LLM") as span:
            span.set_attributes({"provider": "gemini", "model": settings.llm_model})
            resp = client.models.generate_content(model=settings.llm_model, contents=contents, config=config)
        candidate = resp.candidates[0]
        contents.append(candidate.content)

        parts = candidate.content.parts or []
        call_parts = [p for p in parts if p.function_call]
        text_parts = [p.text for p in parts if p.text]

        if text_parts:
            produced_any_narration = True
            yield {"type": "step", "role": "assistant", "narration": "\n".join(text_parts), "sql": None, "columns": None, "rows": None}

        if not call_parts:
            return  # model finished narrating with no further tool call

        response_parts = []
        for call_part in call_parts:
            fc = call_part.function_call
            sql = (fc.args or {}).get("sql", "")
            yield {"type": "tool_call", "sql": sql}
            result = _run_tool_sql(sql, dataset)
            if "error" not in result:
                yield {"type": "step", "role": "assistant", "narration": None, "sql": sql, "columns": result.get("columns"), "rows": result.get("rows")}
            response_parts.append(types.Part.from_function_response(name=fc.name, response=result))

        contents.append(types.Content(role="user", parts=response_parts))

    # Hit the step ceiling without the model wrapping up on its own —
    # force one final tool-free turn so the run always ends in narration.
    contents.append(
        types.Content(role="user", parts=[types.Part(text="Stop investigating now and give your final narration and key takeaway.")])
    )
    final_config = types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.2)
    with mlflow.start_span(name="gemini.generate_content.final", span_type="LLM") as span:
        span.set_attributes({"provider": "gemini", "model": settings.llm_model})
        resp = client.models.generate_content(model=settings.llm_model, contents=contents, config=final_config)
    if resp.text:
        produced_any_narration = True
        yield {"type": "step", "role": "assistant", "narration": resp.text, "sql": None, "columns": None, "rows": None}

    if not produced_any_narration:
        yield {"type": "step", "role": "assistant", "narration": "The agent didn't produce a response.", "sql": None, "columns": None, "rows": None}


def _replay_groq(history: list[dict]) -> list[dict]:
    import json as _json

    messages: list[dict] = []
    call_id = 0
    for step in history:
        role = step.get("role", "assistant")
        if step.get("narration") is not None:
            messages.append({"role": ("user" if role == "user" else "assistant"), "content": step["narration"]})
        elif step.get("sql") is not None:
            call_id += 1
            cid = f"replay_{call_id}"
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": cid, "type": "function", "function": {"name": "run_sql", "arguments": _json.dumps({"sql": step["sql"]})}}
                    ],
                }
            )
            payload = {
                "columns": step.get("columns") or [],
                "rows": step.get("rows") or [],
                "row_count": len(step.get("rows") or []),
            }
            messages.append({"role": "tool", "tool_call_id": cid, "content": _json.dumps(payload)})
    return messages


def _run_story_groq(message: str, history: list[dict], dataset: str = "olist") -> Iterator[dict]:
    """Same agent loop as Gemini, driven through Groq's OpenAI-compatible
    chat-completions + tool-calling API instead."""
    import json as _json

    from openai import OpenAI

    from ..llm_util import groq_call_with_retry

    client = OpenAI(api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1")

    system_instruction = _SYSTEM_INSTRUCTION_TEMPLATE.format(schema_prompt=build_schema_prompt(dataset))
    tools = [
        {
            "type": "function",
            "function": {
                "name": "run_sql",
                "description": "Execute one read-only SQL statement against the analytics schema.",
                "parameters": _RUN_SQL_TOOL_SCHEMA,
            },
        }
    ]
    messages: list[dict] = (
        [{"role": "system", "content": system_instruction}] + _replay_groq(history) + [{"role": "user", "content": message}]
    )
    produced_any_narration = False

    for _ in range(_MAX_TOOL_CALLS):
        with mlflow.start_span(name="groq.chat_completion", span_type="LLM") as span:
            resp = groq_call_with_retry(
                lambda model: client.chat.completions.create(
                    model=model, messages=messages, tools=tools, tool_choice="auto", temperature=0.2
                ),
                model=settings.groq_model,
                fallback_model=settings.groq_fallback_model,
            )
            span.set_attributes({"provider": "groq", "model": resp.model})
        msg = resp.choices[0].message

        if msg.content:
            produced_any_narration = True
            yield {"type": "step", "role": "assistant", "narration": msg.content, "sql": None, "columns": None, "rows": None}

        if not msg.tool_calls:
            return  # model finished narrating with no further tool call

        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            }
        )
        for tc in msg.tool_calls:
            args = _json.loads(tc.function.arguments or "{}")
            sql = args.get("sql", "")
            yield {"type": "tool_call", "sql": sql}
            result = _run_tool_sql(sql, dataset)
            if "error" not in result:
                yield {"type": "step", "role": "assistant", "narration": None, "sql": sql, "columns": result.get("columns"), "rows": result.get("rows")}
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": _json.dumps(result)})
    else:
        messages.append({"role": "user", "content": "Stop investigating now and give your final narration and key takeaway."})
        with mlflow.start_span(name="groq.chat_completion.final", span_type="LLM") as span:
            resp = groq_call_with_retry(
                lambda model: client.chat.completions.create(model=model, messages=messages, temperature=0.2),
                model=settings.groq_model,
                fallback_model=settings.groq_fallback_model,
            )
            span.set_attributes({"provider": "groq", "model": resp.model})
        final_text = resp.choices[0].message.content
        if final_text:
            produced_any_narration = True
            yield {"type": "step", "role": "assistant", "narration": final_text, "sql": None, "columns": None, "rows": None}

    if not produced_any_narration:
        yield {"type": "step", "role": "assistant", "narration": "The agent didn't produce a response.", "sql": None, "columns": None, "rows": None}


def run_story_stream(message: str, history: list[dict] | None = None, dataset: str = "olist") -> Iterator[dict]:
    """Top-level entry point. Yields events as they happen (see the shapes
    documented above). Always ends with exactly one terminal event:
    {"type": "done"} on success, {"type": "error", ...} on failure.

    Fallback rule: Gemini -> Groq only happens if Gemini fails before this
    generator has yielded ANY event to the caller (i.e. nothing has reached
    the client's transcript yet) — so a provider switch is always invisible
    to the user, never a jarring mid-turn voice change. If Gemini fails
    after already streaming part of the turn, that's a terminal error for
    this turn instead: the partial transcript already shown stays valid,
    and the user can just ask again rather than getting a silently
    Frankenstein'd turn stitched from two different models.
    """
    history = history or []

    if settings.llm_provider == "echo":
        yield from _echo_story(message, history, dataset)
        yield {"type": "done"}
        return

    emitted = False
    try:
        for event in _run_story_gemini(message, history, dataset):
            emitted = True
            yield event
        yield {"type": "done"}
        return
    except Exception as exc:  # noqa: BLE001  (e.g. Gemini quota exhausted)
        if emitted or not settings.groq_api_key:
            yield {"type": "error", "message": str(exc)}
            return
        # Nothing reached the client yet — safe to retry transparently on Groq.

    try:
        for event in _run_story_groq(message, history, dataset):
            yield event
        yield {"type": "done"}
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}
