"""Story-agent graph executor tests.

Fake providers stand in for the LLM (same trick as tests/test_nl_query.py), so
the control flow — step ceiling, forced wrap-up, and mid-turn recovery onto the
fallback provider — is exercised deterministically with no API key.

The `run_sql` callable is injected too, so most of these need no database; the
two that do are marked and use the real guarded tool.
"""
from __future__ import annotations

import pytest

from src.api.story.graph import ACT, DONE, PLAN, StoryState, execute
from src.api.story.providers import Proposal
from src.api.story.service import _run_tool_sql


class FakeProvider:
    """Returns a scripted Proposal per call, or raises to simulate a failure.

    `script` is a list of either Proposal objects or exceptions. Each call pops
    the next entry; the last entry repeats once exhausted.
    """

    def __init__(self, name: str, script: list):
        self.name = name
        self.script = list(script)
        self.calls: list[bool] = []  # with_tools flag per call

    def propose(self, transcript, system_instruction, *, with_tools: bool) -> Proposal:
        self.calls.append(with_tools)
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, BaseException):
            raise item
        return item


def _state(**kw) -> StoryState:
    return StoryState(
        dataset="olist",
        system_instruction="sys",
        transcript=[{"role": "user", "narration": "why did revenue drop?",
                     "sql": None, "columns": None, "rows": None}],
        **kw,
    )


def _fake_sql(sql: str, dataset: str = "olist") -> dict:
    return {"columns": ["category"], "row_count": 1, "rows": [{"category": "toys"}],
            "truncated": False}


def _types(events: list[dict]) -> list[str]:
    return [e["type"] for e in events]


# ---- happy path -------------------------------------------------------------
def test_query_then_narrate_ends_in_done():
    p = FakeProvider("gemini", [
        Proposal(calls=["SELECT category FROM vw_category_performance"]),
        Proposal(narration="Toys led the category mix."),
    ])
    events = list(execute(_state(), [p], _fake_sql))
    assert _types(events) == ["tool_call", "step", "step", "done"]
    assert events[1]["sql"].startswith("SELECT")
    assert events[2]["narration"] == "Toys led the category mix."


def test_narration_without_tool_call_finishes_immediately():
    p = FakeProvider("gemini", [Proposal(narration="I already know this.")])
    events = list(execute(_state(), [p], _fake_sql))
    assert _types(events) == ["step", "done"]


def test_no_provider_configured_is_an_error():
    events = list(execute(_state(), [], _fake_sql))
    assert _types(events) == ["error"]


# ---- step ceiling + forced wrap-up ------------------------------------------
def test_step_ceiling_forces_a_tool_free_final_call():
    # A provider that always wants to query: the executor must stop it and make
    # one last call with the tool removed.
    p = FakeProvider("gemini", [Proposal(calls=["SELECT 1 FROM vw_category_performance"])])
    events = list(execute(_state(max_steps=3), [p], _fake_sql))

    assert _types(events).count("tool_call") == 3, "step ceiling not enforced"
    assert events[-1]["type"] == "done"
    # 3 planning calls with tools, then exactly one final call WITHOUT tools.
    assert p.calls == [True, True, True, False]


def test_turn_always_ends_in_narration_even_if_model_stays_silent():
    p = FakeProvider("gemini", [Proposal()])  # no narration, no calls
    events = list(execute(_state(), [p], _fake_sql))
    assert _types(events) == ["step", "done"]
    assert "didn't produce a response" in events[0]["narration"]


# ---- provider recovery ------------------------------------------------------
def test_recovers_onto_fallback_when_first_provider_fails():
    bad = FakeProvider("gemini", [RuntimeError("429 quota exhausted")])
    good = FakeProvider("groq", [Proposal(narration="Recovered narration.")])

    events = list(execute(_state(), [bad, good], _fake_sql))

    assert _types(events) == ["provider_switch", "step", "done"]
    switch = events[0]
    assert (switch["from"], switch["to"], switch["node"]) == ("gemini", "groq", PLAN)
    assert "quota exhausted" in switch["message"]
    assert events[1]["narration"] == "Recovered narration."


def test_recovery_re_runs_the_failed_node_with_state_intact():
    """The whole point: work done before the failure is not thrown away."""
    bad = FakeProvider("gemini", [
        Proposal(calls=["SELECT category FROM vw_category_performance"]),  # step 1 ok
        RuntimeError("503 server spike"),                                   # step 2 fails
    ])
    good = FakeProvider("groq", [Proposal(narration="Continued from the fallback.")])

    events = list(execute(_state(), [bad, good], _fake_sql))

    assert _types(events) == ["tool_call", "step", "provider_switch", "step", "done"]
    # The fallback was handed the transcript INCLUDING the query gemini already
    # ran, so the investigation continued rather than restarting.
    assert events[2]["node"] == PLAN
    assert events[3]["narration"] == "Continued from the fallback."


