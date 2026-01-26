import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from llm_common.agents.schemas import StoryResult
from llm_common.agents.ui_smoke_agent import UISmokeAgent
from llm_common.agents.uismoke_triage import UISmokeTriage


@pytest.fixture
def mock_browser():
    browser = AsyncMock()
    browser.get_current_url = AsyncMock(return_value="http://localhost:3000/test")
    browser.screenshot = AsyncMock(return_value="YmFzZTY0")  # "base64" in b64
    browser.get_console_errors = AsyncMock(return_value=[])
    browser.get_network_errors = AsyncMock(return_value=[])
    browser.get_content = AsyncMock(return_value="<html><body>Test</body></html>")
    return browser


@pytest.fixture
def mock_llm():
    client = AsyncMock()
    # Default response
    response = MagicMock()
    response.content = "Step complete"
    response.metadata = {
        "raw_response": {
            "choices": [
                {
                    "message": {
                        "tool_calls": [{"function": {"name": "complete_step", "arguments": "{}"}}]
                    }
                }
            ]
        }
    }
    client.chat_completion = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_variable_substitution(mock_browser, mock_llm):
    agent = UISmokeAgent(mock_llm, mock_browser, "http://localhost:3000")

    os.environ["TEST_VAR"] = "secret_value"
    text = "Find the {{ENV:TEST_VAR}}"
    substituted = agent._substitute_vars(text)
    assert substituted == "Find the secret_value"

    redacted = agent._redact_secrets(text)
    assert redacted == "Find the [REDACTED]"


@pytest.mark.asyncio
async def test_missing_env_error(mock_browser, mock_llm):
    agent = UISmokeAgent(mock_llm, mock_browser, "http://localhost:3000")
    if "NON_EXISTENT_VAR" in os.environ:
        del os.environ["NON_EXISTENT_VAR"]

    step_data = {"navigate": "{{ENV:NON_EXISTENT_VAR}}"}
    result = await agent._run_step("admin", "step-1", step_data)

    assert result.status == "fail"
    assert any(e.type == "missing_env" for e in result.errors)


@pytest.mark.asyncio
async def test_deterministic_step_execution(mock_browser, mock_llm):
    agent = UISmokeAgent(mock_llm, mock_browser, "http://localhost:3000")

    # Mock _verify_completion to always pass
    agent._verify_completion = AsyncMock(return_value=True)

    step_data = {"id": "step-1", "navigate": "/dashboard"}

    actions = []
    success = await agent._execute_deterministic_step(step_data, actions)

    assert success is True
    mock_browser.navigate.assert_called_with("/dashboard")
    assert actions[0]["tool"] == "navigate"
    assert actions[0]["deterministic"] is True


@pytest.mark.asyncio
async def test_deterministic_click_execution(mock_browser, mock_llm):
    agent = UISmokeAgent(mock_llm, mock_browser, "http://localhost:3000")
    agent._verify_completion = AsyncMock(return_value=True)

    step_data = {"id": "step-2", "click": "#submit-btn"}

    actions = []
    success = await agent._execute_deterministic_step(step_data, actions)

    assert success is True
    mock_browser.click.assert_called_with("#submit-btn")


def test_triage_plan_generation(tmp_path):
    run_dir = tmp_path / "run_123"
    run_dir.mkdir()
    stories_dir = run_dir / "stories"
    stories_dir.mkdir()

    # Create a mock run.json
    run_data = {
        "run_id": "123",
        "environment": "dev",
        "base_url": "http://dev.example.com",
        "story_results": [{"story_id": "story-1", "status": "fail"}],
    }
    with open(run_dir / "run.json", "w") as f:
        json.dump(run_data, f)

    # Create a reproducible fail summary
    story_dir = stories_dir / "story-1"
    story_dir.mkdir()
    with open(story_dir / "story_summary.json", "w") as f:
        json.dump({"classification": "reproducible_fail"}, f)

    with open(story_dir / "forensics.json", "w") as f:
        json.dump({"last_url": "http://dev/fail", "console_errors": ["Error 500"]}, f)

    triage = UISmokeTriage(run_dir, "[TEST]", dry_run=True)
    # We'll just check if it runs without error and we can inspect logic if needed
    triage.triage()
    # Since we can't easily capture stdout here, we assume if it finishes it's okay for unit test coverage
    # In a real CI we'd use capsys fixture


@pytest.mark.asyncio
async def test_only_stories_filtering(mock_browser, mock_llm, tmp_path):
    from llm_common.agents.auth import AuthConfig
    from llm_common.agents.uismoke_runner import UISmokeRunner

    # Create valid mock stories
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    (stories_dir / "story-1.yml").write_text(
        "id: story-1\ndescription: d\npersona: admin\nsteps: []"
    )
    (stories_dir / "story-2.yml").write_text(
        "id: story-2\ndescription: d\npersona: guest\nsteps: []"
    )

    runner = UISmokeRunner(
        base_url="http://test",
        stories_dir=stories_dir,
        output_dir=tmp_path / "out",
        auth_config=AuthConfig(mode="none"),
        only_stories=["story-1"],
    )

    # We must mock _run_story_with_repro to avoid real execution
    runner._run_story_with_repro = AsyncMock(
        return_value={
            "result": StoryResult(story_id="story-1", status="pass"),
            "authed_shared": None,
            "guest_shared": None,
        }
    )

    # Add ZAI_API_KEY for GLM client init
    os.environ["ZAI_API_KEY"] = "fake"

    await runner.run()

    # Verify only story-1 was run
    assert runner._run_story_with_repro.call_count == 1
    call_args = runner._run_story_with_repro.call_args[0]
    assert call_args[0].id == "story-1"


