from pathlib import Path

import yaml


def test_prime_radiant_founder_story_contract():
    story_path = Path("docs/testing/stories/story-prime-radiant-founder-path.yml")
    assert story_path.exists()

    story = yaml.safe_load(story_path.read_text())

    assert story["id"] == "story-prime-radiant-founder-path"
    assert story["metadata"]["auth_mode"] == "none"

    step_ids = [step["id"] for step in story["steps"]]
    assert "step-6-wait-plaid-iframe" in step_ids
    assert "step-10-wait-analytics-context" in step_ids
    assert "step-14-wait-artifact-render" in step_ids

    set_cookie_steps = [s for s in story["steps"] if s.get("action") == "set_cookie"]
    assert len(set_cookie_steps) == 2
    values = {s["value"] for s in set_cookie_steps}
    assert "{{ENV:PR_DISCONNECTED_BYPASS_TOKEN}}" in values
    assert "{{ENV:PR_CONNECTED_BYPASS_TOKEN}}" in values

    assert any(
        s.get("selector") == '[data-testid="advisor-chat-input"]'
        and "AAPL stock price" in s.get("text", "")
        for s in story["steps"]
    )

    assert any(
        s.get("action") == "wait_for_selector"
        and s.get("selector") == '[data-testid="advisor-artifact"]'
        for s in story["steps"]
    )
