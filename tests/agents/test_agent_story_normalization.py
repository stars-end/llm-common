import pytest

from llm_common.agents.schemas import AgentStory


def test_agent_story_allows_string_steps() -> None:
    story = AgentStory(
        id="plaid_link",
        persona="investor_basic",
        steps=[
            "Navigate to /brokerage",
            "Click [data-testid='connect-button-schwab']",
        ],
    )

    assert story.steps[0]["id"] == "step-1"
    assert story.steps[0]["description"] == "Navigate to /brokerage"
    assert story.steps[0]["validation_criteria"] == []


def test_agent_story_allows_mixed_steps() -> None:
    story = AgentStory(
        id="mixed",
        persona="investor_basic",
        steps=[
            "Navigate to /brokerage",
            {"id": "step-reconnect", "description": "Click reconnect", "validation_criteria": ["Reconnect"]},
        ],
    )

    assert story.steps[0]["id"] == "step-1"
    assert story.steps[1]["id"] == "step-reconnect"


def test_agent_story_rejects_invalid_steps() -> None:
    with pytest.raises(TypeError):
        AgentStory(id="bad", persona="p", steps="not-a-list")  # type: ignore[arg-type]