def test_all_providers_failing_ends_in_error():
    bad1 = FakeProvider("gemini", [RuntimeError("boom")])
    bad2 = FakeProvider("groq", [RuntimeError("also boom")])
    events = list(execute(_state(), [bad1, bad2], _fake_sql))
    assert _types(events) == ["provider_switch", "error"]
    assert "also boom" in events[-1]["message"]


def test_does_not_switch_back_to_a_provider_that_already_failed():
    bad = FakeProvider("gemini", [RuntimeError("down")])
    good = FakeProvider("groq", [
        Proposal(calls=["SELECT category FROM vw_category_performance"]),
        Proposal(narration="Done."),
    ])
    events = list(execute(_state(), [bad, good], _fake_sql))

    assert _types(events).count("provider_switch") == 1, "should not retry a failed provider"
    assert len(bad.calls) == 1
    assert events[-1]["type"] == "done"


# ---- guardrail errors are data, not failures --------------------------------
def test_sql_error_is_fed_back_to_the_model_not_raised():
    def failing_sql(sql: str, dataset: str = "olist") -> dict:
        return {"error": "guardrail rejected this query: table not allowed: app.users"}

    p = FakeProvider("gemini", [
        Proposal(calls=["SELECT * FROM app.users"]),
        Proposal(narration="That table is off-limits; here's what I can see instead."),
    ])
    events = list(execute(_state(), [p], failing_sql))

    # A rejected query is announced but renders no result card, and the run
    # continues so the model can try something else.
    assert _types(events) == ["tool_call", "step", "done"]
    assert events[-2]["narration"].startswith("That table is off-limits")


def test_a_failed_query_does_not_trigger_provider_recovery():
    def failing_sql(sql: str, dataset: str = "olist") -> dict:
        return {"error": "query failed: relation does not exist"}

    p = FakeProvider("gemini", [
        Proposal(calls=["SELECT * FROM nope"]),
        Proposal(narration="Recovered on my own."),
    ])
    fallback = FakeProvider("groq", [Proposal(narration="should not be used")])
    events = list(execute(_state(), [p, fallback], failing_sql))

    assert "provider_switch" not in _types(events)
    assert fallback.calls == []


# ---- state bookkeeping ------------------------------------------------------
def test_snapshot_restore_round_trips():
    s = _state()
    s.pending_sql = ["SELECT 1"]
    s.steps_used = 2
    snap = s.snapshot()

    s.transcript.append({"role": "assistant", "narration": "scratch",
                         "sql": None, "columns": None, "rows": None})
    s.steps_used = 5
    s.next_node = ACT
    s.restore(snap)

    assert s.steps_used == 2
    assert s.next_node == PLAN
    assert len(s.transcript) == 1, "restore must undo transcript growth"


def test_done_sentinel_is_none():
    # The executor loops `while state.next_node is not None`, so DONE must be None.
    assert DONE is None


# ---- integration: the real guarded tool (needs the warehouse) ---------------
def test_real_tool_runs_through_the_guardrail():
    p = FakeProvider("gemini", [
        Proposal(calls=["SELECT category, revenue FROM vw_category_performance LIMIT 3"]),
        Proposal(narration="Top categories above."),
    ])
    events = list(execute(_state(), [p], _run_tool_sql))
    result = events[1]
    assert result["type"] == "step"
    assert result["rows"] and "category" in result["rows"][0]


def test_real_tool_rejects_a_malicious_generation_without_killing_the_run():
    p = FakeProvider("gemini", [
        Proposal(calls=["DROP TABLE analytics.fct_order_items"]),
        Proposal(narration="I can only read."),
    ])
    events = list(execute(_state(), [p], _run_tool_sql))
    # Announced, refused, no result card, run continues to a normal narration.
    assert _types(events) == ["tool_call", "step", "done"]
    assert events[-2]["narration"] == "I can only read."


@pytest.mark.parametrize("sql", [
    "SELECT * FROM app.users",
    "SELECT 1; DROP TABLE analytics.dim_product",
    "UPDATE analytics.dim_product SET category = 'x'",
])
def test_agent_sql_obeys_the_same_guardrail_as_query(sql):
    assert "error" in _run_tool_sql(sql), f"guardrail let through: {sql}"