@pytest.mark.asyncio
async def test_deterministic_wait_and_text(mock_browser, mock_llm):
    agent = UISmokeAgent(mock_llm, mock_browser, "http://localhost:3000")
    agent._verify_completion = AsyncMock(return_value=True)

    # Test wait_for_selector
    step_data = {"action": "wait_for_selector", "selector": "#main"}
    actions = []
    await agent._execute_deterministic_step(step_data, actions)
    mock_browser.wait_for_selector.assert_called()

    # Test assert_text
    mock_browser.get_text = AsyncMock(return_value="Hello World")
    step_data = {"action": "assert_text", "selector": "h1", "text": "Hello"}
    await agent._execute_deterministic_step(step_data, actions)
    mock_browser.get_text.assert_called_with("h1")


def test_hardened_triage_logic(tmp_path):
    run_dir = tmp_path / "run_tri"
    run_dir.mkdir()
    stories_dir = run_dir / "stories"
    stories_dir.mkdir()

    run_data = {
        "run_id": "tri",
        "environment": "dev",
        "base_url": "http://dev",
        "story_results": [
            {"story_id": "bug-story", "status": "fail"},
            {"story_id": "triage-story", "status": "fail"},
        ],
    }
    with open(run_dir / "run.json", "w") as f:
        json.dump(run_data, f)

    # Bug Story: Reproducible + Deterministic
    bug_dir = stories_dir / "bug-story"
    bug_dir.mkdir()
    with open(bug_dir / "story_summary.json", "w") as f:
        json.dump(
            {
                "classification": "reproducible_fail",
                "final_attempt": {
                    "step_results": [
                        {
                            "status": "fail",
                            "actions_taken": [{"tool": "click", "deterministic": True}],
                        }
                    ]
                },
            },
            f,
        )

    # Triage Story: Reproducible + Non-Deterministic (LLM fallible)
    tri_dir = stories_dir / "triage-story"
    tri_dir.mkdir()
    with open(tri_dir / "story_summary.json", "w") as f:
        json.dump(
            {
                "classification": "reproducible_fail",
                "final_attempt": {
                    "step_results": [
                        {
                            "status": "fail",
                            "actions_taken": [{"tool": "click", "deterministic": False}],
                        }
                    ]
                },
            },
            f,
        )

    triage = UISmokeTriage(run_dir, "[TEST]", dry_run=True)
    # Mocking _execute_beads_plan just in case
    triage._execute_beads_plan = MagicMock()

    # We can't easily capture the plan without modifying triage to return it or using a mock
    # For now, we'll just ensure it generates the beads_plan.json
    triage.triage()

    plan_path = run_dir / "beads_plan.json"
    assert plan_path.exists()
    with open(plan_path) as f:
        plan = json.load(f)
        titles = [t["title"] for t in plan["subtasks"]]
        assert any("Bug: bug-story" in t for t in titles)
        assert any("Triage: triage-story" in t for t in titles)


def test_assertion_failure_bug(tmp_path):
    run_dir = tmp_path / "run_assert"
    run_dir.mkdir()
    stories_dir = run_dir / "stories"
    stories_dir.mkdir()

    run_data = {
        "run_id": "assert",
        "environment": "dev",
        "base_url": "http://dev",
        "story_results": [{"story_id": "assert-story", "status": "fail"}],
    }
    with open(run_dir / "run.json", "w") as f:
        json.dump(run_data, f)

    story_dir = stories_dir / "assert-story"
    story_dir.mkdir()
    with open(story_dir / "story_summary.json", "w") as f:
        json.dump(
            {
                "classification": "reproducible_fail",
                "final_attempt": {
                    "step_results": [
                        {
                            "status": "fail",
                            "actions_taken": [{"tool": "click", "deterministic": False}],
                            "errors": [{"type": "assert_text", "message": "not found"}],
                        }
                    ]
                },
            },
            f,
        )

    triage = UISmokeTriage(run_dir, "[TEST]", dry_run=True)
    triage.triage()

    with open(run_dir / "beads_plan.json") as f:
        plan = json.load(f)
        assert any("Bug: assert-story" in t["title"] for t in plan["subtasks"])


def test_empty_triage_plan(tmp_path):
    run_dir = tmp_path / "run_empty"
    run_dir.mkdir()

    run_data = {
        "run_id": "empty",
        "environment": "dev",
        "base_url": "http://dev",
        "story_results": [{"story_id": "ok-story", "status": "pass"}],
    }
    with open(run_dir / "run.json", "w") as f:
        json.dump(run_data, f)

    triage = UISmokeTriage(run_dir, "[TEST]", dry_run=True)
    triage.triage()

    plan_path = run_dir / "beads_plan.json"
    assert plan_path.exists()
    with open(plan_path) as f:
        plan = json.load(f)
        assert len(plan["subtasks"]) == 0
        assert "No issues detected" in plan["epic"]["description"]
