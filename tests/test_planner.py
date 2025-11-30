import pytest

from app.planner import plan_tools_with_llm
from app.registry import load_registry


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def test_planner_routes_summarize(registry):
    plan = plan_tools_with_llm("Please summarize this document", registry)
    assert any(step.agent == "document_summarizer_agent" for step in plan.steps)


def test_planner_routes_deadline(registry):
    plan = plan_tools_with_llm("Check deadline risk for Dec 15", registry)
    assert any(step.agent == "deadline_guardian_agent" for step in plan.steps)


def test_planner_out_of_scope_when_no_match(registry):
    plan = plan_tools_with_llm("Completely unrelated gibberish qwerty", registry)
    # No heuristics should match; when LLM unavailable, returns empty steps
    assert plan.steps == []
