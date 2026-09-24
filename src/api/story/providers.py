"""LLM providers for the Story agent, behind one small interface.

Each provider turns the *same* provider-neutral transcript (our `StoryStep`
dicts) into a `Proposal`: some narration, and/or a list of SQL statements the
model wants to run. Nothing provider-specific escapes this module.

That neutrality is what makes mid-turn recovery possible (see `graph.py`): the
canonical state is always our own step dicts, and the provider-native message
list is rebuilt from scratch on every call. Rebuilding costs a little CPU per
step and buys the ability to hand the exact same state to a different provider
after a failure, without any translation of half-finished native objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import mlflow

from ..config import settings


@dataclass
class Proposal:
    """What a provider decided to do this step."""
    narration: str | None = None
    calls: list[str] = field(default_factory=list)  # SQL statements to run


class Provider(Protocol):
    name: str

    def propose(
        self, transcript: list[dict[str, Any]], system_instruction: str, *, with_tools: bool
    ) -> Proposal:
        """One model call. `with_tools=False` removes the tool entirely, so the
        model *cannot* emit a call and must answer in prose."""
        ...


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

_TOOL_DESCRIPTION = "Execute one read-only SQL statement against the analytics schema."


def _tool_payload(step: dict[str, Any]) -> dict[str, Any]:
    """The tool-result payload a replayed step hands back to the model."""
    payload: dict[str, Any] = {
        "columns": step.get("columns") or [],
        "rows": step.get("rows") or [],
        "row_count": len(step.get("rows") or []),
    }
    # `note` is set when a result was capped; keeping it in the replay is what
    # nudges the model toward a further-reducing query on the next step.
    if step.get("note"):
        payload["note"] = step["note"]
        payload["truncated"] = True
    return payload


# ---------------------------------------------------------------------------
class GeminiProvider:
    """Gemini, with one wrinkle: replayed function calls need a signature.

    Gemini rejects a `functionCall` part that is missing its
    `thought_signature` (400 INVALID_ARGUMENT), and that signature only exists
    on the part the model itself produced. Reconstructing a call from our
    neutral transcript therefore cannot produce a valid native part.

    So this provider remembers the signature it was given for each SQL string
    it proposed (`_signatures`) and replays those calls natively. Anything it
    has no signature for -- history from an earlier turn, or steps another
    provider ran before recovery switched to us -- is replayed as plain text
    instead. The model still sees the SQL and the rows; it just isn't framed
    as a native tool exchange. That keeps a transcript replayable across
    providers and across turns, which native parts alone cannot be.
    """

    name = "gemini"

    def __init__(self) -> None:
        # SQL string -> the thought_signature Gemini returned with that call.
        self._signatures: dict[str, bytes] = {}

    def _replay(self, transcript: list[dict[str, Any]]):
        import json as _json

        from google.genai import types

        contents = []
        for step in transcript:
            role = step.get("role", "assistant")
            if step.get("narration") is not None:
                contents.append(
                    types.Content(
                        role=("user" if role == "user" else "model"),
                        parts=[types.Part(text=step["narration"])],
                    )
                )
            elif step.get("sql") is not None:
                signature = self._signatures.get(step["sql"])
                if signature is None:
                    # No signature: describe the exchange in text rather than
                    # sending a native call that Gemini would reject.
                    contents.append(
                        types.Content(
                            role="model",
                            parts=[types.Part(text=f"I ran this query:\n{step['sql']}")],
                        )
                    )
                    contents.append(
                        types.Content(
                            role="user",
                            parts=[
                                types.Part(
                                    text="Result of that query:\n"
                                    + _json.dumps(_tool_payload(step), default=str)
                                )
                            ],
                        )
                    )
                    continue
                contents.append(
                    types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                functionCall=types.FunctionCall(
                                    name="run_sql", args={"sql": step["sql"]}
                                ),
                                thoughtSignature=signature,
                            )
                        ],
                    )
                )
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(
                                name="run_sql", response=_tool_payload(step)
                            )
                        ],
                    )
                )
        return contents

    def propose(
        self, transcript: list[dict[str, Any]], system_instruction: str, *, with_tools: bool
    ) -> Proposal:
        from google import genai
        from google.genai import types

        key = settings.gemini_api_key
        client = genai.Client(api_key=key) if key else genai.Client()

        config_kwargs: dict[str, Any] = {
            "system_instruction": system_instruction,
            "temperature": 0.2,
        }
        if with_tools:
            config_kwargs["tools"] = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name="run_sql",
                            description=_TOOL_DESCRIPTION,
                            parametersJsonSchema=_RUN_SQL_TOOL_SCHEMA,
                        )
                    ]
                )
            ]
            config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
                disable=True
            )

        with mlflow.start_span(name="gemini.generate_content", span_type="LLM") as span:
            span.set_attributes({"provider": self.name, "model": settings.llm_model})
            resp = client.models.generate_content(
                model=settings.llm_model,
                contents=self._replay(transcript),
                config=types.GenerateContentConfig(**config_kwargs),
            )

        parts = resp.candidates[0].content.parts or []
        text = "\n".join(p.text for p in parts if p.text) or None

        calls = []
        for part in parts:
            if not part.function_call:
                continue
            sql = (part.function_call.args or {}).get("sql", "")
            calls.append(sql)
            # Remember the signature so this call can be replayed natively on
            # the next step of this turn (see the class docstring).
            if part.thought_signature:
                self._signatures[sql] = part.thought_signature

        return Proposal(narration=text, calls=calls)


# ---------------------------------------------------------------------------
class GroqProvider:
    name = "groq"

    def _replay(self, transcript: list[dict[str, Any]]) -> list[dict]:
        import json as _json

        messages: list[dict] = []
        call_id = 0
        for step in transcript:
            role = step.get("role", "assistant")
            if step.get("narration") is not None:
                messages.append(
                    {"role": ("user" if role == "user" else "assistant"), "content": step["narration"]}
                )
            elif step.get("sql") is not None:
                call_id += 1
                cid = f"replay_{call_id}"
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": cid,
                                "type": "function",
                                "function": {
                                    "name": "run_sql",
                                    "arguments": _json.dumps({"sql": step["sql"]}),
                                },
                            }
                        ],
                    }
                )
                messages.append(
                    {"role": "tool", "tool_call_id": cid, "content": _json.dumps(_tool_payload(step))}
                )
        return messages

    def propose(
        self, transcript: list[dict[str, Any]], system_instruction: str, *, with_tools: bool
    ) -> Proposal:
        import json as _json

        from openai import OpenAI

        from ..llm_util import groq_call_with_retry

        client = OpenAI(api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1")
        messages = [{"role": "system", "content": system_instruction}] + self._replay(transcript)

        kwargs: dict[str, Any] = {"messages": messages, "temperature": 0.2}
        if with_tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": "run_sql",
                        "description": _TOOL_DESCRIPTION,
                        "parameters": _RUN_SQL_TOOL_SCHEMA,
                    },
                }
            ]
            kwargs["tool_choice"] = "auto"

        with mlflow.start_span(name="groq.chat_completion", span_type="LLM") as span:
            resp = groq_call_with_retry(
                lambda model: client.chat.completions.create(model=model, **kwargs),
                model=settings.groq_model,
                fallback_model=settings.groq_fallback_model,
            )
            span.set_attributes({"provider": self.name, "model": resp.model})

        msg = resp.choices[0].message
        calls = [
            _json.loads(tc.function.arguments or "{}").get("sql", "")
            for tc in (msg.tool_calls or [])
        ]
        return Proposal(narration=msg.content or None, calls=calls)


# ---------------------------------------------------------------------------
class EchoProvider:
    """Offline provider (LLM_PROVIDER=echo) — no API key required.

    Runs one canned query, then narrates. Deterministic, so it doubles as the
    provider the test suite drives the graph with.
    """

    name = "echo"

    _DEMO_SQL = (
        "SELECT category, revenue, revenue_rank FROM vw_category_performance "
        "ORDER BY revenue_rank LIMIT 5"
    )

    def propose(
        self, transcript: list[dict[str, Any]], system_instruction: str, *, with_tools: bool
    ) -> Proposal:
        already_queried = any(s.get("sql") for s in transcript)
        if with_tools and not already_queried:
            return Proposal(calls=[self._DEMO_SQL])
        return Proposal(
            narration=(
                "This is an offline demo story (LLM_PROVIDER=echo). The top categories by "
                "revenue are shown above.\n\n**Key takeaway:** set a real GEMINI_API_KEY to "
                "get an actual investigated narrative."
            )
        )


def build_providers() -> list[Provider]:
    """Providers in preference order. The first is used; the rest are what the
    graph executor recovers onto, in order, when one fails mid-turn."""
    if settings.llm_provider == "echo":
        return [EchoProvider()]
    chain: list[Provider] = [GeminiProvider()]
    if settings.groq_api_key:
        chain.append(GroqProvider())
    return chain
